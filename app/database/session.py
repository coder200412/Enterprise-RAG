"""
SQLAlchemy database engine, session factory, and base model.
Configured for PostgreSQL.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings


engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def get_db():
    """
    FastAPI dependency that provides a database session.
    Yields a session and ensures it is closed after the request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all database tables."""
    # Import all models so they register with Base.metadata
    import app.auth.models  # noqa: F401
    import app.documents.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
