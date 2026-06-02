# Learning notes

- Architecture boxes: API (FastAPI), Scheduler (passthrough → fair-share), Worker (Whisper), Shared (models + kafka topics), Infra (Postgres, Redis, MinIO, Redpanda).
- Today: scaffolded health endpoints, topic constants, create_topics script, and a test.
- Next: wire `shared` models and add DB models + Alembic initial migration.
