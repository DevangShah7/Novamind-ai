"""Redis client with graceful fallback when Redis is unavailable.

If REDIS_URL points at an unreachable host (e.g. SQLite-only deployment),
we fall back to a no-op in-memory shim so endpoints that use the cache
don't crash the app. Set REDIS_REQUIRED=1 to force a hard failure on
connection errors instead.
"""
import logging

try:
    import redis
except ImportError:  # pragma: no cover - redis should always be installed
    redis = None

from app.core.config import settings

log = logging.getLogger(__name__)


class _NullRedis:
    """In-process shim with the same surface we use. Lets the app run
    without a Redis server (single-user / demo / free-tier deployments)."""

    def __init__(self):
        self._store: dict[str, str] = {}

    # String ops
    def get(self, key):
        return self._store.get(key)

    def set(self, key, value, ex=None, px=None, nx=False, xx=False):
        if nx and key in self._store:
            return None
        if xx and key not in self._store:
            return None
        self._store[key] = value
        return True

    def setex(self, key, time, value):
        self._store[key] = value
        return True

    def delete(self, *keys):
        n = 0
        for k in keys:
            if k in self._store:
                del self._store[k]
                n += 1
        return n

    def exists(self, key):
        return int(key in self._store)

    def expire(self, key, time):
        return 1 if key in self._store else 0

    def keys(self, pattern="*"):
        # very small wildcard impl, fine for demo use
        if pattern == "*":
            return list(self._store.keys())
        return [k for k in self._store if pattern.replace("*", "") in k]

    def ttl(self, key):
        return -1 if key in self._store else -2

    # Hash ops
    def hget(self, name, key):
        return self._store.get(f"{name}::{key}")

    def hset(self, name, key=None, value=None, mapping=None):
        if mapping:
            for k, v in mapping.items():
                self._store[f"{name}::{k}"] = v
        if key is not None:
            self._store[f"{name}::{key}"] = value
        return 1

    def hgetall(self, name):
        prefix = f"{name}::"
        return {k[len(prefix):]: v for k, v in self._store.items() if k.startswith(prefix)}

    def hdel(self, name, *keys):
        return self.delete(*(f"{name}::{k}" for k in keys))

    # Misc
    def ping(self):
        return True

    def incr(self, key, amount=1):
        cur = int(self._store.get(key, 0))
        cur += amount
        self._store[key] = str(cur)
        return cur

    def close(self):
        pass

    # Sorted-set ops (sliding-window rate limiter needs these)
    def _zs(self, key):
        z = self._store.get(key)
        if isinstance(z, list):
            return z  # already a sorted-set representation
        return []

    def zadd(self, key, mapping):
        if not isinstance(mapping, dict):
            mapping = {str(mapping): 0.0}
        existing = self._zs(key)
        scores = {member: float(score) for member, score in existing}
        for member, score in mapping.items():
            scores[str(member)] = float(score)
        self._store[key] = [(m, s) for m, s in scores.items()]
        return len(mapping)

    def zremrangebyscore(self, key, min_score, max_score):
        existing = self._zs(key)
        kept = [(m, s) for m, s in existing if not (float(min_score) <= s <= float(max_score))]
        self._store[key] = kept
        return len(existing) - len(kept)

    def zcard(self, key):
        return len(self._zs(key))

    def zrange(self, key, start, end, withscores=False):
        existing = sorted(self._zs(key), key=lambda x: x[1])
        if end == -1:
            sliced = existing[start:]
        else:
            sliced = existing[start:end + 1]
        if withscores:
            return [(m, s) for m, s in sliced]
        return [m for m, _ in sliced]

    # List ops (chat history uses lpush/ltrim/lrange)
    def _list(self, key):
        v = self._store.get(key)
        if isinstance(v, list):
            return v
        return []

    def lpush(self, key, *values):
        items = self._list(key)
        for v in reversed(values):
            items.insert(0, v)
        self._store[key] = items
        return len(items)

    def lrange(self, key, start, end):
        items = self._list(key)
        if end == -1:
            return items[start:]
        return items[start:end + 1]

    def ltrim(self, key, start, end):
        items = self._list(key)
        if end == -1:
            self._store[key] = items[start:]
        else:
            self._store[key] = items[start:end + 1]
        return True


def _build_client():
    if redis is None:
        log.warning("redis package not installed; using in-memory shim")
        return _NullRedis()
    try:
        client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        log.info("Connected to Redis at %s", settings.REDIS_URL)
        return client
    except Exception as e:
        msg = f"Redis unreachable ({e}); using in-memory shim"
        if getattr(settings, "REDIS_REQUIRED", False):
            raise RuntimeError(msg) from e
        log.warning(msg)
        return _NullRedis()


def get_redis():
    """Return the singleton Redis client (real or in-memory shim).

    Exists so `app.core` can re-export a factory; existing code that uses
    `redis_client` directly keeps working unchanged.
    """
    return redis_client


redis_client = _build_client()