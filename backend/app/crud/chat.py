from sqlalchemy.orm import Session
from app.models.chat import Chat, Message
from app.schemas.chat import ChatCreate, ChatUpdate, MessageCreate
from app.models.user import User
import json

def get_chat(db: Session, chat_id: int):
    return db.query(Chat).filter(Chat.id == chat_id).first()

def get_chats_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return db.query(Chat).filter(Chat.user_id == user_id).offset(skip).limit(limit).all()

def get_chats_by_user_and_type(db: Session, user_id: int, chat_type: str, skip: int = 0, limit: int = 100):
    return db.query(Chat).filter(Chat.user_id == user_id, Chat.chat_type == chat_type).offset(skip).limit(limit).all()

def create_chat(db: Session, chat: ChatCreate, user_id: int):
    db_chat = Chat(
        title=chat.title,
        user_id=user_id,
        chat_type=chat.chat_type or "conversation",
        status=chat.status or "active",
        settings=json.dumps(chat.settings) if chat.settings else None,
        tags=json.dumps(chat.tags) if chat.tags else None
    )
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)
    return db_chat

def update_chat(db: Session, chat_id: int, chat: ChatUpdate):
    db_chat = get_chat(db, chat_id)
    if db_chat:
        update_data = chat.dict(exclude_unset=True)
        # Handle JSON fields
        if "settings" in update_data and isinstance(update_data["settings"], dict):
            update_data["settings"] = json.dumps(update_data["settings"])
        if "tags" in update_data and isinstance(update_data["tags"], list):
            update_data["tags"] = json.dumps(update_data["tags"])
        for key, value in update_data.items():
            setattr(db_chat, key, value)
        db.commit()
        db.refresh(db_chat)
    return db_chat

def delete_chat(db: Session, chat_id: int):
    db_chat = get_chat(db, chat_id)
    if db_chat:
        db.delete(db_chat)
        db.commit()
    return db_chat

def create_message(db: Session, message: MessageCreate, chat_id: int, user_id: int = None):
    db_message = Message(
        **message.dict(exclude={"meta_data"}),
        chat_id=chat_id,
        user_id=user_id,
        meta_data=json.dumps(message.meta_data) if message.meta_data else None
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message

def get_messages_by_chat(db: Session, chat_id: int, skip: int = 0, limit: int = 100):
    return db.query(Message).filter(Message.chat_id == chat_id).order_by(Message.created_at.asc()).offset(skip).limit(limit).all()

def get_recent_messages(db: Session, chat_id: int, limit: int = 50):
    return db.query(Message).filter(Message.chat_id == chat_id).order_by(Message.created_at.desc()).limit(limit).all()

def update_chat_last_message(db: Session, chat_id: int):
    """Update the last message timestamp for a chat"""
    db_chat = get_chat(db, chat_id)
    if db_chat:
        db_chat.last_message_at = func.now()
        db.commit()
        db.refresh(db_chat)
    return db_chat