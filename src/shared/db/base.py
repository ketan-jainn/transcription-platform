from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from src.shared.config import settings


# SQLAlchemy engine and session factory
engine = create_engine(settings.DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

# Declarative base for models to inherit from
Base = declarative_base()


def get_db():
    """Yield a database session, use as dependency in FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
