from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Room, User, QueueItem
from schemas import RoomCreate, RoomResponse, RoomDetailResponse, RoomStateResponse, QueueItemResponse
from security import get_optional_user
from schemas import TokenData
import uuid
import random
import string

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


def generate_room_code() -> str:
    """Generate a random 12-character room code"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=12))


@router.post("/create", response_model=RoomResponse)
async def create_room(
    room: RoomCreate,
    user: TokenData = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    # Get or create admin user
    if user:
        admin = db.query(User).filter(User.id == user.user_id).first()
        if not admin:
            raise HTTPException(status_code=404, detail="User not found")
    elif room.user_id:
        # Use the provided user_id from frontend (guest user)
        admin = db.query(User).filter(User.id == room.user_id).first()
        if not admin:
            raise HTTPException(status_code=404, detail="User not found")
    else:
        # Create guest admin
        admin_id = str(uuid.uuid4())
        admin_username = f"Guest_{uuid.uuid4().hex[:8].upper()}"
        admin = User(id=admin_id, username=admin_username, is_guest=True)
        db.add(admin)
        db.commit()
        db.refresh(admin)
    
    # Generate unique room code
    room_code = generate_room_code()
    while db.query(Room).filter(Room.code == room_code).first():
        room_code = generate_room_code()
    
    # Create room
    db_room = Room(
        code=room_code,
        name=room.name,
        admin_id=admin.id
    )
    db.add(db_room)
    db.commit()
    db.refresh(db_room)
    
    return {
        "code": db_room.code,
        "name": db_room.name,
        "admin_id": db_room.admin_id,
        "created_at": db_room.created_at,
        "queue": []
    }


@router.get("/{room_code}", response_model=RoomDetailResponse)
async def get_room(room_code: str, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    admin = db.query(User).filter(User.id == room.admin_id).first()
    queue_items = db.query(QueueItem).filter(QueueItem.room_code == room_code).order_by(QueueItem.position).all()
    
    return {
        "code": room.code,
        "name": room.name,
        "admin_id": room.admin_id,
        "admin": {
            "id": admin.id,
            "username": admin.username,
            "is_guest": admin.is_guest,
            "created_at": admin.created_at
        },
        "created_at": room.created_at,
        "queue": [
            {
                "id": item.id,
                "song_id": item.song_id,
                "title": item.title,
                "artist": item.artist,
                "duration": item.duration,
                "thumbnail": item.thumbnail,
                "url": item.url,
                "added_by": item.added_by,
                "position": item.position
            }
            for item in queue_items
        ]
    }


@router.post("/{room_code}/join", response_model=RoomResponse)
async def join_room(room_code: str, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    return {
        "code": room.code,
        "name": room.name,
        "admin_id": room.admin_id,
        "created_at": room.created_at,
        "queue": []
    }
