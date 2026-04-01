# Database

## Purpose
Contain schema definitions, migrations, and sample data needed to capture vendors, products, relationships, leads, and logs.

## Getting Started
1. Keep the core schema in schema.sql and version it via migrations.
2. Load reference data for vendor categories, consent types, and communication channels.
3. Track updates in migration notes so Phase 1 dashboards have consistent data.

## Focus Areas for Phase 1
- Define tables for vendors, products, deduplication metadata, and audit logs.
- Model relationship stages, consent flags, and marketing preferences.
- Provide sample SQL for ingestion tests that the backend and workers can reuse.

