# Infrastructure

## Purpose
House Docker Compose, Kubernetes manifests, and deployment notes that tie the Phase 1 services together.

## Getting Started
1. Copy the example compose files when ready.
2. Ensure networking between frontend (port 3000), backend (8000), PostgreSQL, Redis, and Celery.
3. Document environment variables, secrets, and observability hooks here.

## Focus Areas for Phase 1
- Define a minimal Docker Compose bringing up backend, Redis, PostgreSQL, and worker services.
- Outline CI/CD steps for deploying Phase 1 services to staging/K8s.
- Track monitoring hooks (logs, alerts, metrics).

