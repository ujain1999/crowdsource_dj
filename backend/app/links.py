"""Read songs out of links to other music services (Spotify, Apple Music, Tidal, ...).

Every room plays from YouTube, so a link from anywhere else is turned into plain song details
(title, artist, duration) here, and music.py finds each song on YouTube Music. Nothing needs an
account or API key: readers use the public pages, embeds and web APIs each service serves to
its own site and to link previews. That also means a reader can break when a service changes
its site; each one fails with a LinkError rather than a crash.

All functions here are blocking; callers run them with asyncio.to_thread.
"""

import html
import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import ParseResult, parse_qs, unquote, unquote_plus, urlparse

import httpx

from . import config

log = logging.getLogger(__name__)

TIMEOUT = 8
MAX_BYTES = 4_000_000
MAX_REDIRECTS = 5
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
# Amazon Music and Qobuz only put song details in the page for link previews (as in chat apps).
PREVIEW_UA = "Mozilla/5.0 (compatible; CrowdsourceDJ/1.0) facebookexternalhit/1.1"


class LinkError(Exception):
    """A music-service link we can't read. The message is shown to the person who pasted it."""


@dataclass
class Song:
    title: str
    artist: str = ""
    duration: int = 0  # seconds; 0 when the service doesn't say
    video_id: str | None = None  # set when the service itself links the song on YouTube


@dataclass
class Album:
    """An album to look up on YouTube Music, for services that don't list its songs."""
    title: str
    artist: str = ""


Found = list[Song] | Album


@dataclass(frozen=True)
class Service:
    name: str
    hosts: tuple[str, ...]  # a host matches itself and its subdomains
    read: Callable[[ParseResult], Found]


# ---- fetching -------------------------------------------------------------------------------

_client = httpx.Client(timeout=TIMEOUT, follow_redirects=False)


def _host_ok(host: str | None, hosts: tuple[str, ...]) -> bool:
    host = (host or "").lower()
    return any(host == h or host.endswith("." + h) for h in hosts)


def _get(url: str, hosts: tuple[str, ...], *, ua: str = BROWSER_UA, headers: dict | None = None,
         params: dict | None = None) -> tuple[str, str]:
    """GET a page, following redirects only within hosts. Returns (final URL, body)."""
    request = _client.build_request(
        "GET", url, params=params,
        headers={"User-Agent": ua, "Accept-Language": "en-US,en;q=0.8", **(headers or {})},
    )
    for _ in range(MAX_REDIRECTS + 1):
        if request.url.scheme != "https" or not _host_ok(request.url.host, hosts):
            raise LinkError("That link points somewhere we can't follow.")
        response = _client.send(request, stream=True)
        try:
            if response.next_request is not None:
                request = response.next_request
                continue
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                body += chunk
                if len(body) > MAX_BYTES:
                    raise LinkError("That page is too big to read.")
            return str(response.url), body.decode(response.encoding or "utf-8", errors="replace")
        finally:
            response.close()
    raise LinkError("That link redirects too many times.")


def _get_json(url: str, hosts: tuple[str, ...], **kw) -> dict:
    return json.loads(_get(url, hosts, **kw)[1])


# ---- page parsing helpers -------------------------------------------------------------------

def _meta(page: str, name: str) -> str:
    """Content of <meta property|name="name">, whichever order its attributes are in."""
    for tag in re.findall(r"<meta\b[^>]*>", page, re.I):
        if re.search(rf"""\b(?:property|name)\s*=\s*["']{re.escape(name)}["']""", tag, re.I):
            m = re.search(r'\bcontent\s*=\s*"([^"]*)"', tag) or re.search(r"\bcontent\s*=\s*'([^']*)'", tag)
            if m:
                return html.unescape(m.group(1)).strip()
    return ""


def _title_tag(page: str) -> str:
    m = re.search(r"<title[^>]*>([^<]*)</title>", page, re.I)
    return html.unescape(m.group(1)).strip() if m else ""


def _json_ld(page: str) -> list[dict]:
    """Top-level schema.org objects in the page's JSON-LD blocks, including those in @graph."""
    found: list[dict] = []

    def add(item):
        if isinstance(item, list):
            for x in item:
                add(x)
        elif isinstance(item, dict):
            found.append(item)
            add(item.get("@graph"))

    for block in re.findall(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", page, re.S | re.I):
        try:
            add(json.loads(block))
        except ValueError:
            continue
    return found


def _iso_duration(text) -> int:
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", str(text or ""))
    if not m:
        return 0
    h, mins, s = (int(g or 0) for g in m.groups())
    return h * 3600 + mins * 60 + s


def _ld_artist(obj: dict) -> str:
    by = obj.get("byArtist")
    people = by if isinstance(by, list) else [by]
    return ", ".join(p["name"] for p in people if isinstance(p, dict) and p.get("name"))


def _ld_song(obj: dict) -> Song:
    return Song(html.unescape(obj["name"]), html.unescape(_ld_artist(obj)), _iso_duration(obj.get("duration")))


def _ld_tracks(obj: dict) -> list[dict]:
    """The named songs of a schema.org album or playlist; `track` is a list or an ItemList."""
    tracks = obj.get("track") or []
    if isinstance(tracks, dict):
        tracks = [e.get("item", e) for e in tracks.get("itemListElement") or [] if isinstance(e, dict)]
    return [t for t in tracks if isinstance(t, dict) and t.get("name")] if isinstance(tracks, list) else []


def _ld_read(page: str) -> Found | None:
    """Songs from the first schema.org song, album or playlist on the page."""
    for obj in _json_ld(page):
        kind = obj.get("@type")
        if kind == "MusicRecording" and obj.get("name"):
            return [_ld_song(obj)]
        if kind in ("MusicAlbum", "MusicPlaylist"):
            songs = [_ld_song(t) for t in _ld_tracks(obj)]
            if songs:
                return songs
            if kind == "MusicAlbum" and obj.get("name"):
                return Album(html.unescape(obj["name"]), html.unescape(_ld_artist(obj)))
    return None


def _parts(url: ParseResult) -> list[str]:
    return [unquote(p) for p in url.path.split("/") if p]


def _slug_text(slug: str) -> str:
    """'never-gonna-give-you-up' -> 'never gonna give you up'."""
    return re.sub(r"[-_+\s]+", " ", unquote_plus(slug)).strip()


def _split_last(text: str, sep: str) -> tuple[str, str]:
    """For "Song by Artist": ('Stand by Me by Ben E. King', ' by ') -> ('Stand by Me', 'Ben E. King')."""
    head, found, tail = text.rpartition(sep)
    return (head.strip(), tail.strip()) if found else (text.strip(), "")


def _split_first(text: str, sep: str) -> tuple[str, str]:
    """For "Artist - Song": ('Queen - Bohemian Rhapsody - Remastered', ' - ') -> ('Queen', 'Bohemian Rhapsody - Remastered')."""
    head, found, tail = text.partition(sep)
    return (head.strip(), tail.strip()) if found else ("", text.strip())


def _need(value, what: str):
    if not value:
        raise LinkError(f"That doesn't look like a {what} link.")
    return value


# ---- Spotify --------------------------------------------------------------------------------

SPOTIFY_HOSTS = ("open.spotify.com", "play.spotify.com", "spotify.link", "spoti.fi", "spotify.app.link")
SPOTIFY_URL_RE = re.compile(r"open\.spotify\.com/(?:intl-[a-z-]+/)?(?:embed/)?(track|album|playlist)/([A-Za-z0-9]{22})")


def _spotify(url: ParseResult) -> Found:
    m = SPOTIFY_URL_RE.search(f"{url.hostname}{url.path}".replace("play.spotify.com", "open.spotify.com"))
    if not m and not (url.hostname or "").endswith("open.spotify.com"):
        # A short share link: follow it to the real page.
        final, page = _get(url.geturl(), SPOTIFY_HOSTS)
        m = SPOTIFY_URL_RE.search(final) or SPOTIFY_URL_RE.search(page)
    kind, item_id = _need(m, "Spotify song, album or playlist").groups()
    _, page = _get(f"https://open.spotify.com/embed/{kind}/{item_id}", SPOTIFY_HOSTS)
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', page, re.S)
    entity = json.loads(_need(m, "Spotify").group(1))["props"]["pageProps"]["state"]["data"]["entity"]
    if kind == "track":
        artists = ", ".join(a["name"] for a in entity.get("artists") or [] if a.get("name"))
        return [Song(entity.get("name") or entity["title"], artists, int(entity.get("duration") or 0) // 1000)]
    return [
        Song(t["title"], t.get("subtitle") or "", int(t.get("duration") or 0) // 1000)
        for t in entity.get("trackList") or [] if t.get("title")
    ]


# ---- Apple Music / iTunes -------------------------------------------------------------------

APPLE_HOSTS = ("music.apple.com", "itunes.apple.com")


def _itunes_lookup(ids: list[str], country: str, **extra) -> list[dict]:
    data = _get_json(
        "https://itunes.apple.com/lookup", APPLE_HOSTS,
        params={"id": ",".join(ids), "country": country, "limit": 200, **extra},
    )
    return [r for r in data.get("results") or [] if r.get("wrapperType") == "track" and r.get("trackName")]


def _itunes_song(r: dict) -> Song:
    return Song(r["trackName"], r.get("artistName") or "", int(r.get("trackTimeMillis") or 0) // 1000)


def _apple(url: ParseResult) -> Found:
    parts = _parts(url)
    country = parts[0].lower() if parts and re.fullmatch(r"[A-Za-z]{2}", parts[0]) else "us"
    kind = next((p for p in parts if p in ("album", "song", "playlist")), None)
    item_id = re.sub(r"^id", "", parts[-1]) if parts else ""
    song_id = parse_qs(url.query).get("i", [None])[0] or (item_id if kind == "song" else None)

    if song_id and song_id.isdigit():
        return [_itunes_song(r) for r in _itunes_lookup([song_id], country)]
    if kind == "album" and item_id.isdigit():
        return [_itunes_song(r) for r in _itunes_lookup([item_id], country, entity="song")]
    if kind == "playlist" and re.fullmatch(r"pl\.[A-Za-z0-9.-]+", item_id):
        _, page = _get(f"https://music.apple.com/{country}/playlist/-/{item_id}", APPLE_HOSTS)
        playlist = next((o for o in _json_ld(page) if o.get("@type") == "MusicPlaylist"), {})
        tracks = _ld_tracks(playlist)[: config.MAX_PLAYLIST_ITEMS]
        ids = []
        for t in tracks:
            m = re.search(r"/song/[^/]+/(\d+)|[?&]i=(\d+)", t.get("url") or "")
            ids.append((m.group(1) or m.group(2)) if m else None)
        # The page names each song but not its artist; the lookup API has both.
        by_id = {str(r["trackId"]): r for r in _itunes_lookup([i for i in ids if i], country)} if any(ids) else {}
        return [
            _itunes_song(by_id[i]) if i in by_id else Song(t["name"], "", _iso_duration(t.get("duration")))
            for i, t in zip(ids, tracks)
        ]
    raise LinkError("That Apple Music link isn't a song, album or playlist.")


# ---- Amazon Music ---------------------------------------------------------------------------

AMAZON_HOSTS = tuple(
    f"music.amazon.{tld}"
    for tld in ("com", "ca", "com.mx", "com.br", "co.uk", "de", "fr", "it", "es", "in", "co.jp", "com.au")
)
ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")


def _amazon(url: ParseResult) -> Found:
    parts = _parts(url)
    base = f"https://{url.hostname}"
    track = parse_qs(url.query).get("trackAsin", [None])[0]
    if not track and len(parts) >= 2 and parts[0] == "tracks":
        track = parts[1]
    if track and ASIN_RE.match(track):
        _, page = _get(f"{base}/tracks/{track}", AMAZON_HOSTS, ua=PREVIEW_UA)
        title = _meta(page, "og:title")
        if not title or title == "Amazon Music":
            raise LinkError("Couldn't read that Amazon Music song. Is it available in your country?")
        # The song page doesn't name the artist; its album page does ("Album – Artist").
        artist = ""
        album_url = _meta(page, "music:album")
        if album_url:
            try:
                _, album_page = _get(album_url, AMAZON_HOSTS, ua=PREVIEW_UA)
                artist = _split_last(_meta(album_page, "og:title"), " – ")[1]
            except (httpx.HTTPError, LinkError):
                log.info("no artist for Amazon track %s", track)
        if artist and title.endswith(f" – {artist}"):  # some Amazon sites add the artist
            title = title.removesuffix(f" – {artist}")
        duration = _meta(page, "music:duration")
        return [Song(title, artist, int(duration) if duration.isdigit() else 0)]
    if len(parts) >= 2 and parts[0] == "albums" and ASIN_RE.match(parts[1]):
        _, page = _get(f"{base}/albums/{parts[1]}", AMAZON_HOSTS, ua=PREVIEW_UA)
        title, artist = _split_last(_meta(page, "og:title"), " – ")
        if not title or title == "Amazon Music":
            raise LinkError("Couldn't read that Amazon Music album. Is it available in your country?")
        return Album(title, artist)
    if parts and parts[0] in ("playlists", "user-playlists", "stations"):
        raise LinkError("Amazon Music playlists can't be read without signing in. Paste a song or album instead.")
    raise LinkError("That Amazon Music link isn't a song or album.")


# ---- Tidal ----------------------------------------------------------------------------------

TIDAL_HOSTS = ("tidal.com",)
# The public token TIDAL's own web embeds use for catalog lookups.
TIDAL_TOKEN = "CzET4vdadNUFQ5JU"


def _tidal(url: ParseResult) -> Found:
    parts = [p for p in _parts(url) if p != "browse"]
    kind = {"tracks": "track", "albums": "album", "playlists": "playlist"}.get(parts[0], parts[0]) if parts else ""
    item_id = parts[1] if len(parts) >= 2 else ""
    if kind == "track" and item_id.isdigit():
        _, page = _get(f"https://tidal.com/track/{item_id}", TIDAL_HOSTS)
        found = _ld_read(page)
        if found:
            return found
        # og:title is "Artist - Song".
        artist, title = _split_first(_meta(page, "og:title"), " - ")
        if title:
            return [Song(title, artist)]
        raise LinkError("Couldn't read that TIDAL song. Is it available in your country?")
    if (kind == "album" and item_id.isdigit()) or (kind == "playlist" and re.fullmatch(r"[0-9a-f-]{36}", item_id)):
        try:
            data = _get_json(
                f"https://api.tidal.com/v1/{kind}s/{item_id}/items", TIDAL_HOSTS,
                headers={"x-tidal-token": TIDAL_TOKEN},
                params={"countryCode": "US", "limit": config.MAX_PLAYLIST_ITEMS},
            )
            songs = []
            for entry in data.get("items") or []:
                t = entry.get("item") or {}
                if entry.get("type", "track") == "track" and t.get("title"):
                    artists = ", ".join(a["name"] for a in t.get("artists") or [] if a.get("name"))
                    songs.append(Song(t["title"], artists, int(t.get("duration") or 0)))
            if songs:
                return songs
        except (httpx.HTTPError, ValueError):
            log.warning("TIDAL API couldn't list %s %s", kind, item_id)
        if kind == "album":
            _, page = _get(f"https://tidal.com/album/{item_id}", TIDAL_HOSTS)
            found = _ld_read(page)
            if found:
                return found
        raise LinkError(f"Couldn't read that TIDAL {kind}. Is it public?")
    raise LinkError("That TIDAL link isn't a song, album or playlist.")


# ---- Qobuz ----------------------------------------------------------------------------------

QOBUZ_HOSTS = ("qobuz.com",)
# The public app id open.qobuz.com uses; it can read playlists without signing in.
QOBUZ_APP_ID = "712109809"


def _qobuz(url: ParseResult) -> Found:
    parts = _parts(url)
    kind = next((p for p in parts if p in ("track", "album", "playlist")), None)
    item_id = parts[-1] if parts else ""
    if not re.fullmatch(r"[A-Za-z0-9]+", item_id):
        kind = None
    if kind == "track":
        # Songs have no public page, but their share link has a preview: "Song by Artist is on Qobuz.com".
        _, page = _get(f"https://open.qobuz.com/track/{item_id}", QOBUZ_HOSTS, ua=PREVIEW_UA)
        m = re.fullmatch(r"(.*) is on Qobuz\.com", _meta(page, "og:title"))
        if not m:
            raise LinkError("Couldn't read that Qobuz song.")
        return [Song(*_split_last(m.group(1), " by "))]
    if kind == "album":
        _, page = _get(f"https://www.qobuz.com/us-en/album/-/{item_id}", QOBUZ_HOSTS)
        songs = []
        for raw in re.findall(r'data-track-v2="([^"]*)"', page):
            try:
                t = json.loads(html.unescape(raw))
            except ValueError:
                continue
            if t.get("item_name"):
                songs.append(Song(t["item_name"], t.get("item_brand") or ""))
        return songs or _need(_ld_read(page), "Qobuz album")
    if kind == "playlist" and item_id.isdigit():
        data = _get_json(
            "https://www.qobuz.com/api.json/0.2/playlist/get", QOBUZ_HOSTS,
            params={"playlist_id": item_id, "extra": "tracks", "limit": config.MAX_PLAYLIST_ITEMS, "app_id": QOBUZ_APP_ID},
        )
        return [
            Song(t["title"], (t.get("performer") or {}).get("name") or "", int(t.get("duration") or 0))
            for t in (data.get("tracks") or {}).get("items") or [] if t.get("title")
        ]
    raise LinkError("That Qobuz link isn't a song, album or playlist.")


# ---- JioSaavn -------------------------------------------------------------------------------

SAAVN_HOSTS = ("jiosaavn.com", "saavn.com")


def _saavn_song(s: dict) -> Song:
    info = s.get("more_info") or {}
    artists = ((info.get("artistMap") or {}).get("primary_artists")) or []
    artist = ", ".join(a["name"] for a in artists if a.get("name")) or s.get("subtitle") or ""
    duration = str(info.get("duration") or "")
    return Song(html.unescape(s["title"]), html.unescape(artist), int(duration) if duration.isdigit() else 0)


def _saavn(url: ParseResult) -> Found:
    parts = _parts(url)
    kind = {"song": "song", "album": "album", "featured": "playlist", "playlist": "playlist"}.get(
        next((p for p in parts if p in ("song", "album", "featured", "playlist")), ""))
    token = parts[-1] if parts else ""
    if not kind or not re.fullmatch(r"[A-Za-z0-9_,-]+", token):
        raise LinkError("That JioSaavn link isn't a song, album or playlist.")
    data = _get_json(
        "https://www.jiosaavn.com/api.php", SAAVN_HOSTS,
        params={
            "__call": "webapi.get", "token": token, "type": kind, "n": config.MAX_PLAYLIST_ITEMS, "p": 1,
            "includeMetaTags": 0, "ctx": "web6dot0", "api_version": 4, "_format": "json", "_marker": 0,
        },
    )
    items = data.get("songs") if kind == "song" else data.get("list")
    return [_saavn_song(s) for s in items or [] if isinstance(s, dict) and s.get("title")]


# ---- Gaana ----------------------------------------------------------------------------------

GAANA_HOSTS = ("gaana.com",)


def _gaana(url: ParseResult) -> Found:
    parts = _parts(url)
    if len(parts) < 2 or parts[0] not in ("song", "album", "playlist"):
        raise LinkError("That Gaana link isn't a song, album or playlist.")
    _, page = _get(f"https://gaana.com/{parts[0]}/{parts[1]}", GAANA_HOSTS)
    return _need(_ld_read(page), f"Gaana {parts[0]}")


# ---- Wynk -----------------------------------------------------------------------------------

WYNK_HOSTS = ("wynk.in",)


def _wynk(url: ParseResult) -> Found:
    # Wynk's pages and catalog no longer return song details, so go by the name in the link.
    parts = _parts(url)
    if len(parts) >= 3 and parts[:2] == ["music", "song"]:
        return [Song(_slug_text(parts[2]))]
    raise LinkError("Only Wynk song links can be read. Search for the album or playlist's songs instead.")


# ---- Genius ---------------------------------------------------------------------------------

GENIUS_HOSTS = ("genius.com",)
YOUTUBE_ID_RE = re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})")


def _genius(url: ParseResult) -> Found:
    parts = _parts(url)
    if len(parts) == 3 and parts[0] == "albums":
        _, page = _get(f"https://genius.com/albums/{parts[1]}/{parts[2]}", GENIUS_HOSTS)
        title, artist = _split_last(_meta(page, "og:title"), " by ")
        return Album(title or _slug_text(parts[2]), artist or _slug_text(parts[1]))
    if len(parts) == 1 and parts[0].endswith("-lyrics"):
        _, page = _get(f"https://genius.com/{parts[0]}", GENIUS_HOSTS)
        m = re.search(r"genius://songs/(\d+)", page)
        if m:
            try:
                song = _get_json(f"https://genius.com/api/songs/{m.group(1)}", GENIUS_HOSTS)["response"]["song"]
                video = next((YOUTUBE_ID_RE.search(x.get("url") or "") for x in song.get("media") or []
                              if x.get("provider") == "youtube"), None)
                return [Song(song["title"], (song.get("primary_artist") or {}).get("name") or "",
                             video_id=video.group(1) if video else None)]
            except (httpx.HTTPError, ValueError, KeyError):
                log.info("Genius API couldn't read song %s", m.group(1))
        # og:title is "Artist – Song".
        artist, title = _split_first(_meta(page, "og:title"), " – ")
        if not title:
            raise LinkError("Couldn't read that Genius song.")
        return [Song(title, artist)]
    raise LinkError("That Genius link isn't a song or album.")


# ---- AZLyrics -------------------------------------------------------------------------------

AZLYRICS_HOSTS = ("azlyrics.com",)


def _azlyrics(url: ParseResult) -> Found:
    parts = _parts(url)
    if len(parts) != 3 or parts[0] != "lyrics" or not parts[2].endswith(".html"):
        raise LinkError("That AZLyrics link isn't a song.")
    artist_slug, song_slug = parts[1], parts[2].removesuffix(".html")
    try:
        _, page = _get(f"https://www.azlyrics.com/lyrics/{artist_slug}/{song_slug}.html", AZLYRICS_HOSTS)
        # The title is "Artist - Song Lyrics | AZLyrics.com".
        m = re.fullmatch(r"(.+?) - (.+) Lyrics \| AZLyrics(?:\.com)?", _title_tag(page))
        if m:
            return [Song(m.group(2), m.group(1))]
    except (httpx.HTTPError, LinkError):
        log.info("AZLyrics page unavailable for %s/%s", artist_slug, song_slug)
    # AZLyrics often turns away servers. Its links squash names ("rickastley"), which search still copes with.
    return [Song(song_slug, artist_slug)]


# ---- Last.fm --------------------------------------------------------------------------------

LASTFM_HOSTS = ("last.fm", "lastfm.de", "lastfm.es", "lastfm.fr", "lastfm.it", "lastfm.jp", "lastfm.pl",
                "lastfm.com.br", "lastfm.ru", "lastfm.se", "lastfm.com.tr")


def _lastfm(url: ParseResult) -> Found:
    # Last.fm puts names in its links: /music/Artist/_/Song and /music/Artist/Album.
    parts = [unquote_plus(p) for p in url.path.split("/") if p and p != "+noredirect"]
    if "music" in parts:
        parts = parts[parts.index("music") + 1:]
        if len(parts) >= 3 and parts[1] == "_":
            return [Song(parts[2], parts[0])]
        if len(parts) >= 2 and not parts[1].startswith("+"):
            return Album(parts[1], parts[0])
    raise LinkError("That Last.fm link isn't a song or album.")


# ---- Musixmatch -----------------------------------------------------------------------------

MUSIXMATCH_HOSTS = ("musixmatch.com",)


def _musixmatch(url: ParseResult) -> Found:
    # Musixmatch's pages need a browser, but its links carry the names: /lyrics/Artist/Song.
    parts = _parts(url)
    for kind in ("lyrics", "album"):
        if kind in parts:
            rest = parts[parts.index(kind) + 1:]
            if len(rest) >= 2:
                artist, title = _slug_text(rest[0]), _slug_text(rest[1])
                return [Song(title, artist)] if kind == "lyrics" else Album(title, artist)
    raise LinkError("That Musixmatch link isn't a song or album.")


# ---- public API -----------------------------------------------------------------------------

SERVICES = (
    Service("Spotify", SPOTIFY_HOSTS, _spotify),
    Service("Apple Music", APPLE_HOSTS, _apple),
    Service("Amazon Music", AMAZON_HOSTS, _amazon),
    Service("TIDAL", TIDAL_HOSTS, _tidal),
    Service("Qobuz", QOBUZ_HOSTS, _qobuz),
    Service("JioSaavn", SAAVN_HOSTS, _saavn),
    Service("Gaana", GAANA_HOSTS, _gaana),
    Service("Wynk", WYNK_HOSTS, _wynk),
    Service("Genius", GENIUS_HOSTS, _genius),
    Service("AZLyrics", AZLYRICS_HOSTS, _azlyrics),
    Service("Last.fm", LASTFM_HOSTS, _lastfm),
    Service("Musixmatch", MUSIXMATCH_HOSTS, _musixmatch),
)


def _parse(text: str) -> tuple[Service, ParseResult] | None:
    text = (text or "").strip()
    m = re.fullmatch(r"spotify:(track|album|playlist):([A-Za-z0-9]{22})", text)
    if m:
        text = f"https://open.spotify.com/{m.group(1)}/{m.group(2)}"
    if not re.match(r"^https?://", text, re.I):
        if re.search(r"\s", text) or "/" not in text:
            return None
        text = "https://" + text
    try:
        url = urlparse(text)
        host = url.hostname
    except ValueError:
        return None
    for service in SERVICES:
        if _host_ok(host, service.hosts):
            return service, url._replace(scheme="https")
    return None


def service_name(text: str) -> str | None:
    """The music service a link is from, or None if we don't read links from it."""
    found = _parse(text)
    return found[0].name if found else None


def read(text: str) -> Found:
    """The songs (or album) a music-service link points at. Raises LinkError if it can't."""
    found = _parse(text)
    if not found:
        raise LinkError("That isn't a link we can read.")
    service, url = found
    try:
        result = service.read(url)
    except LinkError:
        raise
    except Exception as e:  # network trouble, or a page that's changed shape
        log.warning("couldn't read %s link %s: %r", service.name, url.geturl(), e)
        raise LinkError(f"Couldn't read that {service.name} link. Is it public?") from None
    if isinstance(result, list):
        result = [s for s in result if s.title.strip()][: config.MAX_PLAYLIST_ITEMS]
        if not result:
            raise LinkError(f"That {service.name} link has no songs we can read.")
    return result
