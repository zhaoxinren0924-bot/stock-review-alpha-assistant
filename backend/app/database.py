"""Database configuration and session management."""

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Resolve absolute path so the DB is always at project-root/data/ regardless
# of where the server is started from.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DB_DIR = os.path.join(_PROJECT_ROOT, "data")
_DB_PATH = os.path.join(_DB_DIR, "portfolio.db")

# Ensure data directory exists (needed for Render deployment)
os.makedirs(_DB_DIR, exist_ok=True)

# Allow override via environment variable (Render, Docker, etc.)
SQLALCHEMY_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{_DB_PATH}",
)

connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator:
    """Yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
