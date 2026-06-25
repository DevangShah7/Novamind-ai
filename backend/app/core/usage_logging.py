import time
from typing import Optional, Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from app.core.database import SessionLocal
from app.crud.api_usage import create_api_usage
from app import models
import json


class UsageLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        exclude_paths: Optional[list] = None
    ):
        """
        Middleware to log API usage for analytics and tracking.

        Args:
            app: ASGI application
            exclude_paths: List of paths to exclude from usage logging
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/docs", "/redoc", "/openapi.json", "/favicon.ico"]

    async def dispatch(self, request: Request, call_next):
        # Skip usage logging for excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)

        # Record start time
        start_time = time.time()

        # Extract request information
        endpoint = request.url.path
        method = request.method
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        # Try to get user information from request state (set by auth middleware)
        user_id = None
        api_key_id = None

        # Check if user is authenticated via JWT or API key
        user = getattr(request.state, "user", None)
        if user and hasattr(user, 'id'):
            user_id = user.id

            # If user came from API key, try to get the API key ID
            # This is a bit tricky since we don't store which API key was used in the user object
            # We could look up the most recently used API key for this user, but that's not accurate
            # For now, we'll leave api_key_id as None and rely on the API key increment mechanism
            # Or we could extract it from the request headers if it's an API key request

            # Check for API key in headers
            api_key_header = request.headers.get("X-API-Key")
            if api_key_header:
                # We'll look up the API key in the database to get its ID
                # This adds a DB query but it's for usage logging so it's acceptable
                db = SessionLocal()
                try:
                    api_key_obj = db.query(models.ApiKey).filter(
                        models.ApiKey.key == api_key_header,
                        models.ApiKey.is_active == True
                    ).first()
                    if api_key_obj:
                        api_key_id = api_key_obj.id
                except Exception:
                    pass  # If we can't look it up, continue without api_key_id
                finally:
                    db.close()

        # Process request
        response = await call_next(request)

        # Calculate response time
        process_time = time.time() - start_time
        response_time_ms = int(process_time * 1000)

        # Extract response information
        status_code = response.status_code

        # Get AI-specific metrics from request state (set by endpoints)
        tokens_used = getattr(request.state, "ai_tokens_used", None)
        model_used = getattr(request.state, "ai_model_used", None)

        # Create usage log entry in a separate database session
        # We do this after the response is sent to avoid blocking the request
        # In a production system, you might want to use a message queue
        db = SessionLocal()
        try:
            create_api_usage(
                db=db,
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                user_id=user_id,
                api_key_id=api_key_id,
                ip_address=ip_address,
                user_agent=user_agent,
                response_time_ms=response_time_ms,
                tokens_used=tokens_used,
                model_used=model_used
            )
        except Exception:
            # Don't let usage logging errors break the main request
            pass
        finally:
            db.close()

        return response