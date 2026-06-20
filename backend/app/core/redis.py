import redis
from app.core.config import settings

redis_client = redis.from_string(settings.REDIS_URL, decode_responses=True)