# Phase 3 Market Intelligence Implementation Assistant Prompt

## Purpose
This prompt helps an AI assistant implement successive Phase 3 features in the `Procurement Intelligence` codebase (`backend/app`) with complete wired paths: data model, migration, schema, service, router, and tests.

## When to use
- You have a set of remaining Phase 3 checklist items (e.g., A/B testing outreach, automated lead scoring, GDPR/consent management).
- You need a full implementation slice with data persistence, business logic, API endpoints, and tests.

## Prompt
You are a coding assistant working on a FastAPI + SQLAlchemy Python project at `e:/PIP`. Implement the following feature group end-to-end in the repository under `backend/app`:

1. Data model updates in `backend/app/models.py`.
2. Alembic migration in `backend/alembic/versions/`.
3. Pydantic schemas in `backend/app/schemas.py`.
4. Services in `backend/app/services/*`.
5. Router endpoints in `backend/app/routers/*`.
6. Tests under `backend/tests/`.

Specifically, implement:
- A/B testing campaign management: campaign create/list, result tracking, performance metrics.
- Automated lead scoring: set lead score endpoint and lead-level score persistence.
- GDPR/consent management: store consent records, update lead consent status, retrieve status/history.

For each endpoint, include validation and error handling. Add `log_audit` entries for actions.

### Expected route patterns
- `POST /api/v1/market-intelligence/ab-tests` : create campaign.
- `GET /api/v1/market-intelligence/ab-tests` : list campaigns.
- `POST /api/v1/market-intelligence/ab-tests/results` : record variant result.
- `GET /api/v1/market-intelligence/ab-tests/{campaign_id}/metrics` : metrics.
- `POST /api/v1/market-intelligence/leads/{lead_id}/score` : update score.
- `POST /api/v1/market-intelligence/leads/{lead_id}/consent` : grant/revoke consent.
- `GET /api/v1/market-intelligence/leads/{lead_id}/consent` : status.
- `GET /api/v1/market-intelligence/leads/{lead_id}/consent/records` : history.

### Quality gates
- Add tests in `backend/tests/test_phase3_market_intelligence_flow.py` that cover both happy path and invalid inputs.
- Run `python -m pytest -q backend/tests/test_phase3_market_intelligence_flow.py` and `python -m pytest -q backend/tests/test_phase2_*` to validate.
- Update `roadmap/PHASE-3-MARKET-INTELLIGENCE.md` checklist items to `[x]` for the implemented features.

## Post-run summary
- Report changed files and status of tests.
- Mark the task complete with `task_complete` including a short summary.
