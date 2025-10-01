from flask import Blueprint, request, render_template, redirect, url_for

from utils import clean_room_id
from models import db, Room

api_bp = Blueprint('api_bp', __name__)

routes_bp = Blueprint('routes_bp', __name__)

@routes_bp.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@routes_bp.route('/home', methods=['GET'])
def home_redirect():
    return redirect(url_for('home'))

@routes_bp.route('/<room_id>', methods=['GET'])
def room_page(room_id):
    room_id = clean_room_id(room_id)
    print(room_id)
    room = Room.query.filter_by(room_id=room_id).first()
    # import ipdb; ipdb.set_trace()
    if room:
        return render_template('room.html')
    else:
        return redirect(url_for('home'))