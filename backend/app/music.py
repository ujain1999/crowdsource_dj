"""Song lookup: search and radio via ytmusicapi, URL/playlist resolution via yt_dlp.

All functions here are blocking; callers run them with asyncio.to_thread.
A track is a plain dict:
    {video_id, title, artist, album, duration, thumb}
"""

import logging
import re
import threading
from urllib.parse import parse_qs, urlparse

from . import config

log = logging.getLogger(__name__)

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
PLAYLIST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{2,64}$")
YOUTUBE_HOSTS = ("youtube.com", "youtu.be", "youtube-nocookie.com")
MAX_PLAYLIST_ITEMS = 50

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
    return bool(re.search(r"(^|[/.])(youtube\.com|youtu\.be|youtube-nocookie\.com)/", (text or "").strip()))


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


def resolve(text: str) -> list[dict]:
    """Turn a pasted URL (video or playlist) into tracks. Uses yt_dlp for playlists."""
    video_id, playlist_id = parse_youtube_url(text)
    if video_id:
        track = get_track(video_id)
        return [track] if track else []
    if playlist_id:
        if config.OFFLINE_MUSIC:
            return [_fake(i, "Plst") for i in range(1, 4)]
        import yt_dlp

        opts = {
            "quiet": True, "no_warnings": True, "skip_download": True,
            "extract_flat": "in_playlist", "playlistend": MAX_PLAYLIST_ITEMS,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/playlist?list={playlist_id}", download=False)
            tracks = [t for t in (_from_ytdlp(e) for e in list(info.get("entries") or [])[:MAX_PLAYLIST_ITEMS]) if t]
            if tracks:
                return tracks
        except Exception as e:
            log.warning("yt_dlp could not resolve playlist %s (%s); trying YouTube Music", playlist_id, e)
        try:
            playlist = _yt().get_playlist(playlist_id, limit=MAX_PLAYLIST_ITEMS)
            return [t for t in (_from_ytmusic(i) for i in playlist.get("tracks") or []) if t][:MAX_PLAYLIST_ITEMS]
        except Exception:
            log.exception("could not resolve playlist %s", playlist_id)
            return []
    return []


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
