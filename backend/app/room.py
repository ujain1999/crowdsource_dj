"""Authoritative, in-memory room state and the realtime protocol.

The server owns the room clock. Playback is described as
    {playing, position, updated_at}
and every client derives the live position as
    position + (server_now - updated_at)   while playing.
Any change is broadcast as a full state snapshot, so a client that misses a
message converges on the next one.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import random
import re
import secrets
import string
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from . import auth, config, db, music

log = logging.getLogger(__name__)

ROLE_RANK = {"listener": 0, "mod": 1, "codj": 2, "dj": 3}
ROLE_LABEL = {"listener": "listener", "mod": "moderator", "codj": "co-DJ", "dj": "DJ"}
SLOW_ACTIONS = {"add", "add_url", "refresh_suggestions"}
VOTESKIP_RE = re.compile(r"(^|\s)/voteskip\b", re.IGNORECASE)
ROOM_ID_LEN = 12
HISTORY_LIMIT = 100
LEAVE_ANNOUNCE_DELAY = 4.0


# ---- room ids -----------------------------------------------------------------

def new_room_id() -> str:
    return "".join(secrets.choice(string.ascii_uppercase) for _ in range(ROOM_ID_LEN))


def normalize_room_id(raw: str) -> str | None:
    letters = re.sub(r"[^A-Za-z]", "", raw or "").upper()
    return letters if len(letters) == ROOM_ID_LEN else None


def pretty_room_id(room_id: str) -> str:
    return "-".join(room_id[i:i + 4] for i in range(0, ROOM_ID_LEN, 4))


# ---- people -----------------------------------------------------------------------

@dataclass
class Identity:
    key: str            # "u:<user id>" for accounts, "g:<hash of client id>" for guests
    name: str
    user_id: int | None = None

    @classmethod
    def for_user(cls, user: auth.User) -> "Identity":
        return cls(f"u:{user.id}", user.username, user.id)

    @classmethod
    def for_guest(cls, client_id: str, name: str) -> "Identity":
        client_id = re.sub(r"[^A-Za-z0-9_-]", "", client_id or "")[:40] or secrets.token_hex(8)
        # Keys are shown to everyone in the room, and the client id is what proves who a
        # guest is. Publishing a hash means nobody can copy a key to impersonate a guest.
        digest = hashlib.sha256(client_id.encode()).hexdigest()[:24]
        return cls(f"g:{digest}", clean_name(name) or "Mystery Guest", None)


def clean_name(name: str | None) -> str:
    return re.sub(r"\s+", " ", (name or "")).strip()[:24]


class Client:
    """One websocket connection. Outgoing messages go through a queue so
    broadcasts never block the room and sends never interleave."""

    def __init__(self, identity: Identity, send: Callable[[dict], Awaitable[None]], close: Callable[[], Awaitable[None]]):
        self.identity = identity
        self._send = send
        self._close = close
        self._outbox: asyncio.Queue = asyncio.Queue()
        self.closed = False

    @property
    def key(self) -> str:
        return self.identity.key

    def send(self, msg: dict) -> None:
        if not self.closed:
            self._outbox.put_nowait(msg)

    def close_soon(self) -> None:
        self._outbox.put_nowait(None)

    async def pump(self) -> None:
        while True:
            msg = await self._outbox.get()
            if msg is None:
                self.closed = True
                try:
                    await self._close()
                except Exception:
                    pass
                return
            try:
                await self._send(msg)
            except Exception:
                self.closed = True
                return


@dataclass
class Member:
    identity: Identity
    joined_at: float = field(default_factory=time.time)
    clients: set = field(default_factory=set)
    tuned: bool = False   # has a working player (tapped in)

    @property
    def key(self) -> str:
        return self.identity.key

    @property
    def name(self) -> str:
        return self.identity.name


class ActionError(Exception):
    pass


# ---- room -------------------------------------------------------------------------

class Room:
    def __init__(self, room_id: str, on_deleted: Callable[[str], None] | None = None):
        self.id = room_id
        self.name = "Untitled party"
        self.created_at = time.time()
        self.owner_user_id: int | None = None
        self.dj_key: str | None = None
        self.dj_name: str | None = None
        self.roles: dict[str, str] = {}          # key -> "codj" | "mod"
        self.role_names: dict[str, str] = {}     # key -> display name, for staff who are offline
        self.settings = {"skip_threshold": 50}
        self.queue: list[dict] = []
        self.current = -1
        self.playing = False
        self.position = 0.0
        self.updated_at = time.time()
        self.finished = False                    # queue ran out, nothing left to play
        self.auto_paused = False                 # paused because the room emptied
        self.suggestions: list[dict] = []
        self.suggestions_loading = False
        self.chat: deque = deque(maxlen=config.CHAT_HISTORY)
        self.polls: dict[str, dict] = {}
        self.banned: dict[str, float] = {}

        self.members: dict[str, Member] = {}
        self.dj_left_at: float | None = None
        self.deleted = False
        self._on_deleted = on_deleted
        self._advance_lock = asyncio.Lock()
        self._end_task: asyncio.Task | None = None
        self._grace_task: asyncio.Task | None = None
        self._empty_task: asyncio.Task | None = None
        self._poll_task: asyncio.Task | None = None
        self._broadcast_pending = False
        self._save_handle: asyncio.TimerHandle | None = None
        self._bg: set[asyncio.Task] = set()
        self._leaving: dict[str, asyncio.Task] = {}
        self._error_reports: dict[str, set[str]] = {}  # track uid -> keys whose player failed   # key -> pending "left" announcement

    # ---- persistence ---------------------------------------------------------

    def snapshot(self) -> dict:
        return {
            "name": self.name,
            "created_at": self.created_at,
            "owner_user_id": self.owner_user_id,
            "dj_key": self.dj_key,
            "dj_name": self.dj_name,
            "roles": self.roles,
            "role_names": self.role_names,
            "settings": self.settings,
            "queue": self.queue,
            "current": self.current,
            "playing": self.playing,
            "position": self.live_position(),
            "finished": self.finished,
            "suggestions": self.suggestions,
            "chat": list(self.chat),
            "polls": self.polls,
        }

    @classmethod
    def restore(cls, room_id: str, data: dict, on_deleted=None) -> "Room":
        room = cls(room_id, on_deleted)
        for k in ("name", "created_at", "owner_user_id", "dj_key", "dj_name", "roles",
                  "role_names", "queue", "current", "finished", "suggestions", "polls"):
            if k in data:
                setattr(room, k, data[k])
        room.settings.update(data.get("settings") or {})
        room.chat.extend(data.get("chat") or [])
        room.position = float(data.get("position") or 0)
        # Nobody is listening after a restart; resume when someone joins.
        room.auto_paused = bool(data.get("playing"))
        room.playing = False
        room.updated_at = time.time()
        room.dj_left_at = time.time()
        for poll in room.polls.values():
            if poll["status"] == "open":
                poll["status"] = "cancelled"
        return room

    def _schedule_save(self) -> None:
        if self.deleted:
            return
        if self._save_handle:
            self._save_handle.cancel()
        self._save_handle = asyncio.get_running_loop().call_later(0.5, self.save_now)

    def save_now(self) -> None:
        if not self.deleted:
            db.save_room(self.id, self.snapshot())

    # ---- helpers ---------------------------------------------------------------

    def role_of(self, key: str) -> str:
        if key == self.dj_key:
            return "dj"
        return self.roles.get(key, "listener")

    def rank(self, key: str) -> int:
        return ROLE_RANK[self.role_of(key)]

    def current_track(self) -> dict | None:
        return self.queue[self.current] if 0 <= self.current < len(self.queue) else None

    def live_position(self) -> float:
        pos = self.position
        if self.playing:
            pos += time.time() - self.updated_at
        track = self.current_track()
        if track and track.get("duration"):
            pos = min(pos, float(track["duration"]))
        return max(0.0, pos)

    def _spawn(self, coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._bg.add(task)
        task.add_done_callback(self._bg.discard)
        return task

    def public_state(self) -> dict:
        members = sorted(
            self.members.values(),
            key=lambda m: (-self.rank(m.key), m.joined_at),
        )
        recent_polls = dict(list(self.polls.items())[-10:])
        return {
            "id": self.id,
            "pretty_id": pretty_room_id(self.id),
            "name": self.name,
            "dj_key": self.dj_key,
            "dj_name": self.dj_name,
            "dj_online": self.dj_key in self.members,
            "settings": self.settings,
            "members": [
                {"key": m.key, "name": m.name, "role": self.role_of(m.key), "is_user": m.identity.user_id is not None}
                for m in members
            ],
            "queue": self.queue,
            "current": self.current,
            "playback": {
                "playing": self.playing,
                "position": self.position,
                "updated_at": self.updated_at,
                "finished": self.finished,
            },
            "suggestions": self.suggestions,
            "suggestions_loading": self.suggestions_loading,
            "polls": {pid: self._poll_public(p) for pid, p in recent_polls.items()},
            "server_time": time.time(),
        }

    def changed(self) -> None:
        """Mark state dirty; one broadcast goes out per event-loop tick."""
        if self._broadcast_pending or self.deleted:
            return
        self._broadcast_pending = True
        asyncio.get_running_loop().call_soon(self._flush)

    def _flush(self) -> None:
        self._broadcast_pending = False
        if self.deleted:
            return
        self.broadcast({"type": "state", "state": self.public_state()})
        self._schedule_save()

    def broadcast(self, msg: dict) -> None:
        for member in self.members.values():
            for client in member.clients:
                client.send(msg)

    def post(self, text: str, *, kind: str = "system", member: Member | None = None, **extra) -> dict:
        msg = {
            "id": secrets.token_hex(6),
            "kind": kind,
            "text": text,
            "ts": time.time(),
            "key": member.key if member else None,
            "name": member.name if member else None,
            "role": self.role_of(member.key) if member else None,
            **extra,
        }
        self.chat.append(msg)
        self.broadcast({"type": "chat", "message": msg})
        self._schedule_save()
        return msg

    # ---- joining & leaving ----------------------------------------------------------

    def is_banned(self, key: str) -> bool:
        until = self.banned.get(key)
        if until and until > time.time():
            return True
        self.banned.pop(key, None)
        return False

    def attach(self, client: Client, announce: bool = True) -> Member:
        key = client.key
        member = self.members.get(key)
        is_new = member is None
        if is_new:
            member = Member(client.identity)
            self.members[key] = member
        else:
            member.identity = client.identity
        member.clients.add(client)
        if client.identity.user_id is not None and key in self.roles:
            self.role_names[key] = client.identity.name

        if self._empty_task:
            self._empty_task.cancel()
            self._empty_task = None

        if key == self.dj_key:
            self.dj_left_at = None
            self.dj_name = member.name
            if self._grace_task:
                self._grace_task.cancel()
                self._grace_task = None
        elif self.dj_key is None or self.dj_key not in self.members:
            self._check_dj_absence()

        if self.auto_paused and self.current_track():
            self.auto_paused = False
            self._set_playback(True, self.position)

        returning = self._leaving.pop(key, None)
        if returning:
            returning.cancel()  # back within seconds (a refresh): no join/leave noise
        elif is_new and announce:
            self.post(f"{member.name} joined the party")
        self._poll_recheck()
        self.changed()
        return member

    def detach(self, client: Client, *, explicit: bool = False, announce: bool = True) -> None:
        member = self.members.get(client.key)
        if not member:
            return
        member.clients.discard(client)
        if member.clients:
            return
        del self.members[client.key]
        if announce:
            self._announce_leave(member)
        if client.key == self.dj_key:
            self.dj_left_at = time.time()
            if explicit:
                self.dj_left_at -= config.DJ_GRACE_SECONDS
                self._succeed()
            else:
                self._start_grace(config.DJ_GRACE_SECONDS)
        if not self.members:
            self._empty_task = self._spawn(self._pause_when_empty())
        self._poll_recheck()
        self.changed()

    def _announce_leave(self, member: Member) -> None:
        async def later():
            await asyncio.sleep(LEAVE_ANNOUNCE_DELAY)
            self._leaving.pop(member.key, None)
            if member.key not in self.members:
                self.post(f"{member.name} left")

        if member.key in self._leaving:
            self._leaving[member.key].cancel()
        self._leaving[member.key] = self._spawn(later())

    async def _pause_when_empty(self) -> None:
        await asyncio.sleep(config.DJ_GRACE_SECONDS)
        if not self.members and self.playing:
            self._set_playback(False, self.live_position())
            self.auto_paused = True
            self.changed()

    def _check_dj_absence(self) -> None:
        if self.dj_key is None:
            self._succeed()
            return
        if self.dj_left_at is None:
            self.dj_left_at = time.time()
        waited = time.time() - self.dj_left_at
        if waited >= config.DJ_GRACE_SECONDS:
            self._succeed()
        elif not self._grace_task:
            self._start_grace(config.DJ_GRACE_SECONDS - waited)

    def _start_grace(self, delay: float) -> None:
        if self._grace_task:
            self._grace_task.cancel()

        async def wait():
            await asyncio.sleep(delay)
            self._grace_task = None
            if self.dj_key not in self.members:
                self._succeed()
                self.changed()

        self._grace_task = self._spawn(wait())

    def _succeed(self) -> bool:
        """Hand the booth to someone present: co-DJ, then moderator, then anyone
        (people with accounts first)."""
        candidates = [m for k, m in self.members.items() if k != self.dj_key]
        if not candidates:
            return False
        pick = None
        for tier in ("codj", "mod"):
            pool = [m for m in candidates if self.roles.get(m.key) == tier]
            if pool:
                pick = random.choice(pool)
                break
        if pick is None:
            users = [m for m in candidates if m.identity.user_id is not None]
            pick = random.choice(users or candidates)
        old_name = self.dj_name
        self.roles.pop(pick.key, None)
        self.role_names.pop(pick.key, None)
        self.dj_key = pick.key
        self.dj_name = pick.name
        self.dj_left_at = None
        if self._grace_task:
            self._grace_task.cancel()
            self._grace_task = None
        who = f"{old_name} left the booth. " if old_name else ""
        self.post(f"{who}{pick.name} is now the DJ 🎧", event="dj_change")
        self.changed()
        return True

    def reidentify(self, client: Client, identity: Identity) -> None:
        """Switch a live connection to a new identity (guest logged in, or logged out)."""
        old_key = client.key
        if identity.key == old_key:
            client.identity = identity
            return
        old_member = self.members.get(old_key)
        old_name = old_member.name if old_member else "Someone"
        if old_member:
            old_member.clients.discard(client)
            if not old_member.clients:
                del self.members[old_key]
        client.identity = identity
        # Carry votes over so switching accounts can't double-vote.
        for poll in self.polls.values():
            if poll["status"] == "open" and old_key in poll["votes"]:
                poll["votes"].setdefault(identity.key, poll["votes"].pop(old_key))
        if old_key == self.dj_key and old_key not in self.members:
            if identity.user_id is not None:
                # A guest DJ who logs in keeps the booth.
                self.dj_key, self.dj_name = identity.key, identity.name
                self.roles.pop(identity.key, None)
            else:
                # A DJ logging out gives up the booth right away.
                self.dj_left_at = time.time() - config.DJ_GRACE_SECONDS
        self.attach(client, announce=False)
        if identity.user_id is not None:
            self.post(f"{old_name} logged in as {identity.name}")
        else:
            self.post(f"{old_name} logged out and is listening as {identity.name}")

    # ---- playback ------------------------------------------------------------------------

    def _set_playback(self, playing: bool, position: float) -> None:
        self.playing = playing
        self.position = max(0.0, position)
        self.updated_at = time.time()
        self._reschedule_end()

    def _reschedule_end(self) -> None:
        if self._end_task:
            self._end_task.cancel()
            self._end_task = None
        track = self.current_track()
        if not (self.playing and track and track.get("duration")):
            return
        remaining = float(track["duration"]) - self.live_position()
        uid = track["uid"]

        async def end_later():
            await asyncio.sleep(max(0.0, remaining) + 1.0)
            self._end_task = None
            await self.advance(expected_uid=uid)

        self._end_task = self._spawn(end_later())

    def play_index(self, index: int) -> None:
        self.current = index
        self.finished = False
        self.auto_paused = False
        self._close_open_polls("The song changed before the vote finished.")
        self._set_playback(True, 0.0)
        self._trim_history()
        self.changed()

    def _trim_history(self) -> None:
        extra = self.current - HISTORY_LIMIT
        if extra > 0:
            del self.queue[:extra]
            self.current -= extra

    async def advance(self, expected_uid: str | None = None, *, force: bool = False) -> None:
        """Move to the next song; promote a suggestion if the queue has run out."""
        async with self._advance_lock:
            track = self.current_track()
            if not force and expected_uid is not None and (track is None or track["uid"] != expected_uid):
                return  # someone already moved on
            if self.current + 1 < len(self.queue):
                self.play_index(self.current + 1)
                return
            if not self.suggestions:
                await self.fill_suggestions()
            if self.deleted:
                return
            if self.suggestions:
                pick = self.suggestions.pop(0)
                self.queue.append(self._entry(pick, "Suggestions", None))
                self.play_index(len(self.queue) - 1)
                self.post(f"Queue ran dry, so “{pick['title']}” moved up from suggestions ✨")
                if len(self.suggestions) < 3:
                    self._spawn(self.fill_suggestions(seed=pick["video_id"]))
                return
            # Nothing left anywhere: stop at the end of the last song.
            track = self.current_track()
            self.finished = True
            self._set_playback(False, float(track["duration"]) if track else 0.0)
            self.changed()

    def _entry(self, track: dict, added_by: str, added_by_key: str | None) -> dict:
        return {
            **{k: track.get(k) for k in ("video_id", "title", "artist", "album", "duration", "thumb")},
            "uid": secrets.token_hex(6),
            "added_by": added_by,
            "added_by_key": added_by_key,
            "added_at": time.time(),
        }

    def _is_idle(self) -> bool:
        return self.current_track() is None or self.finished

    def add_tracks(self, tracks: list[dict], member: Member) -> None:
        if not tracks:
            return
        upcoming = len(self.queue) - max(self.current, -1) - 1
        room_left = config.MAX_QUEUE_LENGTH - upcoming
        if room_left <= 0:
            raise ActionError(f"The queue is full ({config.MAX_QUEUE_LENGTH} songs). Wait for a few to play.")
        tracks = tracks[:room_left]
        was_idle = self._is_idle()
        first_new = len(self.queue)
        for t in tracks:
            self.queue.append(self._entry(t, member.name, member.key))
        if was_idle:
            self.play_index(first_new)
        if len(tracks) == 1:
            self.post(f"{member.name} queued “{tracks[0]['title']}”", event="queued")
        else:
            self.post(f"{member.name} queued {len(tracks)} songs", event="queued")
        if not self.suggestions and not self.suggestions_loading:
            self._spawn(self.fill_suggestions())
        self.changed()

    # ---- suggestions -------------------------------------------------------------------

    async def fill_suggestions(self, seed: str | None = None, *, replace: bool = False) -> None:
        if self.suggestions_loading:
            return
        seeds = [seed] if seed else []
        track = self.current_track()
        if track:
            seeds.append(track["video_id"])
        if self.queue:
            seeds.append(self.queue[-1]["video_id"])
            seeds.extend(random.sample([t["video_id"] for t in self.queue], min(3, len(self.queue))))
        seeds = list(dict.fromkeys(s for s in seeds if s))
        if not seeds:
            return
        self.suggestions_loading = True
        self.changed()
        try:
            # A refresh should bring new songs, so current suggestions are excluded too.
            exclude = {t["video_id"] for t in self.queue} | {t["video_id"] for t in self.suggestions}
            fresh: list[dict] = []
            for s in seeds:
                for t in await asyncio.to_thread(music.radio, s):
                    if t["video_id"] not in exclude:
                        exclude.add(t["video_id"])
                        fresh.append(t)
                if len(fresh) >= config.SUGGESTIONS_TARGET:
                    break
            if replace:
                random.shuffle(fresh)
                self.suggestions = fresh[: config.SUGGESTIONS_TARGET] or self.suggestions
            else:
                self.suggestions = (self.suggestions + fresh)[: config.SUGGESTIONS_TARGET]
        finally:
            self.suggestions_loading = False
            self.changed()

    # ---- voteskip polls ----------------------------------------------------------------

    def _poll_public(self, poll: dict) -> dict:
        votes = {k: v for k, v in poll["votes"].items()}
        eligible = len(self.members) if poll["status"] == "open" else poll.get("final_eligible", 0)
        return {
            "id": poll["id"],
            "track_uid": poll["track_uid"],
            "track_title": poll["track_title"],
            "started_by": poll["started_by"],
            "threshold": poll["threshold"],
            "status": poll["status"],
            "reason": poll.get("reason"),
            "ends_at": poll["ends_at"],
            "yes": sum(1 for v in votes.values() if v),
            "no": sum(1 for v in votes.values() if not v),
            "eligible": eligible,
            "needed": (eligible * poll["threshold"]) // 100 + 1,
            "votes": votes,
        }

    def open_poll(self) -> dict | None:
        for poll in self.polls.values():
            if poll["status"] == "open":
                return poll
        return None

    def start_voteskip(self, member: Member) -> None:
        track = self.current_track()
        if not track or self.finished:
            raise ActionError("Nothing is playing, so there's nothing to skip.")
        poll = self.open_poll()
        if poll:
            self.vote(member, poll["id"], True)
            return
        poll = {
            "id": secrets.token_hex(5),
            "track_uid": track["uid"],
            "track_title": track["title"],
            "started_by": member.name,
            "threshold": int(self.settings["skip_threshold"]),
            "status": "open",
            "created_at": time.time(),
            "ends_at": time.time() + config.POLL_SECONDS,
            "votes": {member.key: True},
        }
        self.polls[poll["id"]] = poll
        while len(self.polls) > 20:
            self.polls.pop(next(iter(self.polls)))
        self.post(f"{member.name} wants to skip “{track['title']}”", kind="poll", member=member, poll_id=poll["id"])
        if self._poll_task:
            self._poll_task.cancel()
        self._poll_task = self._spawn(self._poll_timeout(poll["id"]))
        self._evaluate_poll(poll)
        self.changed()

    async def _poll_timeout(self, poll_id: str) -> None:
        await asyncio.sleep(config.POLL_SECONDS)
        poll = self.polls.get(poll_id)
        if poll and poll["status"] == "open":
            self._finish_poll(poll, "failed", "Time ran out.")
            self.changed()

    def vote(self, member: Member, poll_id: str, yes: bool) -> None:
        poll = self.polls.get(poll_id)
        if not poll or poll["status"] != "open":
            raise ActionError("That vote has already closed.")
        if member.key in poll["votes"]:
            raise ActionError("You've already voted on this one.")
        poll["votes"][member.key] = bool(yes)
        self._evaluate_poll(poll)
        self.changed()

    def _poll_recheck(self) -> None:
        poll = self.open_poll()
        if poll:
            self._evaluate_poll(poll)

    def _evaluate_poll(self, poll: dict) -> None:
        eligible = len(self.members)
        if eligible == 0:
            return
        online_votes = {k: v for k, v in poll["votes"].items() if k in self.members}
        yes = sum(1 for v in online_votes.values() if v)
        no = sum(1 for v in online_votes.values() if not v)
        threshold = poll["threshold"]
        if yes * 100 > threshold * eligible:
            self._finish_poll(poll, "passed", f"{yes} of {eligible} voted to skip.")
            track = self.current_track()
            if track and track["uid"] == poll["track_uid"]:
                self._spawn(self.advance(expected_uid=track["uid"]))
        elif (eligible - no) * 100 <= threshold * eligible:
            self._finish_poll(poll, "failed", f"{no} of {eligible} voted to keep it.")

    def _finish_poll(self, poll: dict, status: str, reason: str) -> None:
        poll["status"] = status
        poll["reason"] = reason
        poll["final_eligible"] = len(self.members)
        if self._poll_task:
            self._poll_task.cancel()
            self._poll_task = None
        verdict = {"passed": "Skipped", "failed": "Staying on", "cancelled": "Vote cancelled for"}[status]
        self.post(f"{verdict} “{poll['track_title']}”. {reason}", event=f"poll_{status}", poll_id=poll["id"])

    def _close_open_polls(self, reason: str) -> None:
        track = self.current_track()
        for poll in self.polls.values():
            if poll["status"] == "open" and (track is None or poll["track_uid"] != track["uid"]):
                self._finish_poll(poll, "cancelled", reason)

    # ---- deletion ----------------------------------------------------------------------------

    def delete(self, by: Member) -> None:
        self.broadcast({"type": "room_deleted", "by": by.name})
        for member in list(self.members.values()):
            for client in list(member.clients):
                client.close_soon()
        self.deleted = True
        for task in (self._end_task, self._grace_task, self._empty_task, self._poll_task, *self._bg):
            if task and task is not asyncio.current_task():
                task.cancel()
        if self._save_handle:
            self._save_handle.cancel()
        db.delete_room(self.id)
        if self._on_deleted:
            self._on_deleted(self.id)

    # ---- actions ------------------------------------------------------------------------------

    async def handle(self, client: Client, msg: dict) -> None:
        kind = msg.get("type")
        member = self.members.get(client.key)
        if member is None or self.deleted:
            return
        if kind == "ping":
            client.send({"type": "pong", "t": msg.get("t"), "server_time": time.time()})
            return
        handler = ACTIONS.get(kind)
        if handler is None:
            client.send({"type": "error", "message": f"Unknown action “{kind}”."})
            return
        min_role, fn = handler
        if self.rank(member.key) < ROLE_RANK[min_role]:
            client.send({"type": "error", "message": f"Only a {ROLE_LABEL[min_role]} or higher can do that."})
            return
        if kind in SLOW_ACTIONS:
            # Network-bound; don't hold up this person's other actions (like pause).
            self._spawn(self._run(fn, client, member, msg))
        else:
            await self._run(fn, client, member, msg)

    async def _run(self, fn, client: Client, member: Member, msg: dict) -> None:
        try:
            await fn(self, client, member, msg)
        except ActionError as e:
            client.send({"type": "error", "message": str(e)})
        except Exception:
            log.exception("action %s failed in room %s", msg.get("type"), self.id)
            client.send({"type": "error", "message": "Something went wrong on our side. Try that again."})

    def _find_uid(self, uid: Any) -> int:
        for i, t in enumerate(self.queue):
            if t["uid"] == uid:
                return i
        raise ActionError("That song isn't in the queue anymore.")

    def _require_account(self, key: str) -> Member:
        target = self.members.get(key)
        if target is None:
            raise ActionError("That person isn't in the room right now.")
        return target


# Each handler: async (room, client, member, msg) -> None

async def a_chat(room: Room, client: Client, member: Member, msg: dict) -> None:
    text = re.sub(r"[\r\n]{3,}", "\n\n", str(msg.get("text") or "")).strip()[: config.MAX_CHAT_LENGTH]
    if not text:
        return
    if VOTESKIP_RE.search(text):
        rest = VOTESKIP_RE.sub(" ", text).strip()
        if rest:
            room.post(text, kind="user", member=member)
        room.start_voteskip(member)
        return
    room.post(text, kind="user", member=member)


async def a_vote(room, client, member, msg):
    room.vote(member, str(msg.get("poll_id")), bool(msg.get("yes")))


async def a_add(room, client, member, msg):
    video_id = str(msg.get("video_id") or "")
    track = await asyncio.to_thread(music.get_track, video_id)
    if not track:
        raise ActionError("Couldn't find that song on YouTube.")
    if msg.get("from_suggestions"):
        room.suggestions = [s for s in room.suggestions if s["video_id"] != video_id]
    room.add_tracks([track], member)


async def a_add_url(room, client, member, msg):
    url = str(msg.get("url") or "")
    if not music.looks_like_url(url):
        raise ActionError("Paste a youtube.com, music.youtube.com or youtu.be link.")
    client.send({"type": "toast", "text": "Fetching that link…"})
    tracks = await asyncio.to_thread(music.resolve, url)
    if not tracks:
        raise ActionError("Couldn't read that link. Is the video or playlist public?")
    room.add_tracks(tracks, member)


async def a_remove(room, client, member, msg):
    idx = room._find_uid(msg.get("uid"))
    entry = room.queue[idx]
    if entry.get("added_by_key") != member.key and room.rank(member.key) < ROLE_RANK["mod"]:
        raise ActionError("You can only remove songs you added.")
    del room.queue[idx]
    if idx < room.current:
        room.current -= 1
    elif idx == room.current:
        # Removing the song that's playing moves on to whatever is next.
        room.current = idx - 1
        await room.advance(force=True)
    room.changed()


async def a_move(room, client, member, msg):
    idx = room._find_uid(msg.get("uid"))
    if idx <= room.current:
        raise ActionError("Only upcoming songs can be moved.")
    try:
        to = int(msg.get("to", idx))
    except (TypeError, ValueError, OverflowError):
        raise ActionError("That isn't a valid spot in the queue.")
    to = max(room.current + 1, min(to, len(room.queue) - 1))
    entry = room.queue.pop(idx)
    room.queue.insert(to, entry)
    room.changed()


async def a_play(room, client, member, msg):
    if room.current_track() is None:
        if room.queue:
            room.play_index(0)
        return
    if room.finished:
        await room.advance(force=True)
        if room.finished:
            room.play_index(room.current)  # nothing new; replay the last song
        return
    room._set_playback(True, room.live_position())
    room.changed()


async def a_pause(room, client, member, msg):
    room._set_playback(False, room.live_position())
    room.changed()


async def a_seek(room, client, member, msg):
    track = room.current_track()
    if not track:
        return
    try:
        pos = float(msg.get("position") or 0)
    except (TypeError, ValueError):
        raise ActionError("That isn't a valid position.")
    if not math.isfinite(pos):
        raise ActionError("That isn't a valid position.")
    if track.get("duration"):
        pos = min(pos, float(track["duration"]) - 0.5)
    room.finished = False
    room._set_playback(room.playing, pos)
    room.changed()


async def a_next(room, client, member, msg):
    track = room.current_track()
    await room.advance(expected_uid=track["uid"] if track else None, force=track is None)


async def a_prev(room, client, member, msg):
    if room.current > 0:
        room.play_index(room.current - 1)
    elif room.current_track():
        room.play_index(room.current)


async def a_jump(room, client, member, msg):
    room.play_index(room._find_uid(msg.get("uid")))


async def a_ended(room, client, member, msg):
    track = room.current_track()
    if not track or track["uid"] != msg.get("uid") or not room.playing:
        return
    duration = float(track.get("duration") or 0)
    if duration == 0 or room.live_position() >= duration - 10:
        await room.advance(expected_uid=track["uid"])


async def a_tuned(room, client, member, msg):
    member.tuned = True


async def a_player_error(room, client, member, msg):
    """One listener's player failing (region lock, ad blocker…) shouldn't skip the song for
    everyone. Skip once more than half of the people with a running player report it."""
    track = room.current_track()
    if not track or track["uid"] != msg.get("uid") or track.get("failed"):
        return
    reports = room._error_reports.setdefault(track["uid"], set())
    reports.add(member.key)
    tuned = [k for k, m in room.members.items() if m.tuned or k in reports]
    if len(reports & set(tuned)) * 2 <= len(tuned):
        client.send({"type": "toast", "text": "This song won't play in your browser. Waiting to see if it works for others."})
        return
    track["failed"] = True
    room._error_reports.pop(track["uid"], None)
    room.post(f"YouTube won't play “{track['title']}” here, so it's been skipped.")
    await room.advance(expected_uid=track["uid"])


async def a_refresh_suggestions(room, client, member, msg):
    if not room.queue:
        raise ActionError("Add a song first. Suggestions are based on what's in the queue.")
    await room.fill_suggestions(replace=True)


async def a_remove_suggestion(room, client, member, msg):
    room.suggestions = [s for s in room.suggestions if s["video_id"] != msg.get("video_id")]
    room.changed()


async def a_set_role(room, client, member, msg):
    key = str(msg.get("key") or "")
    role = msg.get("role")
    if role not in ("codj", "mod", "listener"):
        raise ActionError("Pick co-DJ, moderator or listener.")
    if key == room.dj_key:
        raise ActionError("The DJ's role can't be changed. They can hand the booth over instead.")
    target = room._require_account(key)
    if target.identity.user_id is None and role != "listener":
        raise ActionError(f"{target.name} needs to log in before they can be a {ROLE_LABEL[role]}.")
    if role == "listener":
        room.roles.pop(key, None)
        room.role_names.pop(key, None)
    else:
        room.roles[key] = role
        room.role_names[key] = target.name
    room.post(f"{member.name} made {target.name} a {ROLE_LABEL[role]}", event="role_change")
    room.changed()


async def a_transfer_dj(room, client, member, msg):
    target = room._require_account(str(msg.get("key") or ""))
    if target.key == member.key:
        return
    if target.identity.user_id is None:
        raise ActionError(f"{target.name} needs to log in before they can be the DJ.")
    room.roles.pop(target.key, None)
    room.roles[member.key] = "codj"
    room.role_names[member.key] = member.name
    room.dj_key, room.dj_name = target.key, target.name
    room.post(f"{member.name} handed the booth to {target.name} 🎧", event="dj_change")
    room.changed()


async def a_settings(room, client, member, msg):
    if "skip_threshold" in msg:
        try:
            value = int(msg["skip_threshold"])
        except (TypeError, ValueError):
            raise ActionError("The skip threshold must be a whole number.")
        if not 1 <= value <= 99:
            raise ActionError("The skip threshold must be between 1% and 99%.")
        if value != room.settings["skip_threshold"]:
            room.settings["skip_threshold"] = value
            room.post(f"{member.name} set votes needed to skip to more than {value}%")
    if "name" in msg:
        name = clean_name(msg["name"])[:40] if msg["name"] else ""
        if not name:
            raise ActionError("Give the room a name.")
        if name != room.name:
            room.name = name
            room.post(f"{member.name} renamed the room to “{name}”")
    room.changed()


async def a_kick(room, client, member, msg):
    key = str(msg.get("key") or "")
    target = room._require_account(key)
    if room.rank(key) >= room.rank(member.key):
        raise ActionError(f"You can't remove {target.name}.")
    room.banned[key] = time.time() + 600
    for c in list(target.clients):
        c.send({"type": "kicked", "by": member.name})
        c.close_soon()
        room.detach(c, announce=False)
    room.post(f"{member.name} removed {target.name} from the room")
    room.changed()


async def a_delete_message(room, client, member, msg):
    mid = msg.get("id")
    for m in room.chat:
        if m["id"] == mid:
            room.chat.remove(m)
            room.broadcast({"type": "chat_delete", "id": mid})
            room._schedule_save()
            return
    raise ActionError("That message is already gone.")


async def a_rename(room, client, member, msg):
    if member.identity.user_id is not None:
        raise ActionError("Your name comes from your account.")
    name = clean_name(msg.get("name"))
    if not name:
        raise ActionError("Pick a name with at least one character.")
    old = member.name
    member.identity.name = name
    for c in member.clients:
        c.identity = member.identity
        c.send({"type": "identity", "you": identity_public(member.identity)})
    if room.dj_key == member.key:
        room.dj_name = name
    room.post(f"{old} is now {name}")
    room.changed()


async def a_auth(room, client, member, msg):
    token = msg.get("token")
    if token:
        user = await asyncio.to_thread(auth.user_for_token, token)
        if not user:
            raise ActionError("Your login expired. Log in again.")
        identity = Identity.for_user(user)
    else:
        identity = Identity.for_guest(str(msg.get("client_id") or ""), msg.get("name") or member.name)
    if room.is_banned(identity.key):
        raise ActionError("That account was removed from this room recently.")
    room.reidentify(client, identity)
    client.send({"type": "identity", "you": identity_public(identity)})


async def a_leave(room, client, member, msg):
    room.detach(client, explicit=True)
    client.send({"type": "left"})
    client.close_soon()


async def a_delete_room(room, client, member, msg):
    room.delete(member)


ACTIONS: dict[str, tuple[str, Callable]] = {
    "chat": ("listener", a_chat),
    "vote": ("listener", a_vote),
    "add": ("listener", a_add),
    "add_url": ("listener", a_add_url),
    "remove": ("listener", a_remove),        # own songs; mods+ can remove any
    "ended": ("listener", a_ended),
    "player_error": ("listener", a_player_error),
    "tuned": ("listener", a_tuned),
    "rename": ("listener", a_rename),
    "auth": ("listener", a_auth),
    "leave": ("listener", a_leave),
    "kick": ("mod", a_kick),
    "delete_message": ("mod", a_delete_message),
    "move": ("codj", a_move),
    "play": ("codj", a_play),
    "pause": ("codj", a_pause),
    "seek": ("codj", a_seek),
    "next": ("codj", a_next),
    "prev": ("codj", a_prev),
    "jump": ("codj", a_jump),
    "refresh_suggestions": ("codj", a_refresh_suggestions),
    "remove_suggestion": ("codj", a_remove_suggestion),
    "set_role": ("codj", a_set_role),
    "settings": ("codj", a_settings),
    "transfer_dj": ("dj", a_transfer_dj),
    "delete_room": ("dj", a_delete_room),
}


def identity_public(identity: Identity) -> dict:
    return {
        "key": identity.key,
        "name": identity.name,
        "user": {"id": identity.user_id, "username": identity.name} if identity.user_id is not None else None,
    }


# ---- registry ---------------------------------------------------------------------------------

class RoomManager:
    def __init__(self):
        self.rooms: dict[str, Room] = {}

    def get(self, room_id: str) -> Room | None:
        room = self.rooms.get(room_id)
        if room:
            return room
        data = db.load_room(room_id)
        if data is None:
            return None
        room = Room.restore(room_id, data, on_deleted=self._forget)
        self.rooms[room_id] = room
        return room

    def create(self, owner: auth.User, name: str | None = None) -> Room:
        room_id = new_room_id()
        while room_id in self.rooms or db.room_exists(room_id):
            room_id = new_room_id()
        room = Room(room_id, on_deleted=self._forget)
        room.owner_user_id = owner.id
        room.dj_key = f"u:{owner.id}"
        room.dj_name = owner.username
        room.dj_left_at = time.time()  # the owner hasn't connected yet; grace starts now
        room.name = clean_name(name)[:40] if name else f"{owner.username}'s party"
        self.rooms[room_id] = room
        db.save_room(room_id, room.snapshot())
        return room

    def _forget(self, room_id: str) -> None:
        self.rooms.pop(room_id, None)

    def save_all(self) -> None:
        for room in self.rooms.values():
            room.save_now()
