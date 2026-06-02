from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres_password@localhost:5432/omniscribe_db"
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_BUCKET: str = "omniscribe-chunks"
    S3_ACCESS_KEY: Optional[str] = "minio_admin"
    S3_SECRET_KEY: Optional[str] = "minio_password"
    REDIS_URL: str = "redis://localhost:6379/0"
    LOG_LEVEL: str = "info"
    # Optional path to an ops YAML config for non-code defaults
    CONFIG_FILE: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
