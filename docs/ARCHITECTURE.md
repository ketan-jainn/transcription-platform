
# Omniscribe Architecture

This document describes the architecture, components, data flows, failure modes, and operational runbook for the Omniscribe async transcription platform. It follows the phased roadmap in the project plan (Phase 0 → Phase 4). Use this as the single source of architectural truth for design decisions and future changes.

## One-sentence system summary
Users upload large audio/video files → chunks land in S3 (MinIO locally) → API publishes chunk work to Kafka ingress → a scheduler (passthrough or fair-share) forwards to the jobs topic → workers consume jobs, download chunks from S3, run faster-whisper, publish segments → API streams segments to clients over WebSocket and stores results in Postgres.

---

## High-level components

- `api` (FastAPI): HTTP endpoints, presigned uploads or chunk endpoints, job creation, WebSocket streaming, and readiness/health checks. Writes job metadata to Postgres and publishes chunk messages to `transcription.ingress`.
- `scheduler` (Phase 1 passthrough → Phase 3 fair-share): consumes `transcription.ingress`, enforces fairness/rate limits via Redis (in Phase 3), and publishes selected messages to `transcription.jobs`.
- `worker` (whisper-workers): consumes `transcription.jobs`, downloads chunk from S3, transcribes with `faster-whisper`, publishes `transcription.segments`, and persists segments to Postgres.
- `shared`: Pydantic message schemas, topic name constants, DB models, Kafka wrappers and retry helpers used by all services.
- Infra: Postgres (metadata), MinIO (S3), Redpanda (Kafka-compatible), Redis (rate limits, scheduler state, pub/sub for WS), Docker Compose for local dev and Terraform/ECS for production.

---

## Kafka topics and their purpose

- `transcription.ingress` — messages created by the API for each chunk uploaded. Raw arrival order.
- `transcription.jobs` — work chosen by the scheduler for workers to process (fair interleaving applied here in Phase 3).
- `transcription.segments` — results produced by workers: timestamped text segments for a chunk (consumed by API for streaming/persistence and other consumers).
- `transcription.jobs.retry.30s`, `transcription.jobs.retry.5m` — delayed retry lanes implementing exponential backoff.
- `transcription.dlq` — dead letter queue for permanently failed messages.

Notes: in local dev topics can be single-partition, single-replica. In production increase partitions for throughput and replication_factor for durability.

---

## Data flow (end-to-end)

1. Client calls `POST /v1/jobs` with `Idempotency-Key` header. API writes a `jobs` row in Postgres with status `PENDING_UPLOAD`.
2. Client uploads file in chunks to S3: `s3://<bucket>/{job_id}/chunks/{n}`. API updates manifest in DB and sets job `UPLOADED` once complete.
3. For each chunk the API publishes a small JSON message to `transcription.ingress`:
	```json
	{ "job_id": "...", "chunk_index": 0, "s3_key": "...", "user_id": "...", "attempt": 0 }
	```
4. Scheduler consumes `transcription.ingress` and —
	- Phase 1: passthrough publishes the same message to `transcription.jobs`
	- Phase 3: fair-share uses Redis DRR & in-flight caps to decide when to publish to `transcription.jobs`.
5. Workers (consumer group `whisper-workers`) consume `transcription.jobs`, download chunk, run `faster-whisper`, then publish `transcription.segments` and write the segment rows to Postgres (idempotent write: UNIQUE(job_id, chunk_index, seq)). Only after successful DB write the worker commits the offset.
6. API subscribes (or uses Redis pub/sub when multi-replica) to `transcription.segments` and forwards incoming segments over the WebSocket `ws://.../v1/jobs/{id}/stream` to connected clients. On reconnect the API can replay from Postgres.
7. When all chunks are processed, job status becomes `COMPLETED`; if a chunk repeatedly fails it moves to DLQ and job may become `FAILED`.

---

## Job lifecycle and states

- `PENDING_UPLOAD` — job created, awaiting client uploads
- `UPLOADED` — manifest complete in Postgres
- `QUEUED` — chunk messages published to `transcription.ingress`
- `PROCESSING` — worker is actively transcribing chunk(s)
- `COMPLETED` — all chunks processed and segments persisted
- `FAILED` — fatal error preventing completion
- `DLQ` — chunk message moved to dead-letter queue after retries

---

## Postgres schema (summary)

- `users` (id PK, plan, rate_limit_tier)
- `jobs` (id PK, user_id FK, status, s3_prefix, chunk_count, idempotency_key, created_at, updated_at)
- `chunks` (job_id FK, index, s3_key, status, retry_count)
- `segments` (job_id FK, chunk_index, seq, start_ms, end_ms, text) — UNIQUE(job_id, chunk_index, seq)
- `dlq_events` (job_id, chunk_index, error, payload_json, created_at, replayed_at)

Use Alembic for all migrations; never edit schema by hand in prod.

---

## Reliability: retries, DLQ, idempotency

- Worker errors are categorized as retryable or non-retryable.
- Retry policy (Phase 2): immediate retry on `transcription.jobs`, then publish to `transcription.jobs.retry.30s`, then `transcription.jobs.retry.5m`, finally `transcription.dlq`.
- Messages include headers/fields like `attempt`, `error_class` to track retries.
- Idempotency keys and DB unique constraints prevent duplicate rows on re-delivery.
- `scripts/dlq_replay.py` provides operators a way to inspect DLQ and requeue messages after fixes.

---

## Scheduler: passthrough vs fair-share

- Phase 1: scheduler is a lightweight passthrough consumer/producer. Simple, minimal logic, used to validate pipeline.
- Phase 3: scheduler implements a Deficit Round Robin (DRR) or weighted fair queuing using Redis:
  - Maintain per-user queues and deficit counters.
  - Compute job cost (chunks or approximate MB/10MB).
  - Cap per-user in-flight chunks with Redis semaphores.
  - Publish from per-user queues to `transcription.jobs` in fair order.

Scheduler design goals: keep API and worker message shapes unchanged, so swapping passthrough for DRR requires only scheduler changes.

---

## Observability & health

- Health endpoints (API): `/health/live` (process up) and `/health/ready` (DB + Redis + Kafka connectivity check).
- Metrics to expose (Prometheus): consumer lag, DLQ depth, jobs_completed_total, job_processing_seconds (histogram), fair_share_wait_seconds.
- Logging: structured `structlog` JSON with `job_id` and `user_id` fields.
- Tracing: optional; consider adding lightweight tracing (OpenTelemetry) in Phase 4.

---

## Deployment

- Local dev: `docker compose -f deploy/docker-compose.yml up -d` brings Postgres, Redis, MinIO, Redpanda. Run `uvicorn src.api.main:app --reload` locally for faster iteration.
- Prod (Phase 4): Terraform provisioning to create S3, RDS, ElastiCache, ECS/Fargate services and ALB. Use Secrets Manager for credentials.

Important production considerations:
- Use MSK or Redpanda cluster with replication_factor ≥ 3.
- Increase partitions for `transcription.jobs` to match worker horizontal scale.
- Use multi-AZ RDS and read replicas if needed for analytics.

---

## Security and config

- Use `pydantic-settings` (`BaseSettings`) to centralize config. Document all vars in `.env.example` and never commit secrets.
- Use presigned S3 URLs for direct client uploads or server-mediated chunking depending on the UI design.
- For multi-tenant isolation, always include `user_id` on messages and DB rows.

---

## Operational runbook (quick)

1. Start local infra:
	```bash
	docker compose -f deploy/docker-compose.yml up -d
	```
2. Create topics (after Redpanda ready):
	```bash
	python scripts/create_topics.py
	```
3. Apply DB migrations:
	```bash
	alembic upgrade head
	```
4. Run API (dev):
	```bash
	uvicorn src.api.main:app --reload --port 8000
	```
5. Run worker & scheduler locally (during development run on host for easier debugging):
	```bash
	python -m src.worker.main
	python -m src.scheduler.main
	```

DLQ replay tip: use `scripts/dlq_replay.py` to inspect, fix, and requeue messages. Record why a DLQ item was replayed in `dlq_events.replayed_at` and comments.

---

## Extensibility and phase boundaries

- Keep `shared` models authoritative (Pydantic + SQLAlchemy) to avoid divergent JSON shapes.
- Avoid calling Whisper from the API; worker separation enables scaling and a clean migration to GPU workers in Phase 5.
- Phase changes:
  - Phase 1: passthrough scheduler, core pipeline working end-to-end.
  - Phase 2: add retry topics, DLQ, idempotent writes, and `dlq_replay.py`.
  - Phase 3: replace passthrough scheduler with Redis DRR fair-share implementation.
  - Phase 4: Terraform + AWS ECS + monitoring and production hardening.

---

## Appendix: Messaging example

- Chunk job message (ingress/jobs):
  ```json
  {
	 "job_id": "uuid",
	 "chunk_index": 0,
	 "s3_key": "job-uuid/chunks/0.bin",
	 "user_id": "user-123",
	 "attempt": 0
  }
  ```

- Segment message (segments):
  ```json
  {
	 "job_id": "uuid",
	 "chunk_index": 0,
	 "seq": 1,
	 "start_ms": 0,
	 "end_ms": 1200,
	 "text": "Hello world"
  }
  ```

---