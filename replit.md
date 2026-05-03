# Procurement Intelligence Platform

AI-powered B2B+B2C commerce system for vendor discovery, RFQ, negotiation, CRM, and analytics.

## Architecture

### Backend (FastAPI)
- **Location:** `backend/`
- **Framework:** FastAPI + SQLAlchemy (SQLite dev / PostgreSQL prod)
- **Port:** 8000 (development, console workflow)
- **Entry point:** `backend/app/main.py`
- **Workflow:** "Backend API" — `cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

### Frontend (Next.js 14)
- **Location:** `frontend/`
- **Framework:** Next.js 14 + TypeScript + TailwindCSS
- **Port:** 5000 (webview)
- **Workflow:** "Start application" — `cd frontend && npm run dev`
- **API Proxy:** `/api/*` → `http://localhost:8000/api/*` (via next.config.js rewrites)

## Key Features (Implemented)
- **Authentication:** JWT-based (register, login, RBAC roles: admin, sales_rep, customer, vendor)
- **Vendor Management:** Ingestion, enrichment (CSV-based), categorization
- **Product Catalog:** B2C products with SKU, pricing, stock
- **CRM / Leads:** Lead capture, stage tracking, funnel analytics, AB testing
- **B2C Orders:** Order creation, fulfillment tracking, shipping, payment gateway
- **RFQ System:** Broadcast RFQs to vendors, collect responses, parse quotes, negotiate
- **Marketing:** Campaign dispatch, A/B testing, consent management
- **Analytics:** Sales drill-down, anomaly detection, funnel metrics, CRM dashboard
- **AI Automation:** Category assignment, lead scoring, market intelligence stubs

## Database
- **Dev:** SQLite (`backend/dev.db`)
- **Prod:** PostgreSQL (via `DATABASE_URL` env var)
- **Migrations:** 34 Alembic migrations in `backend/alembic/versions/`

## Auth System
- **File:** `backend/app/auth/` (utils.py, router.py, schemas.py, user_model.py)
- **User model:** `users` table — id, email, hashed_password, full_name, role, is_active
- **JWT:** HS256, 24h expiry, configurable via `JWT_SECRET_KEY` env var
- **Roles:** admin, sales_rep, customer, vendor

## API Routers (18 total)
- `/api/v1/auth` — register, login, me
- `/api/v1/vendors` — vendor CRUD + enrichment
- `/api/v1/products` — product CRUD
- `/api/v1/leads` — CRM lead management
- `/api/v1/orders/b2c` — B2C commerce
- `/api/v1/rfq` — RFQ broadcasts
- `/api/v1/crm` — funnel, dashboard, communications
- `/api/v1/analytics` — sales, marketing, anomaly detection
- `/api/v1/marketing` — campaigns, A/B tests
- `/api/v1/compliance` — GDPR, consent
- `/api/v1/monitoring` — alerts, audit logs
- `/api/v1/operations` — pricing, approvals
- `/api/v1/enrichment` — vendor/product enrichment
- `/api/v1/rfq` — RFQ management
- `/api/v1/cart` — B2C cart
- `/api/v1/messages` — message templates
- `/api/v1/escalations` — escalation rules
- `/api/v1/market-intelligence` — signals, opportunities
- `/api/v1/automation` — AI automation stubs
- `/api/v1/i18n` — internationalization
- `/api/v1/integrations` — external integrations

## Frontend Pages
- `/` — Dashboard (KPI cards, funnel chart, quick links)
- `/vendors` — Vendor list + add form
- `/products` — Product catalog + add form
- `/crm` — Lead management with stage updates
- `/orders` — B2C orders tracking
- `/rfq` — RFQ broadcasts + create
- `/analytics` — Charts (funnel bar, pipeline trend)
- `/login` — Auth (login + register toggle)

## Deployment
- **Target:** Autoscale
- **Backend command:** `gunicorn --bind=0.0.0.0:5000 -k uvicorn.workers.UvicornWorker app.main:app`
- **Build:** `cd backend && pip install -r requirements.txt`

## Bug Fixes Applied
- Route ordering fix in orders.py (feedback/summary before /{order_id}/feedback)
- Replaced deprecated `@app.on_event('startup')` with `asynccontextmanager` lifespan
- Added indexes to Lead.email, Lead.stage, Lead.segment
- Removed passlib dependency (bcrypt incompatibility) — use bcrypt directly
- Enrichment CSVs present in `data/enrichment/`

## RFQ Workflow (NEW)
- **Step 1: Product Details** — Enter what you're sourcing (name, qty, target price, deadline, notes)
- **Step 2: Vendor Matching** — Smart algorithm ranks 50 vendors by:
  - Category fit (0–50 pts) — product keywords mapped to 10 industry banks
  - Name relevance (0–15 pts) — keyword overlap with vendor metadata
  - Quote history (0–35 pts) — past response rate + price competitiveness
  - Auto-selects "good" and above confidence vendors
- **Step 3: Broadcast** — Send RFQ to selected vendors via email
- **Quotes View** — After vendors respond, side-by-side comparison table sorted by:
  - Unit price (lowest first)
  - Lead time (fastest)
  - Response speed (hours to respond)
  - Parse confidence (0–100%)
- **Endpoints:**
  - `GET /api/v1/rfq/vendor-suggestions?product_name=...&target_price=...&limit=10` — Returns ranked vendors with scoring breakdown
  - `GET /api/v1/rfq/broadcasts/{id}/quotes-comparison` — Returns sorted quote comparison with response metrics

## Env Vars
- `DATABASE_URL` — PostgreSQL URL for production
- `JWT_SECRET_KEY` — JWT signing secret (MUST change in prod)
- `ACCESS_TOKEN_EXPIRE_MINUTES` — JWT expiry (default: 1440 = 24h)
- `BACKEND_URL` — Backend API URL for Next.js rewrites (default: http://localhost:8000)
