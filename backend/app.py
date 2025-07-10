from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from models import db
import os

from utils import get_youtube_audio, search_yt_music


def create_app():
    app = Flask(__name__, template_folder='../frontend/templates/', static_folder='../frontend/static/')

    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    with app.app_context():
        db.create_all()
    
    return app

app = create_app()
@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def search():
    data = request.json 
    if data['type'] == 'url':
        if data['playlist']:
            metadata = {}
            print('Playlist')
        else:
            metadata = get_youtube_audio(data['inputText'])
    elif data['type'] == 'query':
        metadata = search_yt_music(data['inputText'])
    if 'error' in metadata:
        return jsonify(metadata), 500
    else:
        return jsonify(metadata)

if __name__ == '__main__':
    app.run(debug=True)