from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.schemas.user import User
from enum import Enum

class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    CODE = "code"
    FILE = "file"

class MessageBase(BaseModel):
    content: str
    message_type: MessageType = MessageType.TEXT
    is_ai: bool = False
    # Stored as JSON text in SQLite; tolerate either a dict or a string
    # depending on the path that read the row.
    meta_data: Optional[Any] = None

class MessageCreate(MessageBase):
    pass

class Message(MessageBase):
    id: int
    chat_id: int
    user_id: Optional[int] = None
    created_at: datetime

    class Config:
        orm_mode = True

class ChatBase(BaseModel):
    title: str
    chat_type: Optional[str] = "conversation"
    status: Optional[str] = "active"
    settings: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None

class ChatCreate(ChatBase):
    pass

class ChatUpdate(BaseModel):
    title: Optional[str] = None
    chat_type: Optional[str] = None
    status: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None

class ChatInDBBase(ChatBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_message_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class ChatInDB(ChatInDBBase):
    pass

class Chat(ChatInDBBase):
    messages: List[Message] = []
    user: Optional[User] = None

    class Config:
        orm_mode = True