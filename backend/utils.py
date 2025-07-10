from flask import jsonify
from yt_dlp import YoutubeDL
from ytmusicapi import YTMusic

def search_yt_music(query):
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/best',
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extract_flat': False,
    }
    ytmusic = YTMusic()
    yt_music_url = ytmusic.search(query, filter="songs")
    if yt_music_url:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://music.youtube.com/watch?v={yt_music_url[0]['videoId']}", download=False)
            yt_music_metadata = {
                "title": info.get('title', 'Unknown Title'),
                "artist": info.get('uploader', 'Unknown Artist'),
                "url": info.get('url'),
                "thumbnail": info.get('thumbnail', ''),
                "duration": info.get('duration', 0)
            }
    return yt_music_metadata

def get_youtube_audio(youtube_url):
    if not youtube_url:
        return {"error": "Missing URL"}

    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/best',
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extract_flat': False,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            metadata = {
                "title": info.get('title', 'Unknown Title'),
                "artist": info.get('uploader', 'Unknown Artist'),
                "url": info.get('url'),
                "thumbnail": info.get('thumbnail', ''),
                "duration": info.get('duration', 0)
            }
            if "music.youtube" not in youtube_url:
                yt_music_metadata = search_yt_music(f"{metadata['title']} {metadata['artist']}")
                if yt_music_metadata['title'].lower().replace(' ','') in metadata['title'].lower().replace(' ',''):
                    metadata = yt_music_metadata
            return metadata
    except Exception as e:
        return {"error": "Failed to fetch audio", "details": str(e)}
