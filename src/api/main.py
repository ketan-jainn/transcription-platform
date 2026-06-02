from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.shared.config import settings
from src.shared.log import configure_logging, get_logger


from .routes import health

configure_logging()
logger = get_logger(__name__)

app = FastAPI(title="omniscribe API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
    
app.include_router(health.router)


@app.get("/")
async def index():
    return {"service": "omniscribe api", "status": "ok"}


@app.on_event("startup")
async def startup_event():
    # Optionally load env or perform startup tasks here
    env = settings.CONFIG_FILE
    logger.info("Starting omniscribe API", env=settings.CONFIG_FILE)
