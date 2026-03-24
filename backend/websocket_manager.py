from fastapi import WebSocket
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class ConnectionData:
    user_id: str
    username: str
    room_code: str


@dataclass
class PlaybackState:
    current_song_id: Optional[str] = None
    is_playing: bool = False
    current_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    play_started_at: Optional[datetime] = None  # Track when play started for accurate sync


class ConnectionManager:
    def __init__(self):
        # room_code -> Set of WebSocket connections
        self.active_connections: Dict[str, List[tuple[WebSocket, ConnectionData]]] = {}
        # room_code -> playback state
        self.playback_state: Dict[str, PlaybackState] = {}
        # room_code -> current song being played
        self.current_songs: Dict[str, Optional[str]] = {}
    
    async def connect(self, websocket: WebSocket, room_code: str, user_id: str, username: str):
        await websocket.accept()
        
        if room_code not in self.active_connections:
            self.active_connections[room_code] = []
            self.playback_state[room_code] = PlaybackState()
        
        connection_data = ConnectionData(user_id=user_id, username=username, room_code=room_code)
        self.active_connections[room_code].append((websocket, connection_data))
        
        # Send join notification
        await self.broadcast(
            room_code,
            {
                "type": "user_joined",
                "username": username,
                "timestamp": datetime.utcnow().isoformat(),
            },
            exclude_user=user_id
        )
    
    def disconnect(self, room_code: str, websocket: WebSocket):
        if room_code in self.active_connections:
            self.active_connections[room_code] = [
                (ws, data) for ws, data in self.active_connections[room_code]
                if ws != websocket
            ]
    
    async def broadcast(self, room_code: str, message: dict, exclude_user: str = None):
        if room_code not in self.active_connections:
            return
        
        disconnected = []
        for websocket, data in self.active_connections[room_code]:
            if exclude_user and data.user_id == exclude_user:
                continue
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(room_code, ws)
    
    async def send_to_user(self, room_code: str, user_id: str, message: dict):
        if room_code not in self.active_connections:
            return
        
        for websocket, data in self.active_connections[room_code]:
            if data.user_id == user_id:
                try:
                    await websocket.send_json(message)
                except Exception:
                    pass
    
    def get_room_users(self, room_code: str) -> List[str]:
        if room_code not in self.active_connections:
            return []
        return [data.username for _, data in self.active_connections[room_code]]
    
    def get_room_user_count(self, room_code: str) -> int:
        if room_code not in self.active_connections:
            return 0
        return len(self.active_connections[room_code])
    
    def get_playback_state(self, room_code: str) -> dict:
        """Get current playback state for a room"""
        if room_code not in self.playback_state:
            return {
                "current_song_id": None,
                "is_playing": False,
                "current_time": 0.0
            }
        
        state = self.playback_state[room_code]
        current_time = state.current_time
        
        # If playing, calculate elapsed time since play started
        if state.is_playing and state.play_started_at:
            elapsed = (datetime.utcnow() - state.play_started_at).total_seconds()
            current_time = state.current_time + elapsed
        
        return {
            "current_song_id": state.current_song_id,
            "is_playing": state.is_playing,
            "current_time": current_time
        }
    
    def set_playback_state(self, room_code: str, current_song_id: Optional[str], is_playing: bool, current_time: float):
        """Update playback state for a room"""
        if room_code not in self.playback_state:
            self.playback_state[room_code] = PlaybackState()
        
        state = self.playback_state[room_code]
        state.current_song_id = current_song_id
        state.is_playing = is_playing
        state.current_time = current_time
        state.timestamp = datetime.utcnow()
        
        # If starting to play, record the time
        if is_playing:
            state.play_started_at = datetime.utcnow()
        else:
            state.play_started_at = None


manager = ConnectionManager()
