from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Room, QueueItem
from schemas import SongCreate, QueueItemResponse, QueueReorderRequest
from websocket_manager import manager
from typing import List
import uuid
import sys
import os

# Add parent directory to path to import utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import search_yt_music, get_youtube_audio

router = APIRouter(prefix="/api/songs", tags=["songs"])


def get_next_position(db: Session, room_code: str) -> int:
    """Get the next position for a queue item"""
    last_item = db.query(QueueItem).filter(
        QueueItem.room_code == room_code
    ).order_by(QueueItem.position.desc()).first()
    return (last_item.position if last_item else -1) + 1


@router.post("/{room_code}/add", response_model=QueueItemResponse)
async def add_song_to_queue(
    room_code: str,
    song: SongCreate,
    db: Session = Depends(get_db)
):
    # Verify room exists
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Get song metadata
    try:
        if song.url:
            metadata = get_youtube_audio(song.url)
        elif song.query:
            metadata = search_yt_music(song.query)
        else:
            raise HTTPException(
                status_code=400,
                detail="Either url or query must be provided"
            )
        
        if "error" in metadata:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to fetch song: {metadata.get('error')}"
            )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch song metadata: {str(e)}"
        )
    
    # Create queue item
    position = get_next_position(db, room_code)
    queue_item = QueueItem(
        id=str(uuid.uuid4()),
        room_code=room_code,
        song_id=str(uuid.uuid4()),
        title=metadata.get("title", "Unknown"),
        artist=metadata.get("artist", "Unknown"),
        duration=metadata.get("duration", 0),
        thumbnail=metadata.get("thumbnail"),
        url=metadata.get("url", ""),
        added_by="Guest",  # Will be updated when WebSocket connects
        position=position
    )
    db.add(queue_item)
    db.commit()
    db.refresh(queue_item)
    
    # Broadcast to room
    import asyncio
    asyncio.create_task(manager.broadcast(
        room_code,
        {
            "type": "song_added",
            "song": {
                "id": queue_item.id,
                "song_id": queue_item.song_id,
                "title": queue_item.title,
                "artist": queue_item.artist,
                "duration": queue_item.duration,
                "thumbnail": queue_item.thumbnail,
                "url": queue_item.url,
                "added_by": queue_item.added_by,
                "position": queue_item.position
            }
        }
    ))
    
    return {
        "id": queue_item.id,
        "song_id": queue_item.song_id,
        "title": queue_item.title,
        "artist": queue_item.artist,
        "duration": queue_item.duration,
        "thumbnail": queue_item.thumbnail,
        "url": queue_item.url,
        "added_by": queue_item.added_by,
        "position": queue_item.position
    }


@router.delete("/{room_code}/songs/{song_id}")
async def remove_song(room_code: str, song_id: str, db: Session = Depends(get_db)):
    # Verify room exists
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Find and delete song
    queue_item = db.query(QueueItem).filter(
        QueueItem.id == song_id,
        QueueItem.room_code == room_code
    ).first()
    
    if not queue_item:
        raise HTTPException(status_code=404, detail="Song not found in queue")
    
    db.delete(queue_item)
    db.commit()
    
    # Update positions
    remaining_items = db.query(QueueItem).filter(
        QueueItem.room_code == room_code
    ).order_by(QueueItem.position).all()
    
    for idx, item in enumerate(remaining_items):
        item.position = idx
    db.commit()
    
    # Broadcast to room
    import asyncio
    asyncio.create_task(manager.broadcast(
        room_code,
        {
            "type": "song_removed",
            "song_id": song_id
        }
    ))
    
    return {"detail": "Song removed"}


@router.post("/{room_code}/queue/reorder")
async def reorder_queue(
    room_code: str,
    reorder: QueueReorderRequest,
    db: Session = Depends(get_db)
):
    # Verify room exists
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Get all queue items
    queue_items = db.query(QueueItem).filter(
        QueueItem.room_code == room_code
    ).order_by(QueueItem.position).all()
    
    if reorder.from_index < 0 or reorder.from_index >= len(queue_items):
        raise HTTPException(status_code=400, detail="Invalid from_index")
    
    if reorder.to_index < 0 or reorder.to_index >= len(queue_items):
        raise HTTPException(status_code=400, detail="Invalid to_index")
    
    # Reorder items
    moved_item = queue_items.pop(reorder.from_index)
    queue_items.insert(reorder.to_index, moved_item)
    
    # Update positions
    for idx, item in enumerate(queue_items):
        item.position = idx
    db.commit()
    
    # Broadcast to room
    import asyncio
    asyncio.create_task(manager.broadcast(
        room_code,
        {
            "type": "queue_reordered",
            "from_index": reorder.from_index,
            "to_index": reorder.to_index
        }
    ))
    
    return {"detail": "Queue reordered"}


@router.get("/{room_code}/queue", response_model=List[QueueItemResponse])
async def get_queue(room_code: str, db: Session = Depends(get_db)):
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    queue_items = db.query(QueueItem).filter(
        QueueItem.room_code == room_code
    ).order_by(QueueItem.position).all()
    
    return [
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
