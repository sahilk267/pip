# Phase 1 Implementation Plan: Data Foundation & Self-Building Network (B2B+B2C)

This roadmap is **kept in sync with the repository** (last verified against `e:\PIP` code + tests on 2026-03-30). The narrative twin is `e:\PIP\PHASE-1-IMPLEMENTATION-PLAN.md` at the repo root.

---

## Step-by-Step Implementation Plan

### 1. Project & Environment Setup
- [x] Python environment and dependencies (`backend/requirements.txt`: FastAPI, SQLAlchemy, Pydantic v2, Celery, Redis drivers, Alembic, etc.).
- [x] Pre-commit: `.pre-commit-config.yaml`, repo **`.env.example`** (`PRE_COMMIT_HOME` hint), and **`scripts/install-precommit.ps1`** (Windows-local cache). *Hooks are “ready”; run the installer once per clone.*
- [x] Docker Compose for PostgreSQL, Redis, API, Celery worker, and Celery beat (`infrastructure/docker-compose.yml`). *Static admin pages are served by the API (`/admin/*`); no separate frontend service.*

### 2. Database Schema Design
- [x] Tables for vendors, products, leads (incl. segmentation/attribution fields), customers, data sources, audit logs, alerts, CRM communications, and lead stage transitions — `backend/app/models.py`, `crm_models.py`, Alembic **`0001`–`0006`**.

### 3. Data Ingestion Modules
- [x] Vendor discovery connectors and `POST /api/v1/ingestion/discovery`.
- [x] Product catalog ingestion via discovery and `POST /api/v1/products`.
- [x] Customer/lead CRM router; list + update endpoints.
- [x] Celery beat: vendor refresh, B2B/B2C enrichment, categorization, **lead segmentation batch**, **lead B2B enrichment**, data quality metrics, connector monitoring.

### 4. Data Deduplication & Validation
- [x] Normalized-name deduplication (`crud.py`).
- [x] Pydantic validation; **`ProductCreate`** normalizes SKU (upper/strip) and price (strip); connector `metadata` coercion for vendors (`schemas.py`).

### 5. Data Enrichment & Quality
- [x] Enrichment plumbing: CSV fixtures + optional `B2B_ENRICHMENT_API` / `B2C_ATTRIBUTE_API` (`enrichment_sources.py`).
- [x] Quality metrics → `AuditLog` (`compute_data_quality_metrics`).
- [x] **Connector execution**: spacing, exponential backoff, retries (`CONNECTOR_*` env vars, `connector_execution.py`, `scraping_governance.py`).
- [x] Marketing intent enrichment: persisted lead signal data + refresh task (`POST /api/v1/marketing/intent/event`, `refresh_marketing_intent`).

### 6. Relationship & Customer Management
- [x] CRM APIs: leads (create, list, stage, **marketing prefs / unsubscribe**), customers (create, **list**, consent, **engagement patch**).
- [x] CRM communication tracking (`POST/GET /api/v1/crm/communications`) for lead/customer touchpoints.
- [x] **CRM dashboard JSON** `GET /api/v1/crm/dashboard` + static **`/admin/crm-dashboard`**.
- [x] Automated follow-up reminders via Celery (`send_follow_up_reminders`).
- [x] Sales funnel tracking endpoints (`GET /api/v1/crm/funnel`, `GET /api/v1/leads/{lead_id}/transitions`) backed by stage transition history.
- [x] Automated sales playbooks (`GET /api/v1/leads/{lead_id}/playbook`, `GET /api/v1/crm/playbook-queue`) using stage, score, and communication context.

### 7. Categorization & Feedback
- [x] Rule engine (`ai_engines/categorization_rules.json`, `categorization.py`, `categorize_catalog` task).
- [x] Admin category overrides (PATCH + `/admin/categorization`).

### 8. Audit Logging & Compliance
- [x] `AuditLog` + `GET /api/v1/compliance/report`.
- [x] **Scraping / governance disclosure** `GET /api/v1/compliance/scraping-controls` (policy JSON + checklist).

### 9. Monitoring & Alerts
- [x] Connector + schema drift alerts; `GET /api/v1/monitoring/dashboard`.
- [x] Celery retries and `task_failure` → `Alert`.
- [x] **Escalation playbook API** `GET /api/v1/operations/escalation-playbook` (`services/escalation.py`).
- [x] Sales funnel snapshot audit task (`compute_sales_funnel_snapshot`) scheduled in Celery beat.

### 10. Documentation & Testing
- [x] READMEs + Phase 1 plans; **`backend/tests/`** (31 tests): drop/recreate schema in `conftest` for SQLite parity with migrations.

### 11. Integrations & Internationalization (Phase 1 stubs)
- [x] **External CRM / MAP stub** `POST /api/v1/integrations/external-crm/event` → `AuditLog` only (`routers/integrations.py`).
- [x] **i18n preview** `GET /api/v1/i18n/strings?locale=en|hi` (`services/i18n_preview.py`).

---

## Cross-Verification vs `PHASE-1-DATA-NETWORK.md`

| Requirement | Status | Evidence / gap |
| --- | --- | --- |
| Vendor/client/product auto-discovery | Implemented | Connectors + discovery endpoint + resilient fetch. |
| Deduplication & validation | Implemented | `crud.py`, `schemas.py`. |
| Periodic enrichment / Celery | Implemented | Worker + beat (incl. `segment_leads_batch`). |
| Anti-bot/captcha & legal | Implemented (guardrails) | Compliance policy endpoint + legal connector allow-list (`SCRAPING_APPROVED_CONNECTORS`) + anti-bot signal alerts. |
| Data quality metrics & monitoring | Implemented | Quality task + dashboard. |
| Distributed/adaptive scraping | Implemented (single-node adaptive) | Per-connector dynamic throttling based on failure streak + exponential backoff/retries. |
| Automated error recovery/retry | Implemented | Celery retries + connector `fetch_with_resilience` + alerts. |
| Lead enrichment / segmentation | Implemented | Lead segmentation + B2B enrichment (revenue_estimate/decision_maker) + attribution channel + marketing prefs. |
| Communication tracking / follow-up reminders | Implemented | CRM communications API (`POST/GET /api/v1/crm/communications`) + scheduled reminder task (`send_follow_up_reminders`). |
| Sales funnel tracking | Implemented | Transition history in `lead_stage_transitions`; analytics endpoint `GET /api/v1/crm/funnel`; transition audit via `GET /api/v1/leads/{lead_id}/transitions`. |
| Automated sales playbooks | Implemented | Rule-based recommendations via `GET /api/v1/leads/{lead_id}/playbook` and prioritized queue `GET /api/v1/crm/playbook-queue`. |
| Marketing intent enrichment | Implemented | Lead intent signal ingestion via `POST /api/v1/marketing/intent/event`; persisted signal/score fields on `Lead`; scheduled refresh task `refresh_marketing_intent`. |
| Product catalog normalization (B2C) | Implemented | B2C attribute feed key normalization + product `category/category_confidence` bootstrap from feed. |
| CRM dashboard (visual) | Implemented (MVP) | JSON dashboard + static admin page. |
| B2C customer management | Implemented (API) | Customer create/list (`POST /api/v1/customers`, `GET /api/v1/customers`), consent updates (`PATCH /api/v1/customers/{customer_id}/consent`), and engagement patch (`PATCH /api/v1/customers/{customer_id}`). |
| Consent / opt-in | Implemented (API) | Lead marketing preferences/unsubscribe (`PATCH /api/v1/leads/{lead_id}/preferences`) and customer consent (`PATCH /api/v1/customers/{customer_id}/consent`). |
| Categorization + admin feedback | Implemented | Rules + admin UI/API. |
| Audit / compliance reporting | Implemented | Audit + compliance + scraping-controls bundle. |
| Governance records | Implemented | Audit aggregation + explicit governance endpoints. |
| Marketing automation / analytics | Implemented (Phase 1 provider dispatch + ROI + upsell/cross-sell) | Marketing events + intent signals now power `GET /api/v1/marketing/analytics`, `GET /api/v1/marketing/roi`, campaign trigger API (`POST /api/v1/marketing/campaigns/trigger`), provider dispatch API (`POST /api/v1/marketing/campaigns/dispatch`), and upsell/cross-sell trigger-dispatch API (`POST /api/v1/marketing/campaigns/upsell-cross-sell/trigger`); periodic snapshots/triggers/dispatches via `compute_marketing_analytics_snapshot`, `compute_campaign_roi_snapshot`, `trigger_nurture_reengagement_campaigns`, `dispatch_marketing_automation_campaigns`, and `trigger_upsell_cross_sell_campaigns`. |
| Escalation playbook | Implemented | API-backed steps (`escalation.py`). |
| Multi-language | Implemented (Phase 1 API scope) | Locale-aware responses now cover i18n string catalog plus marketing/integrations/compliance/operations endpoints (`GET /api/v1/i18n/strings`, `POST /api/v1/marketing/automation/event`, `POST /api/v1/integrations/external-crm/event`, `GET /api/v1/compliance/scraping-controls`, `GET /api/v1/operations/escalation-playbook`). |
| External CRM integration | Implemented (stub) | Audit-log stub webhook `POST /api/v1/integrations/external-crm/event`; real sync TBD. |
| Monitoring & alerts | Implemented | Alerts + dashboard + Celery failures. |

---

## Implementation Notes

- **Tests:** `PYTHONPATH=<repo-root> python -m pytest backend/tests/`. `conftest.py` forces `DATABASE_URL` to `backend/tests/.pytest.db` (SQLite) before imports, then `drop_all` + `init_db()` so schema always matches models. Latest verification: 38 passed.
- **Migrations:** apply **`0003_lead_intelligence`**, **`0004_lead_b2b_enrichment`**, **`0005_crm_communications`**, **`0006_lead_stage_transitions`**, and **`0007_marketing_intent`** on PostgreSQL for lead intelligence, CRM communication tracking, funnel transition history, and marketing intent fields.
- **`Vendor` JSON** uses Python attr `vendor_metadata`; never bind Pydantic response fields to the name `metadata` (SQLAlchemy `MetaData` collision).
- **Single narrative source:** keep `e:\PIP\PHASE-1-IMPLEMENTATION-PLAN.md` aligned when scope changes, then refresh this roadmap table.
