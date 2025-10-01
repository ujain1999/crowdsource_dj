from models import db
from flask import Blueprint, request, jsonify

from utils import get_youtube_audio, search_yt_music, clean_room_id
from models import Room

api_bp = Blueprint('api_bp', __name__)

@api_bp.route('/api/room', methods=['GET', 'POST'])
def room():
    # import ipdb; ipdb.set_trace()
    if request.method == 'POST':
        data = request.json
        if data['action'] == 'create':
            room = Room()
            db.session.add(room)
            db.session.commit()
            return jsonify({'room_id': room.room_id})

@api_bp.route('/api/queue', methods=['POST'])
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

@api_bp.route('/api/search', methods=['POST'])
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
        room_id = clean_room_id(data['room_id'])
        room = Room.query.filter_by(room_id=room_id).first()
        room_json = room.room_json
        room_json['queue'] = room_json.get('queue', []) + [metadata]
        room.room_json = room_json
        db.session.commit()
        return jsonify(metadata)
