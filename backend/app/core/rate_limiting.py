import time
from typing import Optional, Callable
from fastapi import Request, HTTPException, Response
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse
from app.core.redis import get_redis
import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        times: int = 100,
        seconds: int = 60,
        auth_times: Optional[int] = None,
        exclude_paths: Optional[list] = None
    ):
        """
        Rate limiting middleware using Redis sliding window counter.

        Args:
            app: ASGI application
            times: Number of allowed requests per window for most endpoints
            seconds: Time window in seconds
            auth_times: Optional tighter limit for /auth/* endpoints
            exclude_paths: List of paths to exclude from rate limiting
        """
        super().__init__(app)
        self.times = times
        self.seconds = seconds
        self.auth_times = auth_times or max(10, times // 10)
        self.exclude_paths = exclude_paths or []
        self.redis_prefix = "rate_limit"

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for excluded paths
        if request.url.path in self.exclude_paths:
            response = await call_next(request)
            return response

        # Get Redis connection
        redis_client = get_redis()
        if not redis_client:
            # If Redis is not available, allow the request (fail open)
            response = await call_next(request)
            return response

        # Determine rate limit configuration based on request
        times, seconds = self._get_rate_limit_config(request)

        # Get client identifier (IP address or user ID if authenticated)
        client_id = self._get_client_id(request)

        # Current timestamp
        now = time.time()
        window_start = now - seconds

        # Redis key for this client
        key = f"{self.redis_prefix}:{client_id}"

        # Remove outdated entries
        redis_client.zremrangebyscore(key, 0, window_start)

        # Count current requests
        current_count = redis_client.zcard(key)

        # Check if rate limit exceeded
        if current_count >= times:
            # Rate limit exceeded
            # Calculate retry-after header
            oldest_entry = redis_client.zrange(key, 0, 0, withscores=True)
            if oldest_entry:
                oldest_timestamp = oldest_entry[0][1]
                retry_after = int(seconds - (now - oldest_timestamp))
            else:
                retry_after = seconds

            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(retry_after)}
            )

        # Add current request
        redis_client.zadd(key, {str(now): now})
        redis_client.expire(key, seconds)

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        remaining = max(0, times - current_count - 1)  # -1 for current request
        reset_time = int(now + seconds)

        response.headers["X-RateLimit-Limit"] = str(times)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)

        return response

    def _get_rate_limit_config(self, request: Request) -> tuple[int, int]:
        """Get rate limit configuration based on request"""
        # Auth endpoints get the tighter, dedicated bucket.
        if request.url.path.startswith("/auth/"):
            return self.auth_times, self.seconds

        # Default limit for everything else.
        return self.times, self.seconds

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting"""
        # Try to get authenticated user ID first
        # This requires authentication middleware to run before this middleware
        user = getattr(request.state, "user", None)
        if user and hasattr(user, 'id'):
            return f"user:{user.id}"

        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0]
        else:
            ip = request.client.host if request.client else "unknown"

        return f"ip:{ip}"


# Convenience function to create rate limiter with different configurations
def create_rate_limiter(
    times: int = 100,
    seconds: int = 60,
    exclude_paths: Optional[list] = None
) -> RateLimitMiddleware:
    """Create a rate limiter middleware instance"""
    return lambda app: RateLimitMiddleware(app, times=times, seconds=seconds, exclude_paths=exclude_paths)


# Pre-configured limiters
def create_default_rate_limiter(exclude_paths: Optional[list] = None) -> RateLimitMiddleware:
    """Create default rate limiter: 100 requests per minute"""
    return lambda app: RateLimitMiddleware(app, times=100, seconds=60, exclude_paths=exclude_paths)


def create_auth_rate_limiter(exclude_paths: Optional[list] = None) -> RateLimitMiddleware:
    """Create strict rate limiter for auth endpoints: 10 requests per minute"""
    return lambda app: RateLimitMiddleware(app, times=10, seconds=60, exclude_paths=exclude_paths)


def create_api_key_rate_limiter(exclude_paths: Optional[list] = None) -> RateLimitMiddleware:
    """Create generous rate limiter for API key users: 1000 requests per minute"""
    return lambda app: RateLimitMiddleware(app, times=1000, seconds=60, exclude_paths=exclude_paths)