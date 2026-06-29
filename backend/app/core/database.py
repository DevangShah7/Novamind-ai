from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# SQLite needs check_same_thread=False because FastAPI dispatches sync
# endpoints across a thread pool — each request may run in a different
# thread than the one that opened the session. Postgres doesn't need this
# and we don't want to set it (it raises on the libpq driver).
_connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

# pool_pre_ping=True issues a cheap SELECT 1 before each checkout so a
# connection that the server (e.g. Neon) closed during idle doesn't blow up
# the first request after cold-start. pool_recycle forces fresh connections
# before any platform-level idle-kill kicks in (Neon closes idle conns at ~5min).
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
    pool_recycle=280,  # < Neon's ~5min idle timeout
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()