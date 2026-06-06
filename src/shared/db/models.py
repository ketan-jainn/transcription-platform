import uuid
from enum import Enum as PyEnum
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    Enum,
    ForeignKey,
    DateTime,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from src.shared.db.base import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


class JobStatus(PyEnum):
    PENDING_UPLOAD = "PENDING_UPLOAD"
    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DLQ = "DLQ"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(128), nullable=False, index=True)
    status = Column(Enum(JobStatus, native_enum=False), nullable=False, default=JobStatus.PENDING_UPLOAD)
    s3_prefix = Column(String(1024), nullable=True)  # e.g. {job_id}/chunks/
    chunk_count = Column(Integer, nullable=True)
    idempotency_key = Column(String(255), nullable=True, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    chunks = relationship("Chunk", back_populates="job", cascade="all, delete-orphan", lazy="selectin")
    segments = relationship("Segment", back_populates="job", cascade="all, delete-orphan", lazy="selectin")


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("job_id", "index", name="uq_chunks_job_index"),
        Index("ix_chunks_job_index", "job_id", "index"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid)
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    index = Column(Integer, nullable=False)  # chunk index within job
    s3_key = Column(String(1024), nullable=False)
    status = Column(String(32), nullable=False, default="PENDING")
    retry_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    job = relationship("Job", back_populates="chunks")


class Segment(Base):
    __tablename__ = "segments"
    __table_args__ = (
        UniqueConstraint("job_id", "chunk_index", "seq", name="uq_segments_job_chunk_seq"),
        Index("ix_segments_job_chunk", "job_id", "chunk_index"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid)
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    seq = Column(Integer, nullable=False)  # ordering within chunk
    start_ms = Column(Integer, nullable=True)
    end_ms = Column(Integer, nullable=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    job = relationship("Job", back_populates="segments")