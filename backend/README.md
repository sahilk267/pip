# Backend (FastAPI + PostgreSQL)

## Purpose
Host the ingestion APIs, dedup/validation logic, CRM automation, and audit logging services described in Phase 1.

## Getting Started
1. Create virtualenv or use Poetry.
2. Install dependencies: pip install -r requirements.txt.
3. Run locally: uvicorn app.main:app --reload.
4. Configure DATABASE_URL to point to the PostgreSQL docker instance.

## Focus Areas for Phase 1
- Implement vendor/product ingestion endpoints with validation and deduplication hooks.
- Track communication logs, consent metadata, and relationship stages for CRM dashboards.
- Emit audit logs for every enrichment or manual override action.
- Provide stub data for frontend integration and worker testing.

### Enrichment & Monitoring
- Background Celery workers run `refresh_vendor_metadata`, `enrich_vendor_profiles`, and `monitor_data_sources` to keep vendor metadata fresh, record enrichment activity, and audit connector health.
- These jobs rely on the new enrichment/monitoring service modules so the Phase 1 stack can log how many vendors/products each connector returns.

## Local Docker Compose
- Use docker compose -f infrastructure/docker-compose.yml up --build from the repository root to bring up Postgres, Redis, the backend API, and the Celery worker.
- The Docker image installs dependencies from backend/requirements.txt and runs uvicorn app.main:app. The Celery service uses celery_worker.app as its entry point.

## Sample Data
- Run python backend/scripts/seed_data.py to seed a handful of vendors/products via the ingestion endpoints for manual QA and onboarding demos.
