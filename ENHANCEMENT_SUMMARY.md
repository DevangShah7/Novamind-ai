# Enhanced NovaMind AI with Short-Term Memory System

## 1. Folder Structure Changes
```
/c/Users/DEVANG/novamind-ai/backend/app/core/redis.py  [NEW]
/c/Users/DEVANG/novamind-ai/backend/app/api/endpoints/chats.py  [MODIFIED]
```

## 2. File Names
- backend/app/core/redis.py
- backend/app/api/endpoints/chats.py

## 3. Complete Code

### backend/app/core/redis.py
```python
import redis
from app.core.config import settings

redis_client = redis.from_string(settings.REDIS_URL, decode_responses=True)
```

### backend/app/api/endpoints/chats.py (Modified Sections)
```python
from app.core.redis import redis_client
import json

# In create_message_endpoint function:
# Store conversation context in Redis (short-term memory)
chat_key = f"chat:{chat_id}:messages"
message_data = {
    "id": user_message.id,
    "content": message_in.content,
    "is_ai": False,
    "created_at": user_message.created_at.isoformat() if hasattr(user_message.created_at, 'isoformat') else str(user_message.created_at)
}

# Add to Redis list, keep last 10 messages
redis_client.lpush(chat_key, json.dumps(message_data))
redis_client.ltrim(chat_key, 0, 9)  # Keep only last 10 messages
redis_client.expire(chat_key, 3600)  # Expire after 1 hour

# Get conversation history for AI context
message_history = []
stored_messages = redis_client.lrange(chat_key, 0, -1)
for stored_msg in reversed(stored_messages):  # Reverse to get chronological order
    try:
        msg_data = json.loads(stored_msg)
        message_history.append(msg_data)
    except:
        pass

# Generate AI response with context (still mocked, but now uses history)
context_summary = f"Previous conversation ({len(message_history)} messages): "
if message_history:
    recent_topics = [msg["content"][:50] + "..." if len(msg["content"]) > 50 else msg["content"]
                    for msg in message_history[-3:]]  # Last 3 messages
    context_summary += " | ".join(recent_topics)
else:
    context_summary = "No previous messages"

ai_message_content = f"AI response to: {message_in.content}\n\n[Context: {context_summary}]"
ai_message = MessageCreate(content=ai_message_content, is_ai=True)
ai_message_db = create_message(db=db, message=ai_message, chat_id=chat_id)

# Also store AI message in Redis
ai_message_data = {
    "id": ai_message_db.id,
    "content": ai_message_content,
    "is_ai": True,
    "created_at": ai_message_db.created_at.isoformat() if hasattr(ai_message_db.created_at, 'isoformat') else str(ai_message_db.created_at)
}
redis_client.lpush(chat_key, json.dumps(ai_message_data))
redis_client.ltrim(chat_key, 0, 9)
```

## 4. Commands To Run
```bash
# Start enhanced services
docker-compose up --build

# Test memory functionality:
# 1. Register/login at http://localhost:3000
# 2. Create a new chat
# 3. Send multiple messages
# 4. Observe that AI responses include conversation history context
```

## 5. Deployment Files
- docker-compose.yml (already includes Redis service)
- No additional deployment files needed