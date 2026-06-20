from fastapi import FastAPI
from app.core.config import settings
from app.api.v1 import api_router
from app.db.database import Base, engine

# Create tables
Base.metadata.create_all(bind=engine)

# Create initial admin user if no users exist
def create_initial_admin():
    from app.db.database import SessionLocal
    from app.models.user import User
    from app.schemas.user import UserCreate
    from app.core.security import get_password_hash

    db = SessionLocal()
    try:
        # Check if any users exist
        user_count = db.query(User).count()
        if user_count == 0:
            # Create admin user
            admin_in = UserCreate(
                email="admin@novamind.ai",
                password="admin123",  # In production, use strong password and force change
                username="admin",
                full_name="System Administrator",
                is_admin=True
            )
            hashed_password = get_password_hash(admin_in.password)
            admin_user = User(
                email=admin_in.email,
                username=admin_in.username,
                full_name=admin_in.full_name,
                hashed_password=hashed_password,
                is_admin=True,
                is_active=True,
                is_verified=True
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            print("Created initial admin user: admin@novamind.ai")
    except Exception as e:
        print(f"Error creating initial admin: {e}")
    finally:
        db.close()

create_initial_admin()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Initialize audit logger
from app.core.audit_logging import init_audit_logger
import os
# Create logs directory if it doesn't exist
os.makedirs("/app/logs", exist_ok=True)
init_audit_logger("/app/logs/audit.log")

# Add rate limiting middleware
from app.core.rate_limiting import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware(exclude_paths=["/docs", "/redoc", "/openapi.json"]))

# Add usage logging middleware
from app.core.usage_logging import UsageLoggingMiddleware
app.add_middleware(UsageLoggingMiddleware(exclude_paths=["/docs", "/redoc", "/openapi.json", "/favicon.ico"]))

# Add security audit logging middleware (would be implemented as a middleware in production)
# For now, we'll log through the audit logger directly in endpoints

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {"message": "Welcome to NovaMind AI"}