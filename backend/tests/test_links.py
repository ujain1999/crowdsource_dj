"""Reading songs out of other music services' links. Pages are canned; nothing goes online."""

import json

import pytest

from app import links, music
from app.links import Album, LinkError, Song


@pytest.fixture
def pages(monkeypatch):
    """Serve canned pages to the readers: pages[url_prefix] = body (str, or dict for JSON)."""
    served: dict[str, str | dict] = {}

    def fake_get(url, hosts, *, ua=links.BROWSER_UA, headers=None, params=None):
        for prefix, body in served.items():
            if url.startswith(prefix):
                assert links._host_ok(url.split("/")[2], hosts)
                return url, json.dumps(body) if isinstance(body, dict) else body
        raise LinkError(f"no canned page for {url}")

    monkeypatch.setattr(links, "_get", fake_get)
    return served


def ld(obj) -> str:
    return f'<script type="application/ld+json">{json.dumps(obj)}</script>'


def test_recognises_services_and_ignores_everything_else():
    cases = {
        "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT?si=x": "Spotify",
        "open.spotify.com/intl-de/album/6N9PS4QXF1D0OWPk0Sxtb4": "Spotify",
        "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M": "Spotify",
        "https://music.apple.com/us/album/x/1559885420?i=1559885421": "Apple Music",
        "https://itunes.apple.com/us/album/x/id1559885420": "Apple Music",
        "https://music.amazon.co.uk/tracks/B079LLJCJK": "Amazon Music",
        "https://listen.tidal.com/album/491206011": "TIDAL",
        "https://open.qobuz.com/track/30369643": "Qobuz",
        "https://www.jiosaavn.com/song/kesariya/AgIAQyBeWlI": "JioSaavn",
        "https://gaana.com/song/kesariya-from-brahmastra": "Gaana",
        "https://wynk.in/music/song/kesariya/um_123": "Wynk",
        "https://genius.com/Rick-astley-never-gonna-give-you-up-lyrics": "Genius",
        "https://www.azlyrics.com/lyrics/rickastley/nevergonnagiveyouup.html": "AZLyrics",
        "https://www.last.fm/music/Rick+Astley/_/Never+Gonna+Give+You+Up": "Last.fm",
        "https://www.musixmatch.com/lyrics/Rick-Astley/Never-Gonna-Give-You-Up": "Musixmatch",
    }
    for url, name in cases.items():
        assert links.service_name(url) == name, url
        assert music.looks_like_url(url), url
    for text in ("daft punk", "spotify", "last.fm", "https://example.com/spotify.com/track/x",
                 "https://evilspotify.com/track/4cOdK2wGLETKBW3PvgPWqT", "https://open.spotify.com.evil.io/track/x"):
        assert links.service_name(text) is None, text
        assert not music.looks_like_url(text), text


def test_names_in_the_link_are_enough_for_some_services():
    assert links.read("https://www.last.fm/music/Rick+Astley/_/Never+Gonna+Give+You+Up") == [
        Song("Never Gonna Give You Up", "Rick Astley")]
    assert links.read("https://www.last.fm/de/music/Daft+Punk/Random+Access+Memories") == Album(
        "Random Access Memories", "Daft Punk")
    assert links.read("https://www.musixmatch.com/lyrics/Rick-Astley/Never-Gonna-Give-You-Up") == [
        Song("Never Gonna Give You Up", "Rick Astley")]
    assert links.read("https://www.musixmatch.com/album/Daft-Punk/Random-Access-Memories") == Album(
        "Random Access Memories", "Daft Punk")
    assert links.read("https://wynk.in/music/song/kesariya/um_00602557984071") == [Song("kesariya")]
    for url in ("https://www.last.fm/music/Rick+Astley", "https://wynk.in/music/playlist/x/y",
                "https://open.spotify.com/artist/0gxyHStUsqpMadRV0Di1Qt"):
        with pytest.raises(LinkError):
            links.read(url)


def test_spotify_embed(pages):
    def embed(entity):
        data = {"props": {"pageProps": {"state": {"data": {"entity": entity}}}}}
        return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'

    pages["https://open.spotify.com/embed/track/"] = embed(
        {"type": "track", "name": "Never Gonna Give You Up", "artists": [{"name": "Rick Astley"}], "duration": 213573})
    assert links.read("spotify:track:4cOdK2wGLETKBW3PvgPWqT") == [Song("Never Gonna Give You Up", "Rick Astley", 213)]
    pages["https://open.spotify.com/embed/playlist/"] = embed({"type": "playlist", "trackList": [
        {"title": "One", "subtitle": "A", "duration": 1000}, {"title": "Two", "subtitle": "B, C", "duration": 2000}]})
    assert links.read("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M") == [
        Song("One", "A", 1), Song("Two", "B, C", 2)]


def test_apple_playlist_gets_artists_from_lookup(pages):
    pages["https://music.apple.com/gb/playlist/"] = ld({"@type": "MusicPlaylist", "name": "Hits", "track": [
        {"@type": "MusicRecording", "name": "Nicole Kidman", "url": "https://music.apple.com/gb/song/x/111", "duration": "PT3M1S"},
        {"@type": "MusicRecording", "name": "Not In Lookup", "url": "https://music.apple.com/gb/song/y/222", "duration": "PT1M"},
    ]})
    pages["https://itunes.apple.com/lookup"] = {"results": [
        {"wrapperType": "track", "trackId": 111, "trackName": "Nicole Kidman", "artistName": "ADÉLA", "trackTimeMillis": 181270}]}
    assert links.read("https://music.apple.com/gb/playlist/hits/pl.f4d106fed2bd") == [
        Song("Nicole Kidman", "ADÉLA", 181), Song("Not In Lookup", "", 60)]


def test_json_ld_pages(pages):
    pages["https://gaana.com/song/"] = ld({"@type": "WebPage"}) + ld({
        "@type": "MusicRecording", "name": "Kesariya", "duration": "PT04M28S",
        "byArtist": [{"name": "Pritam"}, {"name": "Arijit Singh"}],
        "inAlbum": {"@type": "MusicAlbum", "name": "Brahmastra"}})
    assert links.read("https://gaana.com/song/kesariya") == [Song("Kesariya", "Pritam, Arijit Singh", 268)]
    pages["https://tidal.com/album/"] = ld({"@context": "x", "@graph": [
        {"@type": "MusicAlbum", "name": "Whenever You Need Somebody", "byArtist": [{"name": "Rick Astley"}]}]})
    pages["https://api.tidal.com/"] = "not json"
    assert links.read("https://tidal.com/browse/album/491206011") == Album("Whenever You Need Somebody", "Rick Astley")


def test_preview_titles(pages):
    pages["https://open.qobuz.com/track/"] = '<meta property="og:title" content="Stand by Me by Ben E. King is on Qobuz.com">'
    assert links.read("https://play.qobuz.com/track/123") == [Song("Stand by Me", "Ben E. King")]
    # Genius without its API falls back to the page title, "Artist – Song".
    pages["https://genius.com/"] = '<meta content="Rick Astley – Never Gonna Give You Up" property="og:title" />'
    assert links.read("https://genius.com/Rick-astley-never-gonna-give-you-up-lyrics") == [
        Song("Never Gonna Give You Up", "Rick Astley")]


def test_unreadable_pages_become_friendly_errors(pages):
    pages["https://open.spotify.com/embed/"] = "<html>nothing here</html>"
    with pytest.raises(LinkError, match="Spotify"):
        links.read("https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT")
    with pytest.raises(LinkError, match="playlists"):
        links.read("https://music.amazon.com/playlists/B07H9GFSXR")


def test_redirects_stay_on_the_service(monkeypatch):
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "spotify.link":
            return httpx.Response(302, headers={"Location": "https://169.254.169.254/latest/meta-data"})
        return httpx.Response(200, text="ok")

    monkeypatch.setattr(links, "_client", httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(LinkError, match="can't follow"):
        links._get("https://spotify.link/abc", links.SPOTIFY_HOSTS)
    with pytest.raises(LinkError, match="can't follow"):
        links._get("http://open.spotify.com/track/x", links.SPOTIFY_HOSTS)


def test_matching_prefers_the_right_version():
    want = Song("Never Gonna Give You Up", "Rick Astley", 213)
    original = {"title": "Never Gonna Give You Up", "artist": "Rick Astley", "duration": 214}
    karaoke = {"title": "Never Gonna Give You Up (Karaoke Version)", "artist": "Rick Astley", "duration": 213}
    stranger = {"title": "Up", "artist": "Someone Else", "duration": 213}
    assert music._match_score(want, original) > music._match_score(want, karaoke)
    assert music._match_score(want, original) > music._match_score(want, stranger)
    # Squashed names from AZLyrics links still match.
    assert music._similar("nevergonnagiveyouup", "Never Gonna Give You Up") == 1.0
    assert music._similar("nevergonnagiveyouup", "Up") == 0.0


def test_find_song_skips_strangers(monkeypatch):
    def track(title, artist):
        return {"video_id": "x" * 11, "title": title, "artist": artist, "album": None, "duration": 200, "thumb": ""}

    results = []
    monkeypatch.setattr(music, "search", lambda q, limit=12: results)
    results[:] = [track("Shake It Off", "Taylor Swift")]  # same artist, different song
    assert music.find_song(Song("A Deep Cut", "Taylor Swift")) is None
    results[:] = [track("Story of My Life", "One Direction")]  # one word in common
    assert music.find_song(Song("Love Story", "Taylor Swift")) is None
    results[:] = [track("Kesariya (From \"Brahmastra\")", "Arijit Singh")]  # credited differently
    assert music.find_song(Song("Kesariya", "Pritam"))["artist"] == "Arijit Singh"
    results[:] = [track("Love Story (Taylor's Version)", "Taylor Swift")]
    assert music.find_song(Song("lovestory", "taylorswift"))


def test_titles_match_through_extras_and_spelling():
    assert music._title_similar("BURN (feat. Ava Max)", "BURN") == 1.0
    assert music._title_similar("Kesariya (From \"Brahmastra\")", "Kesariya") == 1.0
    assert music._similar("Vighnahartha", "Vighnaharta (From \"ANTIM\")") == 0.0  # the extras hide it...
    assert music._title_similar("Vighnahartha", "Vighnaharta (From \"ANTIM\")") > 0.85  # ...until stripped
    assert music._title_similar("Hello", "Othello") < 0.75
