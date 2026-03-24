from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Room, Message, User
from schemas import MessageCreate, MessageResponse, TokenData
from security import get_current_user
from websocket_manager import manager
from typing import List
import uuid

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/{room_code}/messages", response_model=MessageResponse)
async def add_message(
    room_code: str,
    message: MessageCreate,
    user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify room exists
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Verify user exists
    db_user = db.query(User).filter(User.id == user.user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Create message
    db_message = Message(
        id=str(uuid.uuid4()),
        room_code=room_code,
        user_id=user.user_id,
        content=message.content
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    
    # Broadcast to room
    import asyncio
    asyncio.create_task(manager.broadcast(
        room_code,
        {
            "type": "message",
            "id": db_message.id,
            "user": {
                "id": db_user.id,
                "username": db_user.username,
                "is_guest": db_user.is_guest,
                "created_at": db_user.created_at.isoformat()
            },
            "content": db_message.content,
            "created_at": db_message.created_at.isoformat()
        }
    ))
    
    return {
        "id": db_message.id,
        "content": db_message.content,
        "user": {
            "id": db_user.id,
            "username": db_user.username,
            "is_guest": db_user.is_guest,
            "created_at": db_user.created_at
        },
        "created_at": db_message.created_at
    }


@router.get("/{room_code}/messages", response_model=List[MessageResponse])
async def get_messages(room_code: str, db: Session = Depends(get_db)):
    # Verify room exists
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    messages = db.query(Message).filter(
        Message.room_code == room_code
    ).order_by(Message.created_at).all()
    
    result = []
    for msg in messages:
        user = db.query(User).filter(User.id == msg.user_id).first()
        result.append({
            "id": msg.id,
            "content": msg.content,
            "user": {
                "id": user.id,
                "username": user.username,
                "is_guest": user.is_guest,
                "created_at": user.created_at
            },
            "created_at": msg.created_at
        })
    
    return result
