# Enrichment Path Overview

This note captures the Phase 1 enrichment flow now that discovery connectors and Celery tasks are in place. It bridges the backend implementation and onboarding guidance so the team can move from stub data to real revenue/decision-maker APIs.

## Flow
1. `run_discovery` (`backend/app/services/discovery.py`) gathers vendor/product payloads from the LinkedIn, IndiaMART, Google Maps, and supplier catalog connectors and persists them via the ingestion endpoints (`/api/v1/vendors`, `/api/v1/products`).
2. `run_enrichment` (`backend/app/services/enrichment.py`) looks up sample metadata keyed by normalized vendor names, merges it into `vendor_metadata`, and logs how many vendors were enriched.
3. Celery workers (`backend/app/tasks.py`) trigger the enrichment job via the `enrich_vendor_profiles` task, which in turn calls `run_enrichment` and records the action in the audit log.
4. Quality/monitoring jobs (`compute_data_quality_metrics`, `monitor_data_sources`) log inventory counts and connector health, raise alerts for failures/schema drift, and feed the monitoring dashboard.

## Status and Next Steps
- **Implemented in Phase 1 (stub enrichment)**: CSV-backed B2B/B2C enrichment and optional HTTP fallback (`B2B_ENRICHMENT_API`, `B2C_ATTRIBUTE_API`) are active, with Celery scheduling and audit logging.
- **Next**: Replace fixture feeds with production firmographic/product providers, standardize revenue band taxonomy, and expand source-level quality scoring.
- **Monitoring status**: `monitor_data_sources` plus `GET /api/v1/monitoring/dashboard` already surface connector health, recent alerts, and audit telemetry.

## References
- `backend/app/services/enrichment.py` and `backend/app/services/monitoring.py`
- `backend/app/tasks.py` for scheduled jobs
- `PHASE-1-IMPLEMENTATION-PLAN.md` for status tracking
