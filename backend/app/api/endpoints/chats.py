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

    # Image-mode branch: skip the LLM, hit Pollinations, and persist the
    # resulting image as the AI message. The user message is also stored
    # so the conversation log reads naturally ("user asked for an image →
    # AI produced one"). The base64 lives in meta_data so we don't need a
    # new column. `meta_data` is already JSON-shaped and tolerates any
    # extra keys (see schemas/chat.py: MessageBase.meta_data: Optional[Any]).
    if (
        message_in.message_type is not None
        and message_in.message_type.value == "image"
    ):
        return await _create_image_message(
            chat_id=chat_id,
            chat=chat,
            message_in=message_in,
            background_tasks=background_tasks,
            request=request,
            db=db,
            current_user=current_user,
        )

    # File-mode branches: PPT / Word / Code. We use the existing
    # MessageType.CODE and MessageType.FILE enum values (no schema
    # migration) and discriminate within `file` by meta_data.kind
    # ("pptx" / "docx"). Each branch mirrors _create_image_message:
    # skip the LLM codepath, run the file generator, persist a user +
    # AI message pair, push to Redis, set request.state for usage.
    if (
        message_in.message_type is not None
        and message_in.message_type.value == "file"
    ):
        meta_in = message_in.meta_data if isinstance(message_in.meta_data, dict) else {}
        kind = (meta_in.get("kind") or "").lower()
        if kind == "pptx":
            return await _create_pptx_message(
                chat_id=chat_id,
                chat=chat,
                message_in=message_in,
                background_tasks=background_tasks,
                request=request,
                db=db,
                current_user=current_user,
            )
        if kind == "docx":
            return await _create_docx_message(
                chat_id=chat_id,
                chat=chat,
                message_in=message_in,
                background_tasks=background_tasks,
                request=request,
                db=db,
                current_user=current_user,
            )
        # Unknown `kind` — fall through to the LLM codepath so the user
        # gets a sane error rather than a 502. The LLM will likely
        # echo the prompt back, which is the closest thing to a useful
        # response when the frontend is out of sync with the backend.
        logger.warning("Unknown file kind=%r on chat %s — falling through", kind, chat_id)

    if (
        message_in.message_type is not None
        and message_in.message_type.value == "code"
    ):
        return await _create_code_message(
            chat_id=chat_id,
            chat=chat,
            message_in=message_in,
            background_tasks=background_tasks,
            request=request,
            db=db,
            current_user=current_user,
        )

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

    # Generate AI response using the LLM service. We honor the
    # `message_in.model` field (set by the UI's model picker) and fall
    # back to the default public id if unset. The factory always
    # returns a stealth-router service, so `model_name` on the response
    # is always a public NovaMind id — the real backend identity never
    # leaks through the wire.
    from app.core import alias_config
    chosen_model = message_in.model or alias_config.default_public_id()
    llm_service = get_llm_service(model_name=chosen_model)

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
    ai_message_db = create_message(db=db, message=ai_message, chat_id=chat_id, user_id=None)  # NULL for AI-authored messages

    # Also store AI message in Redis
    ai_message_data = {
        "id": ai_message_db.id,
        "content": ai_message_content,
        "message_type": ai_message.message_type.value if hasattr(ai_message.message_type, 'value') else str(ai_message.message_type),
        "is_ai": True,
        "user_id": None,  # AI-authored; null instead of 0 to avoid a phantom user FK row
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


async def _create_image_message(
    *,
    chat_id: int,
    chat,  # Chat SQLAlchemy row, kept for parity with text path
    message_in: "MessageCreate",
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session,
    current_user: User,
):
    """Persist a user "image request" + the AI's image result.

    The frontend calls `POST /chats/{id}/messages` with
    `message_type='image'` and the prompt in `content`. Style/size/seed
    are pulled from `message_in.meta_data` (a dict on the frontend side)
    so we don't have to grow the public MessageCreate schema.

    Pollinations is best-effort and free, so failures bubble up as 502
    BEFORE the user message is persisted — better to lose the click
    than to leave a "user asked for an image" row with no answer.
    """
    import base64
    from app.api.endpoints.image import generate_image_payload

    # Style/size/seed come in via meta_data so the schema stays the same.
    # Frontend always sends these keys, but tolerate their absence.
    meta_in = message_in.meta_data if isinstance(message_in.meta_data, dict) else {}
    style = meta_in.get("style")
    width = int(meta_in.get("width") or 512)
    height = int(meta_in.get("height") or 512)
    seed = meta_in.get("seed")
    try:
        seed = int(seed) if seed is not None else None
    except (TypeError, ValueError):
        seed = None

    # Clamp size — Pollinations free tier accepts up to ~1024×1024 but
    # larger images blow past our 45 s timeout. Keep this in sync with
    # the chip selector in MessageInput.tsx.
    width = max(256, min(width, 1024))
    height = max(256, min(height, 1024))

    image_id, image_bytes, image_format, gen_meta = generate_image_payload(
        prompt=message_in.content,
        style=style,
        width=width,
        height=height,
        seed=seed,
    )

    image_b64 = base64.b64encode(image_bytes).decode("ascii")

    # Persist the user's "I want an image of X" message first so the
    # conversation reads naturally. message_type='image' so the
    # frontend can render the prompt itself in a styled bubble.
    user_message = create_message(
        db=db,
        message=message_in,  # already has message_type='image' + the prompt in content
        chat_id=chat_id,
        user_id=current_user.id,
    )

    chat_key = f"chat:{chat_id}:messages"
    redis_client.lpush(
        chat_key,
        json.dumps(
            {
                "id": user_message.id,
                "content": message_in.content,
                "message_type": "image",
                "is_ai": False,
                "user_id": current_user.id,
                "created_at": user_message.created_at.isoformat()
                if hasattr(user_message.created_at, "isoformat")
                else str(user_message.created_at),
            }
        ),
    )
    redis_client.ltrim(chat_key, 0, 9)
    redis_client.expire(chat_key, 3600)

    # Now persist the AI's image result. The base64 lives in meta_data so
    # reloading the chat re-renders the image without any extra round trip.
    ai_meta = {
        **gen_meta,
        "image_id": image_id,
        "image_base64": image_b64,
        "image_format": image_format,
        "prompt": message_in.content,
        "user_id": current_user.id,
    }
    ai_message = MessageCreate(
        # Short caption above the image — the frontend renders the
        # image itself from meta_data; this text is the breadcrumb
        # in the conversation timeline and on hover/alt-text.
        content=f"Here is your image of “{message_in.content}”.",
        message_type=MessageType.IMAGE,
        is_ai=True,
        meta_data=ai_meta,
    )
    ai_message_db = create_message(
        db=db,
        message=ai_message,
        chat_id=chat_id,
        user_id=None,  # NULL for AI-authored messages
    )

    ai_message_data = {
        "id": ai_message_db.id,
        "content": ai_message.content,
        "message_type": "image",
        "is_ai": True,
        "user_id": None,
        "created_at": ai_message_db.created_at.isoformat()
        if hasattr(ai_message_db.created_at, "isoformat")
        else str(ai_message_db.created_at),
    }
    redis_client.lpush(chat_key, json.dumps(ai_message_data))
    redis_client.ltrim(chat_key, 0, 9)

    background_tasks.add_task(update_chat_last_message, db, chat_id)

    # Surface generation metrics so /usage logging picks them up.
    request.state.ai_tokens_used = None  # image gen doesn't use tokens
    request.state.ai_model_used = gen_meta.get("generation_model")

    return ai_message_db


# ----- File-mode helpers (PPT / Word / Code) -------------------------------
#
# These three functions mirror _create_image_message above. Each:
#   1. Skips the LLM codepath
#   2. Calls into app/api/endpoints/files.py for the actual generator
#   3. Persists a user row + AI row, both with message_type preserved
#   4. Pushes both to Redis so the chat history reads naturally
#   5. Schedules update_chat_last_message
#   6. Sets request.state.ai_tokens_used / ai_model_used for /usage
#
# We keep the file payload in meta_data (base64) so reloading the chat
# re-renders without a round trip. For PPT/Word the payload is small
# enough (<200 KiB) to live there. For code we store the source itself
# (often <2 KiB) plus stdout/stderr.


async def _create_pptx_message(
    *,
    chat_id: int,
    chat,
    message_in: "MessageCreate",
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session,
    current_user: User,
):
    """Persist a user "make me a slide deck" + the AI's .pptx result."""
    import base64
    from app.api.endpoints.files import generate_pptx_payload, file_b64

    meta_in = message_in.meta_data if isinstance(message_in.meta_data, dict) else {}
    theme = (meta_in.get("theme") or "modern").lower()
    slide_count = int(meta_in.get("slide_count") or 6)
    model_name = message_in.model or "NovaMind-Chat"

    payload_bytes, filename, gen_meta = await generate_pptx_payload(
        prompt=message_in.content,
        theme=theme,
        slide_count=slide_count,
        model_name=model_name,
    )

    # Persist user message first so the conversation reads naturally.
    user_message = create_message(
        db=db,
        message=message_in,
        chat_id=chat_id,
        user_id=current_user.id,
    )

    chat_key = f"chat:{chat_id}:messages"
    redis_client.lpush(
        chat_key,
        json.dumps(
            {
                "id": user_message.id,
                "content": message_in.content,
                "message_type": "file",
                "is_ai": False,
                "user_id": current_user.id,
                "created_at": user_message.created_at.isoformat()
                if hasattr(user_message.created_at, "isoformat")
                else str(user_message.created_at),
            }
        ),
    )
    redis_client.ltrim(chat_key, 0, 9)
    redis_client.expire(chat_key, 3600)

    ai_meta = {
        **gen_meta,
        "file_b64": file_b64(payload_bytes),
        "user_id": current_user.id,
    }
    ai_message = MessageCreate(
        content=f"Here is your presentation, “{message_in.content}”.",
        message_type=MessageType.FILE,
        is_ai=True,
        meta_data=ai_meta,
    )
    ai_message_db = create_message(
        db=db,
        message=ai_message,
        chat_id=chat_id,
        user_id=None,
    )

    ai_message_data = {
        "id": ai_message_db.id,
        "content": ai_message.content,
        "message_type": "file",
        "is_ai": True,
        "user_id": None,
        "created_at": ai_message_db.created_at.isoformat()
        if hasattr(ai_message_db.created_at, "isoformat")
        else str(ai_message_db.created_at),
    }
    redis_client.lpush(chat_key, json.dumps(ai_message_data))
    redis_client.ltrim(chat_key, 0, 9)

    background_tasks.add_task(update_chat_last_message, db, chat_id)

    request.state.ai_tokens_used = None
    request.state.ai_model_used = gen_meta.get("model_used")
    return ai_message_db


async def _create_docx_message(
    *,
    chat_id: int,
    chat,
    message_in: "MessageCreate",
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session,
    current_user: User,
):
    """Persist a user "draft me a document" + the AI's .docx result."""
    from app.api.endpoints.files import generate_docx_payload, file_b64

    meta_in = message_in.meta_data if isinstance(message_in.meta_data, dict) else {}
    style = (meta_in.get("style") or "report").lower()
    theme = (meta_in.get("theme") or "modern").lower()
    model_name = message_in.model or "NovaMind-Chat"

    payload_bytes, filename, gen_meta = generate_docx_payload(
        prompt=message_in.content,
        style=style,
        theme=theme,
        model_name=model_name,
    )

    user_message = create_message(
        db=db,
        message=message_in,
        chat_id=chat_id,
        user_id=current_user.id,
    )

    chat_key = f"chat:{chat_id}:messages"
    redis_client.lpush(
        chat_key,
        json.dumps(
            {
                "id": user_message.id,
                "content": message_in.content,
                "message_type": "file",
                "is_ai": False,
                "user_id": current_user.id,
                "created_at": user_message.created_at.isoformat()
                if hasattr(user_message.created_at, "isoformat")
                else str(user_message.created_at),
            }
        ),
    )
    redis_client.ltrim(chat_key, 0, 9)
    redis_client.expire(chat_key, 3600)

    ai_meta = {
        **gen_meta,
        "file_b64": file_b64(payload_bytes),
        "user_id": current_user.id,
    }
    ai_message = MessageCreate(
        content=f"Here is your document, “{message_in.content}”.",
        message_type=MessageType.FILE,
        is_ai=True,
        meta_data=ai_meta,
    )
    ai_message_db = create_message(
        db=db,
        message=ai_message,
        chat_id=chat_id,
        user_id=None,
    )

    ai_message_data = {
        "id": ai_message_db.id,
        "content": ai_message.content,
        "message_type": "file",
        "is_ai": True,
        "user_id": None,
        "created_at": ai_message_db.created_at.isoformat()
        if hasattr(ai_message_db.created_at, "isoformat")
        else str(ai_message_db.created_at),
    }
    redis_client.lpush(chat_key, json.dumps(ai_message_data))
    redis_client.ltrim(chat_key, 0, 9)

    background_tasks.add_task(update_chat_last_message, db, chat_id)

    request.state.ai_tokens_used = None
    request.state.ai_model_used = gen_meta.get("model_used")
    return ai_message_db


async def _create_code_message(
    *,
    chat_id: int,
    chat,
    message_in: "MessageCreate",
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session,
    current_user: User,
):
    """Persist a user "run this code" + the AI's run result.

    Unlike PPT/Word we don't return a downloadable file — the AI
    message is the source code + its stdout/stderr, and the frontend
    renders that as a code block with a Play / "run again" affordance.
    """
    from app.api.endpoints.files import generate_code_payload

    meta_in = message_in.meta_data if isinstance(message_in.meta_data, dict) else {}
    language = (meta_in.get("language") or "python").lower()
    model_name = message_in.model or "NovaMind-Code"
    timeout_s = float(meta_in.get("timeout_s") or 8.0)

    result, gen_meta = generate_code_payload(
        prompt=message_in.content,
        language=language,
        model_name=model_name,
        timeout_s=timeout_s,
    )

    user_message = create_message(
        db=db,
        message=message_in,
        chat_id=chat_id,
        user_id=current_user.id,
    )

    chat_key = f"chat:{chat_id}:messages"
    redis_client.lpush(
        chat_key,
        json.dumps(
            {
                "id": user_message.id,
                "content": message_in.content,
                "message_type": "code",
                "is_ai": False,
                "user_id": current_user.id,
                "created_at": user_message.created_at.isoformat()
                if hasattr(user_message.created_at, "isoformat")
                else str(user_message.created_at),
            }
        ),
    )
    redis_client.ltrim(chat_key, 0, 9)
    redis_client.expire(chat_key, 3600)

    # Persist the actual run result. `code_runner.CodeRunResult.to_meta()`
    # produces a JSON-safe dict; we merge in the generator metadata so
    # the chat page can show "language: python, 234 ms".
    run_meta = result.to_meta()
    ai_meta = {
        **gen_meta,
        **run_meta,
        "user_id": current_user.id,
    }

    # Build a short human-readable caption. The frontend renders the
    # full code + stdout in the bubble; this is the breadcrumb.
    if result.runtime_missing:
        caption = f"I couldn't run the {language} code: {result.stderr or 'missing runtime'}."
    elif result.timed_out:
        caption = f"Code execution timed out after {result.elapsed_ms} ms."
    elif result.exit_code == 0:
        first_line = (result.stdout or "").splitlines()[0] if result.stdout else ""
        caption = f"Ran successfully in {result.elapsed_ms} ms"
        if first_line:
            caption += f" — first line: {first_line[:80]}"
    else:
        caption = f"Code exited with code {result.exit_code}."

    ai_message = MessageCreate(
        content=caption,
        message_type=MessageType.CODE,
        is_ai=True,
        meta_data=ai_meta,
    )
    ai_message_db = create_message(
        db=db,
        message=ai_message,
        chat_id=chat_id,
        user_id=None,
    )

    ai_message_data = {
        "id": ai_message_db.id,
        "content": ai_message.content,
        "message_type": "code",
        "is_ai": True,
        "user_id": None,
        "created_at": ai_message_db.created_at.isoformat()
        if hasattr(ai_message_db.created_at, "isoformat")
        else str(ai_message_db.created_at),
    }
    redis_client.lpush(chat_key, json.dumps(ai_message_data))
    redis_client.ltrim(chat_key, 0, 9)

    background_tasks.add_task(update_chat_last_message, db, chat_id)

    request.state.ai_tokens_used = None
    request.state.ai_model_used = gen_meta.get("model_used")
    return ai_message_db