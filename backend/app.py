from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_cors import CORS
from models import db
import os
import json

from utils import get_youtube_audio, search_yt_music, clean_room_id
from models import Room


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

@app.route('/home', methods=['GET'])
def home_redirect():
    return redirect(url_for('home'))

@app.route('/api/room', methods=['GET', 'POST'])
def room():
    if request.method == 'POST':
        data = request.json
        if data['action'] == 'create':
            room = Room()
            db.session.add(room)
            db.session.commit()
            return jsonify({'room_id': room.room_id})

    
@app.route('/<room_id>', methods=['GET'])
def room_page(room_id):
    room_id = clean_room_id(room_id)
    print(room_id)
    room = Room.query.filter_by(room_id=room_id).first()
    if room:
        room_json = room.room_json
        return render_template('room.html')
    else:
        return redirect(url_for('home'))


@app.route('/api/queue', methods=['POST'])
def queue():
    if request.method == 'POST':
        data = request.json
        room_id = clean_room_id(data['room_id'])
        room = Room.query.filter_by(room_id=room_id).first()
        if room:
            room_json = room.room_json
            return jsonify(room_json)
        else:
            return jsonify({'error': 'Room not found'}), 404

@app.route('/api/search', methods=['POST'])
def search():
    data = request.json 
    print(data)
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
        room_id = clean_room_id(data['room_id'])
        room = Room.query.filter_by(room_id=room_id).first()
        room_json = room.room_json
        room_json['queue'] = room_json.get('queue', []) + [metadata]
        room.room_json = room_json
        db.session.commit()
        return jsonify(metadata)

if __name__ == '__main__':
    app.run(debug=True)