from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    status,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session
from database import get_db
from models import Room, User
from websocket_manager import manager
from schemas import TokenData
from security import get_optional_user
from jose import jwt
from config import settings
import json

router = APIRouter(prefix="/api", tags=["websocket"])


@router.websocket("/ws/{room_code}/{user_id}/{username}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_code: str,
    user_id: str,
    username: str,
    db: Session = Depends(get_db),
):
    # Verify room exists
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Room not found"
        )
        return

    try:
        await manager.connect(websocket, room_code, user_id, username)

        # Get current playback state
        playback_state = manager.get_playback_state(room_code)
        print(
            f"[WS] Sending playback_state to new user: current_song_id={playback_state.get('current_song_id')}, current_time={playback_state.get('current_time')}, is_playing={playback_state.get('is_playing')}"
        )

        # Send current state to the connected user
        await websocket.send_json(
            {
                "type": "connection_established",
                "room_code": room_code,
                "user_count": manager.get_room_user_count(room_code),
                "users": manager.get_room_users(room_code),
                "playback_state": playback_state,
            }
        )

        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")
            print(
                f"[WS] Received message type: {message_type} from {username} in room {room_code}"
            )
            print(f"[WS] Message data: {data}")

            if message_type == "play":
                current_song_id = data.get("current_song_id")
                current_time = data.get("current_time", 0)
                print(f"[WS] PLAY: song_id={current_song_id}, time={current_time}")
                # Update state
                manager.set_playback_state(
                    room_code, current_song_id, True, current_time
                )
                # Broadcast to all users
                await manager.broadcast(
                    room_code,
                    {
                        "type": "play",
                        "current_song_id": current_song_id,
                        "current_time": current_time,
                    },
                )

            elif message_type == "pause":
                current_time = data.get("current_time", 0)
                print(f"[WS] PAUSE: time={current_time}")
                # Get current song from state
                state = manager.get_playback_state(room_code)
                # Update state
                manager.set_playback_state(
                    room_code, state.get("current_song_id"), False, current_time
                )
                # Broadcast to all users
                await manager.broadcast(
                    room_code, {"type": "pause", "current_time": current_time}
                )

            elif message_type == "seek":
                current_time = data.get("current_time", 0)
                print(f"[WS] SEEK: time={current_time}")
                # Get current song from state
                state = manager.get_playback_state(room_code)
                is_playing = data.get("is_playing", False)
                # Update state
                manager.set_playback_state(
                    room_code, state.get("current_song_id"), is_playing, current_time
                )
                # Broadcast to all users
                await manager.broadcast(
                    room_code, {"type": "seek", "current_time": current_time}
                )

            elif message_type == "skip":
                current_song_id = data.get("current_song_id")
                current_time = data.get("current_time", 0)
                print(f"[WS] SKIP: song_id={current_song_id}, time={current_time}")
                # Update state
                manager.set_playback_state(
                    room_code, current_song_id, True, current_time
                )
                # Broadcast to all users
                await manager.broadcast(
                    room_code,
                    {
                        "type": "skip",
                        "current_song_id": current_song_id,
                        "current_time": current_time,
                    },
                )

            elif message_type == "heartbeat":
                # Keep connection alive
                await websocket.send_json({"type": "heartbeat"})

            else:
                # Unknown message type
                print(f"[WS] Unknown message type: {message_type}")
                await websocket.send_json(
                    {"type": "error", "detail": f"Unknown message type: {message_type}"}
                )

    except WebSocketDisconnect:
        # Find the connection data to get the username for disconnect notification
        if room_code in manager.active_connections:
            for ws, data in manager.active_connections[room_code]:
                if ws == websocket:
                    broadcast_username = data.username
                    break

            manager.disconnect(room_code, websocket)

            # Send leave notification
            await manager.broadcast(
                room_code,
                {
                    "type": "user_left",
                    "username": broadcast_username,
                    "user_count": manager.get_room_user_count(room_code),
                },
            )

    except Exception as e:
        manager.disconnect(room_code, websocket)
        try:
            await websocket.close(code=status.WS_1011_SERVER_ERROR)
        except:
            pass
