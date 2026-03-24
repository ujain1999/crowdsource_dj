from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


# User Schemas
class UserBase(BaseModel):
    username: str


class UserCreate(UserBase):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(UserBase):
    id: str
    is_guest: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserGuest(BaseModel):
    username: str


# Song/Queue Schemas
class SongBase(BaseModel):
    title: str
    artist: str
    duration: float
    thumbnail: Optional[str] = None
    url: str
    added_by: str


class SongCreate(BaseModel):
    query: Optional[str] = None
    url: Optional[str] = None


class SongResponse(SongBase):
    id: str

    class Config:
        from_attributes = True


class QueueItemResponse(BaseModel):
    id: str
    song_id: str
    title: str
    artist: str
    duration: float
    thumbnail: Optional[str] = None
    url: str
    added_by: str
    position: int

    class Config:
        from_attributes = True


class QueueReorderRequest(BaseModel):
    from_index: int
    to_index: int


# Room Schemas
class RoomCreate(BaseModel):
    name: str
    user_id: Optional[str] = None


class RoomResponse(BaseModel):
    code: str
    name: str
    admin_id: str
    created_at: datetime
    queue: List[QueueItemResponse] = []

    class Config:
        from_attributes = True


class RoomDetailResponse(RoomResponse):
    admin: UserResponse
    queue: List[QueueItemResponse]


class RoomStateResponse(BaseModel):
    code: str
    name: str
    is_admin: bool
    current_song: Optional[SongResponse] = None
    current_time: float = 0
    is_playing: bool = False
    queue: List[QueueItemResponse] = []


# Chat Schemas
class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: str
    content: str
    user: UserResponse
    created_at: datetime

    class Config:
        from_attributes = True


# Auth Schemas
class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


class TokenData(BaseModel):
    user_id: Optional[str] = None
