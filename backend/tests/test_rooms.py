import re
import time

import pytest

from app import music
from app.room import normalize_room_id, pretty_room_id

pytestmark = pytest.mark.timeout(20)


def playing(state):
    return state["playback"]["playing"]


def current(state):
    i = state["current"]
    return state["queue"][i] if 0 <= i < len(state["queue"]) else None


# ---- accounts & room codes -----------------------------------------------------------------

def test_signup_login_me(client):
    r = client.post("/api/auth/signup", json={"username": "discoqueen", "password": "hunter22"})
    assert r.status_code == 200
    token = r.json()["token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["user"]["username"] == "discoqueen"
    assert client.post("/api/auth/signup", json={"username": "DiscoQueen", "password": "hunter22"}).status_code == 400
    assert client.post("/api/auth/login", json={"username": "discoqueen", "password": "nope123"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "discoqueen", "password": "hunter22"}).status_code == 200
    assert client.post("/api/auth/signup", json={"username": "x", "password": "hunter22"}).status_code == 400


def test_room_requires_login_and_has_12_letter_id(client, new_room):
    assert client.post("/api/rooms", json={}).status_code == 401
    room_id, _, _ = new_room()
    assert re.fullmatch(r"[A-Z]{12}", room_id)
    pretty = pretty_room_id(room_id)
    assert re.fullmatch(r"[A-Z]{4}-[A-Z]{4}-[A-Z]{4}", pretty)
    # Codes work with hyphens, without, and in lowercase.
    for variant in (room_id, pretty, pretty.lower()):
        assert client.get(f"/api/rooms/{variant}").json()["id"] == room_id
    assert client.get("/api/rooms/ABCDABCDABCD").status_code == 404
    assert normalize_room_id("abc") is None


def test_url_parsing():
    assert music.parse_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=3") == ("dQw4w9WgXcQ", None)
    assert music.parse_youtube_url("https://youtu.be/dQw4w9WgXcQ?si=x")[0] == "dQw4w9WgXcQ"
    assert music.parse_youtube_url("music.youtube.com/watch?v=dQw4w9WgXcQ&list=RDAMVM")[0] == "dQw4w9WgXcQ"
    assert music.parse_youtube_url("https://www.youtube.com/playlist?list=PL123") == (None, "PL123")
    assert music.parse_youtube_url("https://www.youtube.com/shorts/dQw4w9WgXcQ")[0] == "dQw4w9WgXcQ"
    assert music.looks_like_url("https://youtu.be/dQw4w9WgXcQ")
    assert not music.looks_like_url("daft punk")


# ---- sync & playback ------------------------------------------------------------------------

def test_creator_is_dj_and_guests_can_add_but_not_control(new_room, join):
    room_id, token, user = new_room()
    with join(room_id, token=token) as dj, join(room_id, name="Wobbly Otter") as guest:
        assert dj.role() == "dj"
        guest.until_state(lambda s: any(m["name"] == "Wobbly Otter" for m in s["members"]))
        assert guest.role() == "listener"

        guest.send(type="add", video_id="aaaaaaaaaaa")
        s = dj.until_state(lambda s: len(s["queue"]) == 1 and playing(s))
        assert current(s)["added_by"] == "Wobbly Otter"
        guest.until_state(lambda s: playing(s))

        guest.send(type="pause")
        assert "Only a co-DJ" in guest.until_error()

        dj.send(type="pause")
        for p in (dj, guest):
            s = p.until_state(lambda s: not playing(s))
        paused_at = s["playback"]["position"]
        time.sleep(0.3)
        dj.send(type="seek", position=42)
        for p in (dj, guest):
            s = p.until_state(lambda s: s["playback"]["position"] == 42)
            assert not playing(s)
        assert paused_at < 5

        dj.send(type="play")
        for p in (dj, guest):
            p.until_state(lambda s: playing(s) and s["playback"]["position"] == pytest.approx(42, abs=0.5))


def test_next_prev_and_suggestions_promote_when_queue_ends(new_room, join):
    room_id, token, _ = new_room()
    with join(room_id, token=token) as dj, join(room_id) as guest:
        guest.send(type="add", video_id="aaaaaaaaaaa")
        guest.send(type="add", video_id="bbbbbbbbbbb")
        s = dj.until_state(lambda s: len(s["queue"]) == 2 and len(s["suggestions"]) > 0)
        assert current(s)["video_id"] == "aaaaaaaaaaa"

        dj.send(type="next")
        s = guest.until_state(lambda s: current(s) and current(s)["video_id"] == "bbbbbbbbbbb")
        dj.send(type="prev")
        guest.until_state(lambda s: current(s)["video_id"] == "aaaaaaaaaaa")
        dj.send(type="next")
        s = guest.until_state(lambda s: current(s)["video_id"] == "bbbbbbbbbbb")
        first_suggestion = s["suggestions"][0]

        # Queue is at its last song: next pulls the top suggestion into the queue.
        dj.send(type="next")
        s = guest.until_state(lambda s: len(s["queue"]) == 3 and playing(s))
        assert current(s)["video_id"] == first_suggestion["video_id"]
        assert current(s)["added_by"] == "Suggestions"
        assert all(x["video_id"] != first_suggestion["video_id"] for x in s["suggestions"])


def test_client_reported_end_advances_once(new_room, join):
    room_id, token, _ = new_room()
    with join(room_id, token=token) as dj, join(room_id) as a:
        a.send(type="add", video_id="aaaaaaaaaaa")
        a.send(type="add", video_id="bbbbbbbbbbb")
        s = dj.until_state(lambda s: len(s["queue"]) == 2)
        uid = current(s)["uid"]
        # Too early: the server's clock says the song has barely started.
        a.send(type="ended", uid=uid)
        dj.send(type="seek", position=179)
        dj.until_state(lambda s: s["playback"]["position"] == 179)
        a.send(type="ended", uid=uid)
        dj.send(type="ended", uid=uid)  # duplicate report from another listener
        s = dj.until_state(lambda s: s["current"] == 1)
        time.sleep(0.2)
        dj.send(type="ping", t=1)
        dj.until(lambda m, _: m["type"] == "pong")
        assert dj.state["current"] == 1


def test_refresh_suggestions_is_dj_only(new_room, join):
    room_id, token, _ = new_room()
    with join(room_id, token=token) as dj, join(room_id) as guest:
        guest.send(type="add", video_id="aaaaaaaaaaa")
        before = dj.until_state(lambda s: len(s["suggestions"]) > 0)["suggestions"]
        guest.send(type="refresh_suggestions")
        assert "co-DJ" in guest.until_error()
        dj.send(type="refresh_suggestions")
        after = dj.until_state(lambda s: not s["suggestions_loading"] and s["suggestions"] != before)["suggestions"]
        assert {t["video_id"] for t in after}.isdisjoint({t["video_id"] for t in before})


def test_add_url(new_room, join):
    room_id, token, _ = new_room()
    with join(room_id, token=token) as dj:
        dj.send(type="add_url", url="https://www.youtube.com/playlist?list=PLxyz")
        s = dj.until_state(lambda s: len(s["queue"]) == 3)
        dj.send(type="add_url", url="https://youtu.be/ccccccccccc")
        s = dj.until_state(lambda s: len(s["queue"]) == 4)
        assert s["queue"][-1]["video_id"] == "ccccccccccc"
        dj.send(type="add_url", url="https://example.com/song")
        assert "youtube" in dj.until_error().lower()


def test_remove_own_song_only_unless_mod(new_room, join, signup):
    room_id, token, _ = new_room()
    mod_token, _ = signup()
    with join(room_id, token=token) as dj, join(room_id) as a, join(room_id) as b, join(room_id, token=mod_token) as mod:
        a.send(type="add", video_id="aaaaaaaaaaa")
        a.send(type="add", video_id="bbbbbbbbbbb")
        s = b.until_state(lambda s: len(s["queue"]) == 2)
        b.send(type="remove", uid=s["queue"][1]["uid"])
        assert "only remove songs you added" in b.until_error()
        dj.send(type="set_role", key=mod.key, role="mod")
        mod.until_state(lambda s: mod.role() == "mod")
        mod.send(type="remove", uid=s["queue"][1]["uid"])
        dj.until_state(lambda s: len(s["queue"]) == 1)


# ---- roles & DJ succession ------------------------------------------------------------------

def test_roles_need_accounts_and_codj_can_control_but_not_delete(new_room, join, signup):
    room_id, token, _ = new_room()
    co_token, _ = signup()
    with join(room_id, token=token) as dj, join(room_id) as guest, join(room_id, token=co_token) as co:
        dj.until_state(lambda s: len(s["members"]) == 3)
        dj.send(type="set_role", key=guest.key, role="codj")
        assert "needs to log in" in dj.until_error()

        dj.send(type="set_role", key=co.key, role="codj")
        co.until_state(lambda s: co.role() == "codj")
        guest.send(type="add", video_id="aaaaaaaaaaa")
        co.until_state(lambda s: playing(s))
        co.send(type="pause")
        guest.until_state(lambda s: not playing(s))

        # Co-DJs can change settings and appoint people...
        co.send(type="settings", skip_threshold=70)
        dj.until_state(lambda s: s["settings"]["skip_threshold"] == 70)
        # ...but can't delete the room or touch the DJ.
        co.send(type="delete_room")
        assert "Only a DJ" in co.until_error()
        co.send(type="set_role", key=dj.key, role="listener")
        assert "can't be changed" in co.until_error()


def test_dj_leaving_promotes_codj_first(new_room, join, signup):
    room_id, token, _ = new_room()
    t_co, _ = signup()
    t_mod, _ = signup()
    with join(room_id, token=t_co) as co, join(room_id, token=t_mod) as mod, join(room_id) as guest:
        with join(room_id, token=token) as dj:
            dj.send(type="set_role", key=co.key, role="codj")
            dj.send(type="set_role", key=mod.key, role="mod")
            guest.until_state(lambda s: guest.role(co.key) == "codj" and guest.role(mod.key) == "mod")
            dj.send(type="leave")
            s = guest.until_state(lambda s: s["dj_key"] == co.key)
        assert guest.role(co.key) == "dj"


def test_dj_leaving_promotes_mod_when_no_codj(new_room, join, signup):
    room_id, token, _ = new_room()
    t_mod, _ = signup()
    t_user, _ = signup()
    with join(room_id, token=t_mod) as mod, join(room_id, token=t_user) as other, join(room_id) as guest:
        with join(room_id, token=token) as dj:
            dj.send(type="set_role", key=mod.key, role="mod")
            guest.until_state(lambda s: guest.role(mod.key) == "mod")
            dj.send(type="leave")
        guest.until_state(lambda s: s["dj_key"] == mod.key)


def test_dj_disconnect_hands_over_after_grace_to_anyone(new_room, join):
    room_id, token, _ = new_room()
    with join(room_id) as guest:
        with join(room_id, token=token) as dj:
            guest.until_state(lambda s: s["dj_key"] == dj.key and len(s["members"]) == 2)
        # Socket closed without "leave" (e.g. tab closed): booth is held for the grace period.
        s = guest.until_state(lambda s: len(s["members"]) == 1)
        assert s["dj_key"] != guest.key
        s = guest.until_state(lambda s: s["dj_key"] == guest.key)
        assert guest.role() == "dj"


def test_dj_refresh_within_grace_keeps_booth(new_room, join):
    room_id, token, _ = new_room()
    with join(room_id) as guest:
        with join(room_id, token=token) as dj:
            dj_key = dj.key
        guest.until_state(lambda s: len(s["members"]) == 1)
        with join(room_id, token=token) as dj_again:
            assert dj_again.role() == "dj"
            time.sleep(0.6)
            dj_again.send(type="ping", t=0)
            dj_again.until(lambda m, _: m["type"] == "pong")
            assert dj_again.state["dj_key"] == dj_key


def test_transfer_and_kick(new_room, join, signup):
    room_id, token, _ = new_room()
    t2, _ = signup()
    with join(room_id, token=token) as dj, join(room_id, token=t2) as other, join(room_id) as pest:
        dj.send(type="kick", key=pest.key)
        pest.until(lambda m, _: m["type"] == "kicked")
        dj.until_state(lambda s: len(s["members"]) == 2)
        dj.send(type="transfer_dj", key=other.key)
        s = other.until_state(lambda s: s["dj_key"] == other.key)
        assert other.role(dj.key) == "codj"


# ---- chat & voteskip --------------------------------------------------------------------------

def test_chat_and_voteskip_majority(new_room, join):
    room_id, token, _ = new_room()
    with join(room_id, token=token) as dj, join(room_id) as a, join(room_id) as b:
        a.send(type="add", video_id="aaaaaaaaaaa")
        a.send(type="add", video_id="bbbbbbbbbbb")
        dj.until_state(lambda s: len(s["queue"]) == 2 and len(s["members"]) == 3)

        a.send(type="chat", text="this song slaps")
        b.until(lambda m, _: m["type"] == "chat" and m["message"]["text"] == "this song slaps")

        a.send(type="chat", text="nah /voteskip")
        s = b.until_state(lambda s: any(p["status"] == "open" for p in s["polls"].values()))
        poll = next(p for p in s["polls"].values() if p["status"] == "open")
        assert poll["yes"] == 1 and poll["eligible"] == 3 and poll["needed"] == 2
        assert any(m["kind"] == "poll" for m in b.chat)

        # 1 of 3 is not > 50%; a second yes (2/3) is.
        a.send(type="vote", poll_id=poll["id"], yes=True)
        assert "already voted" in a.until_error()
        b.send(type="vote", poll_id=poll["id"], yes=True)
        s = dj.until_state(lambda s: s["current"] == 1)
        assert s["polls"][poll["id"]]["status"] == "passed"


def test_voteskip_fails_when_majority_says_no_and_threshold_is_configurable(new_room, join):
    room_id, token, _ = new_room()
    with join(room_id, token=token) as dj, join(room_id) as a, join(room_id) as b:
        a.send(type="add", video_id="aaaaaaaaaaa")
        dj.until_state(lambda s: len(s["queue"]) == 1 and len(s["members"]) == 3)

        a.send(type="chat", text="/voteskip")
        s = dj.until_state(lambda s: any(p["status"] == "open" for p in s["polls"].values()))
        pid = next(iter(s["polls"]))
        dj.send(type="vote", poll_id=pid, yes=False)
        b.send(type="vote", poll_id=pid, yes=False)
        s = dj.until_state(lambda s: s["polls"][pid]["status"] == "failed")
        assert s["current"] == 0

        # Guests can't change the threshold; the DJ can. At 1%, a single vote skips.
        a.send(type="settings", skip_threshold=1)
        assert "co-DJ" in a.until_error()
        dj.send(type="settings", skip_threshold=1)
        dj.until_state(lambda s: s["settings"]["skip_threshold"] == 1)
        b.send(type="chat", text="/voteskip")
        s = dj.until_state(lambda s: len(s["queue"]) == 2 and s["current"] == 1)
        assert s["queue"][1]["added_by"] == "Suggestions"


def test_voteskip_with_nothing_playing(new_room, join):
    room_id, token, _ = new_room()
    with join(room_id, token=token) as dj:
        dj.send(type="chat", text="/voteskip")
        assert "Nothing is playing" in dj.until_error()


# ---- identity & room lifecycle ---------------------------------------------------------------

def test_guest_can_log_in_without_leaving(new_room, join, signup):
    room_id, token, _ = new_room()
    t2, user2 = signup()
    with join(room_id, token=token) as dj, join(room_id, name="Shy Guest") as guest:
        old_key = guest.key
        assert old_key.startswith("g:")
        guest.send(type="auth", token=t2)
        guest.until(lambda m, _: m["type"] == "identity")
        assert guest.you["user"]["username"] == user2["username"]
        s = dj.until_state(lambda s: any(m["key"] == f"u:{user2['id']}" for m in s["members"]))
        assert all(m["key"] != old_key for m in s["members"])
        # Now they can be promoted.
        dj.send(type="set_role", key=guest.key, role="codj")
        guest.until_state(lambda s: guest.role() == "codj")


def test_rename_guest(new_room, join):
    room_id, token, _ = new_room()
    with join(room_id, token=token) as dj, join(room_id, name="Guest") as g:
        g.send(type="rename", name="Disco Walrus")
        dj.until_state(lambda s: any(m["name"] == "Disco Walrus" for m in s["members"]))


def test_delete_room(client, new_room, join, signup):
    room_id, token, _ = new_room()
    with join(room_id, token=token) as dj, join(room_id) as guest:
        dj.send(type="delete_room")
        guest.until(lambda m, _: m["type"] == "room_deleted")
    assert client.get(f"/api/rooms/{room_id}").status_code == 404


def test_room_survives_restart(client, new_room, join):
    from app.main import rooms

    room_id, token, _ = new_room()
    with join(room_id, token=token) as dj:
        dj.send(type="add", video_id="aaaaaaaaaaa")
        dj.until_state(lambda s: len(s["queue"]) == 1)
    rooms.rooms[room_id].save_now()
    rooms.rooms.pop(room_id)  # simulate a restart
    with join(room_id, token=token) as dj:
        assert dj.role() == "dj"
        assert dj.state["queue"][0]["video_id"] == "aaaaaaaaaaa"


def test_unknown_room_socket(client):
    with client.websocket_connect("/ws/NOPENOPENOPE") as ws:
        assert ws.receive_json()["type"] == "not_found"


def test_dj_logging_out_hands_over_booth(new_room, join, signup):
    room_id, token, _ = new_room()
    t2, _ = signup()
    with join(room_id, token=token) as dj, join(room_id, token=t2) as other:
        dj.send(type="set_role", key=other.key, role="codj")
        other.until_state(lambda s: other.role() == "codj")
        dj.send(type="auth", token=None, client_id="abc123", name="Former DJ")
        dj.until(lambda m, _: m["type"] == "identity")
        s = other.until_state(lambda s: s["dj_key"] == other.key)
        assert any(m["name"] == "Former DJ" and m["role"] == "listener" for m in s["members"])


def test_guest_dj_keeps_booth_after_logging_in(new_room, join, signup):
    room_id, token, _ = new_room()
    t2, user2 = signup()
    with join(room_id) as guest:
        with join(room_id, token=token) as dj:
            dj.send(type="leave")
        guest.until_state(lambda s: s["dj_key"] == guest.key)
        guest.send(type="auth", token=t2)
        s = guest.until_state(lambda s: s["dj_key"] == f"u:{user2['id']}")
        assert guest.role() == "dj"


def test_player_error_needs_majority_of_tuned_listeners(new_room, join):
    room_id, token, _ = new_room()
    with join(room_id, token=token) as dj, join(room_id) as a, join(room_id) as b:
        for p in (dj, a, b):
            p.send(type="tuned")
        a.send(type="add", video_id="aaaaaaaaaaa")
        a.send(type="add", video_id="bbbbbbbbbbb")
        s = dj.until_state(lambda s: len(s["queue"]) == 2)
        uid = current(s)["uid"]
        a.send(type="player_error", uid=uid, code=150)
        a.until(lambda m, _: m["type"] == "toast" and "won't play in your browser" in m["text"])
        b.send(type="player_error", uid=uid, code=150)
        dj.until_state(lambda s: s["current"] == 1)


# ---- security ---------------------------------------------------------------------------------

def test_guest_key_does_not_reveal_client_id(new_room, join, client):
    room_id, token, _ = new_room()
    with join(room_id, token=token) as dj, client.websocket_connect(f"/ws/{room_id}") as ws:
        ws.send_json({"type": "join", "client_id": "victim-client-id", "name": "Victim"})
        hello = ws.receive_json()
        assert hello["type"] == "hello"
        assert "victim-client-id" not in hello["you"]["key"]
        s = dj.until_state(lambda s: any(m["name"] == "Victim" for m in s["members"]))
        assert all("victim-client-id" not in m["key"] for m in s["members"])


def test_socket_needs_join_message(new_room, client):
    room_id, token, _ = new_room()
    with client.websocket_connect(f"/ws/{room_id}?token={token}") as ws:
        ws.send_json({"type": "chat", "text": "hi"})
        with pytest.raises(Exception):
            ws.receive_json()


def test_session_tokens_are_hashed_at_rest(signup):
    from app import db

    token, user = signup()
    assert db.conn().execute("SELECT 1 FROM sessions WHERE token = ?", (token,)).fetchone() is None
    assert db.user_for_token(token)["id"] == user["id"]


def test_expired_sessions_are_rejected(signup, client, monkeypatch):
    from app import config

    token, _ = signup()
    monkeypatch.setattr(config, "SESSION_TTL_SECONDS", -1)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_login_is_rate_limited(signup, client):
    _, user = signup()
    for _ in range(10):
        r = client.post("/api/auth/login", json={"username": user["username"], "password": "wrong-pass"})
        assert r.status_code == 401
    r = client.post("/api/auth/login", json={"username": user["username"], "password": "secret123"})
    assert r.status_code == 429


def test_seek_rejects_non_finite_positions(new_room, join):
    room_id, token, _ = new_room()
    with join(room_id, token=token) as dj:
        dj.send(type="add", video_id="dQw4w9WgXcQ")
        dj.until_state(lambda s: s["current"] == 0)
        dj.ws.send_text('{"type": "seek", "position": NaN}')
        assert "valid position" in dj.until_error()


def test_lookalike_hosts_are_not_youtube():
    from app import music

    assert music.parse_youtube_url("https://evilyoutube.com/watch?v=dQw4w9WgXcQ") == (None, None)
    assert music.parse_youtube_url("https://music.youtube.com/watch?v=dQw4w9WgXcQ")[0] == "dQw4w9WgXcQ"
    assert music.parse_youtube_url("https://youtube.com/playlist?list=PL%26x%3Dy")[1] is None
