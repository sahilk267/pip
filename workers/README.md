# Workers (Celery)

## Purpose
Run periodic vendor/product enrichment, scraping, deduplication, and alerting tasks for Phase 1 data foundations.

## Getting Started
1. Install dependencies: pip install -r requirements.txt (shared with backend).
2. Start Redis broker and run: celery -A workers.app worker --loglevel=info.

## Focus Areas for Phase 1
- Schedule daily enrichment jobs that refresh vendor metadata, product catalogs, and customer consent markers.
- Implement deduplication heuristics and retries with exponential backoff.
- Emit alerts when scraping pipelines encounter structural changes or legal flags.
- Integrate with the backend audit logger for traceability.

