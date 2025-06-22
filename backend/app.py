from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import json
from yt_dlp import YoutubeDL

app = Flask(__name__, template_folder='../frontend/templates/')

CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

queue = []

@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/api/suggestions', methods=['GET'])
def get_suggestions():
    if request.method == 'GET':
        youtube_url = "https://www.youtube.com/watch?v=H7fBFtif9H4"
        ydl_opts = {
            'format': 'bestaudio/best',
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
                    "file": info.get('url'),
                    "thumbnail": info.get('thumbnail', ''),
                    "duration": info.get('duration', 0),
                }
                return jsonify([metadata])
        except Exception as e:
            return jsonify({"error": "Failed to fetch audio", "details": str(e)}), 500



@app.route('/api/queue', methods=['GET', 'POST', 'DELETE'])
def handle_queue():
    global queue
    if request.method == 'GET':
        return jsonify(queue)
    elif request.method == 'POST':
        track = request.json
        queue.append(track)
        return '', 204
    elif request.method == 'DELETE':
        queue = []
        return '', 204

@app.route('/api/youtube-audio', methods=['POST'])
def get_youtube_audio():
    data = request.get_json()
    youtube_url = data.get("url")
    if not youtube_url:
        return jsonify({"error": "Missing URL"}), 400

    ydl_opts = {
        'format': 'bestaudio/best',
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
                "file": info.get('url'),
                "thumbnail": info.get('thumbnail', ''),
                "duration": info.get('duration', 0),
            }
            return jsonify(metadata)
    except Exception as e:
        return jsonify({"error": "Failed to fetch audio", "details": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)