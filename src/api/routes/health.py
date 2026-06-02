from fastapi import APIRouter
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from src.shared.log import get_logger
from src.shared.config import settings

logger = get_logger(__name__)
router = APIRouter()


@router.get("/health/live")
async def live():
    return {"status": "ok"}


@router.get("/health/ready")
async def ready():
    database_url = settings.DATABASE_URL
    logger.info("Performing readiness check", db=database_url)

    if not database_url:
        logger.warning("Database URL is not configured")
        return {"status": "ok", "db": "not-configured"}

    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "ok"}
    except OperationalError:
        logger.error("Database is unreachable")
        return {"status": "error", "db": "unreachable"}