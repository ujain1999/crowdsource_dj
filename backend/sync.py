from flask_socketio import emit, join_room, leave_room
from flask import request

from models import db, Room
from utils import clean_room_id


def register_handlers(socketio):
    
    @socketio.on('connect')
    def handle_connect():
        print(f'Client connected with session ID: {request.sid}')
        emit('message', {'data': 'Welcome! You are connected.'})

    @socketio.on('disconnect')
    def handle_disconnect():
        print('Client disconnected')

    @socketio.on('create-room')
    def handle_create_room(room_id):
        admin_session_id = request.sid
        room = Room.query.filter_by(room_id=clean_room_id(room_id)).first()
        if room:
            room.room_json['admin_session_id'] = admin_session_id
            db.session.add(room)
            db.session.commit()
    
    @socketio.on('join-room')
    def handle_join_room(room_id):
        room_id = clean_room_id(room_id)
        print(f'Client {request.sid} joining room {room_id}')
        room = Room.query.filter_by(room_id=clean_room_id(room_id)).first()
        if room:
            admin_sid = room.room_json.get('admin_session_id', None)
            sids_in_room = socketio.server.manager.get_participants('/', room_id)
            print(list(sids_in_room))
            if admin_sid:
                room.room_json['members'] = room.room_json.get('members', []) + [request.sid]
                join_room(room_id)
                
            else:
                room.room_json['admin_session_id'] = request.sid

            sids_in_room = socketio.server.manager.get_participants('/', room_id)
            print(list(sids_in_room))
            db.session.commit()

    @socketio.on('play')
    def handle_play(data):
        print('Play received')
        room_id = clean_room_id(data['roomID'])
        print('Emiting sync')
        print(room_id)
        sids_in_room = socketio.server.manager.get_participants('/', room_id)
        print(list(sids_in_room))
        emit("sync",{'action' : 'play'}, room=room_id, include_self=False)
        

    @socketio.on('pause')
    def handle_pause(data):
        print('Pause received')
        room_id = clean_room_id(data['roomID'])
        sids_in_room = socketio.server.manager.get_participants('/', room_id)
        print(list(sids_in_room))
        emit("sync",{'action' : 'pause'}, room=room_id, include_self=False)

    @socketio.on('seek')
    def handle_seek(data):
        print('Seek received')
        print(data)

    @socketio.on('update-queue')
    def handle_update_queue(data):
        print('Update queue received')
        print(data)