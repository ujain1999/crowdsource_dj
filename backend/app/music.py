"""Song lookup: search and radio via ytmusicapi, URL/playlist resolution via yt_dlp.

Links from other music services are read by links.py and matched to songs on YouTube Music.

All functions here are blocking; callers run them with asyncio.to_thread.
A track is a plain dict:
    {video_id, title, artist, album, duration, thumb}
"""

import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from urllib.parse import parse_qs, urlparse

from . import config, links

log = logging.getLogger(__name__)

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
PLAYLIST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{2,64}$")
YOUTUBE_HOSTS = ("youtube.com", "youtu.be", "youtube-nocookie.com")
# Songs from other services' playlists are looked up on YouTube Music this many at a time,
# across every room, so a burst of pasted playlists can't flood YouTube.
MATCH_WORKERS = 8
_match_pool = ThreadPoolExecutor(max_workers=MATCH_WORKERS, thread_name_prefix="match")
# Reading a link waits on those lookups, so it runs here rather than in asyncio's default
# executor, which search, radio and joins share.
link_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="link")
# Versions people rarely mean unless they asked for them.
ALT_VERSION_WORDS = {"karaoke", "cover", "instrumental", "remix", "live", "slowed", "reverb", "sped", "8d", "lofi"}

_cache: dict[str, dict] = {}
_cache_lock = threading.Lock()
_ytmusic = None


def _yt():
    global _ytmusic
    if _ytmusic is None:
        from ytmusicapi import YTMusic

        _ytmusic = YTMusic()
    return _ytmusic


def remember(track: dict) -> dict:
    with _cache_lock:
        _cache[track["video_id"]] = track
    return track


def cached(video_id: str) -> dict | None:
    with _cache_lock:
        return _cache.get(video_id)


def big_thumb(url: str | None, video_id: str) -> str:
    """Return a large square-ish artwork URL, suitable for the record label."""
    if url and "googleusercontent.com" in url:
        return re.sub(r"=w\d+-h\d+.*$", "=w544-h544-l90-rj", url)
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def _parse_duration(text: str | None) -> int:
    if not text:
        return 0
    total = 0
    for part in text.split(":"):
        if not part.isdigit():
            return 0
        total = total * 60 + int(part)
    return total


def _artists(item: dict) -> str:
    names = [a["name"] for a in item.get("artists") or [] if a.get("name")]
    return ", ".join(names)


def _from_ytmusic(item: dict) -> dict | None:
    video_id = item.get("videoId")
    if not video_id:
        return None
    thumbs = item.get("thumbnails") or item.get("thumbnail") or []
    album = item.get("album")
    return remember({
        "video_id": video_id,
        "title": item.get("title") or "Untitled",
        "artist": _artists(item),
        "album": album.get("name") if isinstance(album, dict) else None,
        "duration": item.get("duration_seconds") or _parse_duration(item.get("duration") or item.get("length")),
        "thumb": big_thumb(thumbs[-1]["url"] if thumbs else None, video_id),
    })


# ---- offline fakes (tests) ---------------------------------------------------

def _fake(n: int, prefix: str = "Fake") -> dict:
    vid = f"{prefix[:4]}{n:07d}".ljust(11, "x")[:11]
    return remember({
        "video_id": vid,
        "title": f"{prefix} Song {n}",
        "artist": "Test Band",
        "album": None,
        "duration": 180,
        "thumb": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
    })


# ---- public API ---------------------------------------------------------------

def search(query: str, limit: int = 12) -> list[dict]:
    query = (query or "").strip()[: config.MAX_SEARCH_LENGTH]
    if not query:
        return []
    if config.OFFLINE_MUSIC:
        return [_fake(i, "Srch") for i in range(1, 6)]
    try:
        results = _yt().search(query, filter="songs", limit=limit)
        tracks = [t for t in (_from_ytmusic(r) for r in results) if t]
        if tracks:
            return tracks[:limit]
    except Exception:
        log.exception("ytmusic search failed, falling back to yt_dlp")
    return _ytdlp_search(query, limit)


def _ytdlp_search(query: str, limit: int) -> list[dict]:
    import yt_dlp

    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "extract_flat": "in_playlist"}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
    return [t for t in (_from_ytdlp(e) for e in info.get("entries") or []) if t]


def _from_ytdlp(entry: dict) -> dict | None:
    video_id = entry.get("id")
    if not video_id or not VIDEO_ID_RE.match(video_id):
        return None
    return remember({
        "video_id": video_id,
        "title": entry.get("track") or entry.get("title") or "Untitled",
        "artist": entry.get("artist") or entry.get("channel") or entry.get("uploader") or "",
        "album": entry.get("album"),
        "duration": int(entry.get("duration") or 0),
        "thumb": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
    })


def parse_youtube_url(text: str) -> tuple[str | None, str | None]:
    """Return (video_id, playlist_id) found in a YouTube / YouTube Music URL."""
    text = (text or "").strip()
    if VIDEO_ID_RE.match(text):
        return text, None
    if not re.match(r"^https?://", text):
        text = "https://" + text
    url = urlparse(text)
    host = (url.hostname or "").lower()
    if not any(host == h or host.endswith("." + h) for h in YOUTUBE_HOSTS):
        return None, None
    qs = parse_qs(url.query)
    playlist = qs.get("list", [None])[0]
    if playlist and not PLAYLIST_ID_RE.match(playlist):
        playlist = None
    video = None
    if host.endswith("youtu.be"):
        video = url.path.strip("/").split("/")[0]
    elif "v" in qs:
        video = qs["v"][0]
    else:
        m = re.match(r"^/(?:shorts|embed|live|v)/([A-Za-z0-9_-]{11})", url.path)
        video = m.group(1) if m else None
    if video and not VIDEO_ID_RE.match(video):
        video = None
    return video, playlist


def looks_like_url(text: str) -> bool:
    """A YouTube link, or a link from another service links.py can read."""
    text = (text or "").strip()
    return bool(re.search(r"(^|[/.])(youtube\.com|youtu\.be|youtube-nocookie\.com)/", text)) or bool(links.service_name(text))


def get_track(video_id: str) -> dict | None:
    if not VIDEO_ID_RE.match(video_id or ""):
        return None
    hit = cached(video_id)
    if hit:
        return hit
    if config.OFFLINE_MUSIC:
        return remember({
            "video_id": video_id, "title": f"Track {video_id}", "artist": "Offline",
            "album": None, "duration": 180, "thumb": big_thumb(None, video_id),
        })
    try:
        details = _yt().get_song(video_id).get("videoDetails") or {}
        if details.get("videoId"):
            thumbs = (details.get("thumbnail") or {}).get("thumbnails") or []
            return remember({
                "video_id": video_id,
                "title": details.get("title") or "Untitled",
                "artist": details.get("author") or "",
                "album": None,
                "duration": int(details.get("lengthSeconds") or 0),
                "thumb": big_thumb(thumbs[-1]["url"] if thumbs else None, video_id),
            })
    except Exception:
        log.exception("ytmusic get_song failed for %s, trying yt_dlp", video_id)
    return _ytdlp_video(video_id)


def _ytdlp_video(video_id: str) -> dict | None:
    import yt_dlp

    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
    except Exception:
        log.exception("yt_dlp could not resolve %s", video_id)
        return None
    return _from_ytdlp(info)


def resolve(text: str) -> tuple[list[dict], int]:
    """Turn a pasted link into tracks: (tracks, songs we couldn't find on YouTube).

    Takes YouTube videos and playlists, and links.py's services. Raises links.LinkError with a
    message for the person when a music-service link can't be read.
    """
    video_id, playlist_id = parse_youtube_url(text)
    if video_id or playlist_id:
        return _resolve_youtube(video_id, playlist_id), 0
    if not links.service_name(text):
        return [], 0
    if config.OFFLINE_MUSIC:
        return [_fake(i, "Link") for i in range(1, 3)], 0
    found = links.read(text)
    if isinstance(found, links.Album):
        tracks = find_album(found)
        if not tracks:
            raise links.LinkError(f"Couldn't find “{found.title}” on YouTube Music.")
        return tracks, 0
    matches = list(_match_pool.map(find_song, found))
    tracks = [t for t in matches if t]
    return tracks, len(found) - len(tracks)


def _resolve_youtube(video_id: str | None, playlist_id: str | None) -> list[dict]:
    """A YouTube video or playlist as tracks. Uses yt_dlp for playlists."""
    if video_id:
        track = get_track(video_id)
        return [track] if track else []
    if playlist_id:
        if config.OFFLINE_MUSIC:
            return [_fake(i, "Plst") for i in range(1, 4)]
        import yt_dlp

        opts = {
            "quiet": True, "no_warnings": True, "skip_download": True,
            "extract_flat": "in_playlist", "playlistend": config.MAX_PLAYLIST_ITEMS,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/playlist?list={playlist_id}", download=False)
            tracks = [t for t in (_from_ytdlp(e) for e in list(info.get("entries") or [])[:config.MAX_PLAYLIST_ITEMS]) if t]
            if tracks:
                return tracks
        except Exception as e:
            log.warning("yt_dlp could not resolve playlist %s (%s); trying YouTube Music", playlist_id, e)
        try:
            playlist = _yt().get_playlist(playlist_id, limit=config.MAX_PLAYLIST_ITEMS)
            return [t for t in (_from_ytmusic(i) for i in playlist.get("tracks") or []) if t][:config.MAX_PLAYLIST_ITEMS]
        except Exception:
            log.exception("could not resolve playlist %s", playlist_id)
            return []
    return []


# ---- matching songs from other services ------------------------------------------------------

def _words(text: str) -> set[str]:
    return set(re.findall(r"\w+", (text or "").lower()))


def _overlap(want: set[str], got: set[str]) -> float:
    """How much of what we're looking for is there, 0..1."""
    return len(want & got) / len(want) if want else 0.0


def _squashed(text: str) -> str:
    return re.sub(r"\W+", "", (text or "").lower())


def _core(title: str) -> str:
    """A title without its extras: 'BURN (feat. Ava Max) - Remix' -> 'BURN'."""
    title = re.split(r"\s+[-–]\s+|\s*[(\[]|\s+(?:feat\.?|ft\.?|featuring)\s", title or "", maxsplit=1, flags=re.I)[0]
    return title.strip() or (title or "")


def _similar(want: str, got: str) -> float:
    """How alike two names are, 0..1. Copes with names squashed together ("rickastley") and
    spelled a little differently ("Vighnahartha", "Vighnaharta")."""
    words = _overlap(_words(want), _words(got))
    a, b = _squashed(want), _squashed(got)
    if min(len(a), len(b)) < 4:
        return words
    # "lovestory" starts "Love Story (Taylor's Version)", but "up" doesn't count for "nevergonnagiveyouup".
    if min(len(a), len(b)) >= 6 and (a.startswith(b) or b.startswith(a)):
        return 1.0
    spelling = SequenceMatcher(None, a, b).ratio()
    return max(words, spelling if spelling >= 0.85 else 0.0)


def _title_similar(want: str, got: str) -> float:
    return max(_similar(want, got), _similar(_core(want), _core(got)))


def _match_score(song: links.Song, track: dict) -> float:
    title = _title_similar(song.title, track["title"])
    artist = _similar(song.artist, track["artist"]) if song.artist else 0.5
    score = 2 * title + artist
    if song.duration and track["duration"]:
        score -= min(abs(song.duration - track["duration"]) / 30, 1)
    score -= len((_words(track["title"]) & ALT_VERSION_WORDS) - _words(song.title))
    return score


def find_song(song: links.Song) -> dict | None:
    """The best YouTube match for a song from another service, or None. Never raises."""
    try:
        if song.video_id:
            track = get_track(song.video_id)
            if track:
                return track
        candidates = search(f"{song.title} {song.artist}", limit=5)
        best = max(candidates, key=lambda t: _match_score(song, t), default=None)
        if not best:
            return None
        # Better to skip a song than queue a stranger. The title has to match: closely, or in
        # part alongside the artist (services credit artists differently, and titles carry
        # extras like "From the film").
        title = _title_similar(song.title, best["title"])
        artist = _similar(song.artist, best["artist"]) if song.artist else 0.0
        if title >= 0.75 or (title >= 0.5 and (not song.artist or artist > 0)) or (title >= 0.3 and artist >= 0.5):
            return best
        return None
    except Exception:
        log.exception("couldn't match %r by %r", song.title, song.artist)
        return None


def find_album(album: links.Album) -> list[dict]:
    """An album's tracks, found on YouTube Music by name."""
    try:
        results = _yt().search(f"{album.title} {album.artist}".strip()[: config.MAX_SEARCH_LENGTH], filter="albums", limit=5)
        want_title, want_artist = _words(album.title), _words(album.artist)

        def score(r: dict) -> float:
            return 2 * _overlap(want_title, _words(r.get("title"))) + _overlap(want_artist, _words(_artists(r)))

        best = max((r for r in results[:5] if r.get("browseId")), key=score, default=None)
        if not best or not _overlap(want_title, _words(best.get("title"))):
            return []
        data = _yt().get_album(best["browseId"])
    except Exception:
        log.exception("album lookup failed for %r by %r", album.title, album.artist)
        return []
    tracks = []
    for t in (data.get("tracks") or [])[: config.MAX_PLAYLIST_ITEMS]:
        # Album tracks share the album's artwork and name.
        item = {**t, "thumbnails": t.get("thumbnails") or data.get("thumbnails") or [], "album": {"name": data.get("title")}}
        track = _from_ytmusic(item)
        if track:
            tracks.append(track)
    return tracks


def radio(video_id: str, limit: int = 25) -> list[dict]:
    """Songs similar to video_id, from YouTube Music's free 'radio' mix."""
    if not VIDEO_ID_RE.match(video_id or ""):
        return []
    if config.OFFLINE_MUSIC:
        base = sum(map(ord, video_id)) % 1000
        return [_fake(base * 100 + i, "Radi") for i in range(1, limit + 1)]
    try:
        watch = _yt().get_watch_playlist(videoId=video_id, radio=True, limit=limit)
    except Exception:
        log.exception("radio lookup failed for %s", video_id)
        return []
    tracks = [_from_ytmusic(t) for t in watch.get("tracks") or []]
    return [t for t in tracks if t and t["video_id"] != video_id]
