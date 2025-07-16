from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.mutable import MutableDict
from datetime import datetime
import random, string

db = SQLAlchemy()

class AppModel(db.Model):
    __abstract__ = True
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_dt = db.Column(db.DateTime, default=datetime.utcnow)
    updated_dt = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Room(AppModel):
    __tablename__ = 'room'
    room_id = db.Column(db.String(12), unique=True, nullable=False)
    # room_json = db.Column(db.JSON, default={})
    room_json = db.Column(MutableDict.as_mutable(db.JSON), default={})

    def __init__(self):
        self.room_id = self.generate_unique_room_id()
        self.room_json = {}


    @staticmethod
    def generate_unique_room_id():
        while True:
            room_id = ''.join(random.choices(string.ascii_lowercase, k=12))
            if not Room.query.filter_by(room_id=room_id).first():
                return room_id
