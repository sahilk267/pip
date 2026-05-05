# Procurement Intelligence Platform

AI-powered B2B+B2C commerce system for vendor discovery, RFQ, negotiation, CRM, and analytics.

## Run & Operate
| Command | Purpose |
|---------|---------|
| `cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` | Run backend (dev) |
| `cd frontend && npm run dev` | Run frontend (dev) |
| `gunicorn --bind=0.0.0.0:5000 -k uvicorn.workers.UvicornWorker app.main:app` | Run backend (prod) |
| `cd backend && pip install -r requirements.txt` | Install backend deps |
| `POST /api/v1/seed-all` | Populate all sample data (vendors, products, leads, prices, scores, invoices) |

**Required env vars (all optional — have safe defaults):** `DATABASE_URL`, `JWT_SECRET_KEY`, `STRIPE_SECRET_KEY`, `SENDGRID_API_KEY`, `SMTP_HOST/PORT/USER/PASS`, `EMAIL_FROM`, `DEFAULT_PAYMENT_GATEWAY`

## Stack
- **Backend:** FastAPI + SQLAlchemy (SQLite dev / PostgreSQL prod) · Python 3.11 · Uvicorn
- **Frontend:** Next.js 16.2.4 + TypeScript + TailwindCSS
- **Ports:** Backend 8000 · Frontend 5000 (proxied at `/api/*` → `localhost:8000`)
- **Auth:** JWT HS256, 24h expiry
- **ORM:** SQLAlchemy `create_all` (no migrations needed for dev)

## Where things live
- **Backend entry:** `backend/app/main.py` — registers all 22 routers
- **DB models:** `backend/app/models.py` (core) + `backend/app/models_extended.py` (6 feature tables)
- **Services:** `backend/app/services/` (~50 service files)
- **Routers:** `backend/app/routers/` (21 files) + `backend/app/auth/router.py`
- **Seed data:** `backend/app/routers/seed.py` → `POST /api/v1/seed-all`
- **Frontend pages:** `frontend/app/**/page.tsx`
- **Frontend components:** `frontend/components/`
- **Next.js proxy:** `frontend/next.config.js` rewrites `/api/*` → `http://localhost:8000/api/*`

## Architecture decisions
- **No Redis / Celery** — background tasks use an in-process thread pool (3 workers) + periodic scheduler in `task_runner.py`
- **Vendor dedup** — normalized name matching in `crud.create_vendor` prevents duplicates on ingest
- **Payment abstraction** — `payment_gateway.py` wraps Stripe / Razorpay / Mock behind a single interface; falls back to mock when keys absent
- **Email fallback** — `email_service.py` tries SendGrid → SMTP → console print; never crashes on missing config
- **Feature tables** — `models_extended.py` must be imported before `init_db()` runs so `create_all` picks them up (fixed in `database.py`)
- **Seed-all endpoint** — `POST /api/v1/seed-all` is idempotent (deduplicates vendors/products/leads) and populates all 8 data domains in one call

## Product
**16 frontend pages:**
| Page | Path | Description |
|------|------|-------------|
| Dashboard | `/` | KPI cards (vendors, products, leads, orders, RFQs), lead funnel chart |
| Vendors | `/vendors` | Vendor list + add form |
| Products | `/products` | Product catalog + add form |
| CRM / Leads | `/crm` | Lead management with stage updates |
| Orders | `/orders` | B2C orders tracking |
| Cart | `/cart` | Shopping cart + checkout flow |
| Payments | `/payments` | Gateway selection + intent creation |
| Notifications | `/notifications` | Alerts + audit log viewer |
| RFQ | `/rfq` | RFQ broadcasts + create |
| RFQ Templates | `/rfq/templates` | Bulk RFQ templates: create, add products, reuse |
| Analytics | `/analytics` | Funnel bar chart + pipeline trend |
| Price Trends | `/price-trends` | Historical price tracking, benchmarks, seed button |
| Suppliers | `/suppliers` | Scorecard (A/B/C grades) + smart vendor recommendations |
| Cost Optimizer | `/cost-optimization` | Opportunities, spend analyzer, volume discount tiers |
| Invoices | `/invoices` | Invoice list, create, send, mark paid |
| Login | `/login` | Auth (login + register toggle) |

**22 API router groups:**
`auth`, `vendors`, `products`, `leads`, `orders/b2c`, `rfq`, `crm`, `analytics`, `marketing`, `compliance`, `monitoring`, `operations`, `enrichment`, `cart`, `messages`, `escalations`, `market-intelligence`, `automation`, `i18n`, `integrations`, `payments`, `tasks`, `analytics-extended` (price-trends + supplier-scoring + cost-optimization), `invoices`, `rfq-templates`, `vendor-recommendations`, `seed-all`

**Seed data (via `POST /api/v1/seed-all`):**
- 15 vendors (across Electronics, Manufacturing, Raw Materials, Logistics, Software, Chemicals, Packaging, Services)
- 15 products with SKU and category
- 10 leads across all funnel stages
- 270 price history records → benchmarks for all 9 categories
- 15 supplier scores (quality/reliability/price/communication/compliance breakdown)
- 72 volume discount tiers (3-tier per vendor/category pair)
- 6 cost-saving opportunities (bulk discount, alt vendor, consolidation)
- 10 sample invoices (mix of draft/sent/paid, with vendor names and line items)

## User preferences
- Everything should be documented and updated in replit.md
- All 6 extended features (Price Trends, Supplier Scoring, Invoice Management, Bulk RFQ Templates, Smart Vendor Recommendations, Cost Optimization) must work end-to-end with no errors
- Seed buttons on each feature page so data is visible immediately without manual entry

## Gotchas
- `GET /api/v1/vendors` returns a **plain list** (not `{vendors: [...]}`) — frontend must handle both: `Array.isArray(d) ? d : (d.vendors || [])`
- `models_extended.py` **must** be imported in `database.py` `init_db()` before `create_all()` or feature tables won't be created
- RFQ templates API uses **query params** not JSON body — FastAPI simple params, not Pydantic body models
- Price trend routes: `benchmark/{category}` must come before `{category}` in the router or FastAPI will try to match "benchmark" as a category ID
- Vendor `category` field is set by the categorization engine — `crud.create_vendor` doesn't set it; seed.py patches it manually after creation
- `Lead` model uses `full_name` (not `contact_name`) and `lead_score` (not `score`)
- All new seed endpoints are idempotent (skip if already seeded)

## Pointers
- Backend Swagger UI: `http://localhost:8000/docs`
- Extended models: `backend/app/models_extended.py`
- Seed router: `backend/app/routers/seed.py`
- Analytics + supplier + cost router: `backend/app/routers/analytics_extended.py`
- Invoice router: `backend/app/routers/invoices.py`
- Price trends service: `backend/app/services/price_trends.py`
- Supplier scoring service: `backend/app/services/supplier_scoring.py`
- Cost optimization service: `backend/app/services/cost_optimization.py`
