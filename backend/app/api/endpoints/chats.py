from typing import List, Optional
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.orm import Session
from app.crud.chat import create_chat, get_chat, get_chats_by_user, update_chat, delete_chat, create_message, get_messages_by_chat, get_recent_messages, update_chat_last_message
from app.crud.user import get_user
from app.schemas.chat import Chat, ChatCreate, ChatUpdate, Message, MessageCreate, MessageType
from app.schemas.user import User
from app.api import deps
from app.core.redis import redis_client
from app.core.config import settings
from app.core.llm_service import get_llm_service, LLMMessage, LLMMessageType
import json
import asyncio

logger = logging.getLogger("novamind.chats")

router = APIRouter()

@router.post("", response_model=Chat)
def create_chat_endpoint(
    chat_in: ChatCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    return create_chat(db=db, chat=chat_in, user_id=current_user.id)

@router.get("", response_model=List[Chat])
def get_chats_endpoint(
    skip: int = 0,
    limit: int = 100,
    chat_type: Optional[str] = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    if chat_type:
        chats = get_chats_by_user_and_type(db=db, user_id=current_user.id, chat_type=chat_type, skip=skip, limit=limit)
    else:
        chats = get_chats_by_user(db=db, user_id=current_user.id, skip=skip, limit=limit)
    return chats

@router.get("/{chat_id}", response_model=Chat)
def get_chat_endpoint(
    chat_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    chat = get_chat(db=db, chat_id=chat_id)
    if not chat or chat.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat

@router.put("/{chat_id}", response_model=Chat)
def update_chat_endpoint(
    chat_id: int,
    chat_in: ChatUpdate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    chat = get_chat(db=db, chat_id=chat_id)
    if not chat or chat.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Chat not found")
    return update_chat(db=db, chat_id=chat_id, chat=chat_in)

@router.delete("/{chat_id}", response_model=Chat)
def delete_chat_endpoint(
    chat_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    chat = get_chat(db=db, chat_id=chat_id)
    if not chat or chat.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Chat not found")
    return delete_chat(db=db, chat_id=chat_id)

@router.post("/{chat_id}/messages", response_model=Message)
async def create_message_endpoint(
    chat_id: int,
    message_in: MessageCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    chat = get_chat(db=db, chat_id=chat_id)
    if not chat or chat.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Store user message in database
    user_message = create_message(db=db, message=message_in, chat_id=chat_id, user_id=current_user.id)

    # Store conversation context in Redis (short-term memory)
    chat_key = f"chat:{chat_id}:messages"
    message_data = {
        "id": user_message.id,
        "content": message_in.content,
        "message_type": message_in.message_type.value if hasattr(message_in.message_type, 'value') else str(message_in.message_type),
        "is_ai": False,
        "user_id": current_user.id,
        "created_at": user_message.created_at.isoformat() if hasattr(user_message.created_at, 'isoformat') else str(user_message.created_at)
    }

    # Add to Redis list, keep last 10 messages
    redis_client.lpush(chat_key, json.dumps(message_data))
    redis_client.ltrim(chat_key, 0, 9)  # Keep only last 10 messages
    redis_client.expire(chat_key, 3600)  # Expire after 1 hour

    # Update chat's last message time
    background_tasks.add_task(update_chat_last_message, db, chat_id)

    # Get conversation history for AI context
    message_history = []
    stored_messages = redis_client.lrange(chat_key, 0, -1)
    for stored_msg in reversed(stored_messages):  # Reverse to get chronological order
        try:
            msg_data = json.loads(stored_msg)
            message_history.append(msg_data)
        except:
            pass

    # Generate AI response using the LLM service
    llm_service = get_llm_service()

    # Convert chat messages to LLM service format
    llm_messages = llm_service.prepare_messages_for_llm(message_history)

    # Add the current user message to the conversation
    current_user_msg = LLMMessage(
        content=message_in.content,
        message_type=LLMMessageType(message_in.message_type.value),
        is_ai=False,
        user_id=current_user.id
    )
    llm_messages.append(current_user_msg)

    # Generate response from LLM
    try:
        llm_response = await llm_service.generate_response(
            messages=llm_messages,
            temperature=0.7,
            max_tokens=500  # Reasonable default for chat responses
        )

        ai_message_content = llm_response.content
        ai_message_type = llm_response.message_type
        ai_metadata = llm_service.extract_response_metadata(llm_response)

        # Store AI-specific metrics in request state for usage logging
        request.state.ai_tokens_used = llm_response.tokens_used
        request.state.ai_model_used = llm_response.model_name

    except (httpx.TimeoutException, asyncio.TimeoutError) as timeout_exc:
        # Ollama didn't reply inside OLLAMA_TIMEOUT_S. Surface a clean 504 so
        # the client knows to retry (vs the generic 500 below). The user
        # message is already persisted — the next request will see it and
        # can ask again. This is the path that fires on Vercel's 10s/60s
        # free/Pro cutoffs when Ollama is slower than the platform limit.
        logger.warning("LLM timeout on chat %s: %s", chat_id, timeout_exc)
        raise HTTPException(
            status_code=504,
            detail={
                "code": "llm_timeout",
                "message": "The model took too long to respond. Please try again.",
            },
        )
    except Exception as e:
        # Fallback to basic response if LLM fails
        ai_message_content = f"I apologize, but I'm unable to generate a response at the moment. Please try again later.\n\nError: {str(e)}"
        ai_message_type = LLMMessageType.TEXT
        ai_metadata = {
            "model": "error-fallback",
            "error": str(e)
        }
        # Set default values for failed requests
        request.state.ai_tokens_used = None
        request.state.ai_model_used = None

    ai_message = MessageCreate(
        content=ai_message_content,
        message_type=MessageType(ai_message_type.value),
        is_ai=True,
        meta_data=ai_metadata
    )
    ai_message_db = create_message(db=db, message=ai_message, chat_id=chat_id, user_id=0)  # 0 for AI user

    # Also store AI message in Redis
    ai_message_data = {
        "id": ai_message_db.id,
        "content": ai_message_content,
        "message_type": ai_message.message_type.value if hasattr(ai_message.message_type, 'value') else str(ai_message.message_type),
        "is_ai": True,
        "user_id": 0,
        "created_at": ai_message_db.created_at.isoformat() if hasattr(ai_message_db.created_at, 'isoformat') else str(ai_message_db.created_at)
    }
    redis_client.lpush(chat_key, json.dumps(ai_message_data))
    redis_client.ltrim(chat_key, 0, 9)

    return ai_message_db

@router.get("/{chat_id}/messages", response_model=List[Message])
def get_messages_endpoint(
    chat_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    chat = get_chat(db=db, chat_id=chat_id)
    if not chat or chat.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Chat not found")
    return get_messages_by_chat(db=db, chat_id=chat_id, skip=skip, limit=limit)