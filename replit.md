# Procurement Intelligence Platform

AI-powered B2B+B2C commerce system for vendor discovery, RFQ, negotiation, CRM, email digest reporting, and analytics.

---

## Quick Start

### 1 — Install dependencies
```bash
cd backend && pip install -r requirements.txt
cd frontend && npm install
```

### 2 — Start the servers (two terminals or two Replit workflows)
```bash
# Terminal 1 — Backend API
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Frontend
cd frontend && npm run dev
```

### 3 — Seed all sample data
```
POST http://localhost:8000/api/v1/seed-all
```
Or click the **Seed Data** button on any feature page.

### 4 — Open the app
```
http://localhost:5000   (frontend — proxies /api/* → backend:8000)
http://localhost:8000/docs   (Swagger UI — all 24 API router groups)
```

---

## Deployment

### Production run commands
```bash
# Backend (prod — gunicorn + uvicorn workers)
cd backend
gunicorn --bind=0.0.0.0:8000 -k uvicorn.workers.UvicornWorker app.main:app

# Frontend (prod build)
cd frontend
npm run build
npm start   # serves on port 5000 by default (see next.config.js)
```

### Environment variables
All variables are **optional** — every feature has a safe in-process fallback.

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | SQLite `./dev.db` | Postgres connection string for production |
| `JWT_SECRET_KEY` | `"dev-secret-change-me"` | HS256 signing key for auth tokens (24h expiry) |
| `STRIPE_SECRET_KEY` | _(mock)_ | Stripe payment gateway |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | _(mock)_ | Razorpay gateway |
| `DEFAULT_PAYMENT_GATEWAY` | `mock` | `stripe` \| `razorpay` \| `mock` |
| `SENDGRID_API_KEY` | _(console fallback)_ | SendGrid email provider |
| `SMTP_HOST` | _(console fallback)_ | SMTP server hostname |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` | — | SMTP username |
| `SMTP_PASSWORD` | — | SMTP password |
| `SMTP_FROM` | `noreply@procurement-platform.com` | Sender address |
| `SMTP_FROM_NAME` | `Procurement Intelligence Platform` | Sender display name |
| `EMAIL_BACKEND` | `auto` | `auto` \| `smtp` \| `sendgrid` \| `console` |
| `APP_BASE_URL` | `http://localhost:8000` | Base URL used to build unsubscribe links in digest emails |

**Email priority:** SendGrid (if key present) → SMTP (if host+user present) → console print (never crashes).

### Database
- **Dev:** SQLite file at `backend/dev.db` — created automatically on first start.
- **Prod:** Set `DATABASE_URL=postgresql://user:pass@host:5432/dbname`. SQLAlchemy `create_all()` creates all tables on startup — no migrations needed.
- All feature tables are auto-registered because `models_extended.py` is imported in `database.py` before `create_all()` runs.

### Replit workflows (pre-configured)
| Workflow name | Command |
|---------------|---------|
| `Backend API` | `cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` |
| `Start application` | `cd frontend && npm run dev` |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend language | Python 3.11 |
| API framework | FastAPI |
| ORM | SQLAlchemy (sync) |
| DB (dev) | SQLite |
| DB (prod) | PostgreSQL |
| ASGI server (dev) | Uvicorn |
| ASGI server (prod) | Gunicorn + UvicornWorker |
| Background tasks | In-process thread pool (3 workers) + periodic scheduler — no Redis/Celery |
| Auth | JWT HS256, 24h expiry |
| Frontend language | TypeScript |
| Frontend framework | Next.js 16.2.4 (App Router) |
| Styling | TailwindCSS |
| Frontend port | 5000 |
| Backend port | 8000 |
| API proxy | `next.config.js` rewrites `/api/*` → `http://localhost:8000/api/*` |

---

## Repository structure

```
backend/
  app/
    main.py                  ← FastAPI app + lifespan (registers all 24 routers, starts scheduler)
    database.py              ← SQLAlchemy engine, SessionLocal, init_db()
    models.py                ← Core ORM models (Vendor, Product, Lead, Order, RFQ*, Cart, etc.)
    models_extended.py       ← Feature ORM models (see "Extended models" below)
    crud.py                  ← Generic CRUD helpers + vendor dedup logic
    auth/
      router.py              ← POST /api/v1/auth/login, /register, /me
    routers/
      seed.py                ← POST /api/v1/seed-all (idempotent master seed)
      vendors.py
      products.py
      leads.py
      orders.py
      rfq.py
      rfq_analytics.py       ← GET /api/v1/rfq/analytics
      rfq_digest.py          ← GET|POST /api/v1/rfq/digest/* (config, send, history, preview, unsubscribe)
      rfq_templates.py
      invoices.py
      analytics_extended.py  ← price-trends, supplier-scoring, cost-optimization endpoints
      vendor_recommendations.py
      crm.py
      cart.py
      payments.py
      marketing.py
      compliance.py
      monitoring.py
      operations.py
      enrichment.py
      messages.py
      escalations.py
      market_intelligence.py
      automation.py
      i18n.py
      integrations.py
      tasks.py
    services/
      email_service.py       ← send_email() — SendGrid → SMTP → console fallback
      task_runner.py         ← Thread pool + periodic scheduler (schedule(), enqueue())
      rfq_digest.py          ← Digest stats, HTML/text builder, token management, scheduler hook
      price_trends.py
      supplier_scoring.py
      cost_optimization.py
      payment_gateway.py     ← Stripe / Razorpay / Mock abstraction
      ... (~50 total service files)
  requirements.txt

frontend/
  app/
    page.tsx                 ← Dashboard
    vendors/page.tsx
    products/page.tsx
    crm/page.tsx
    orders/page.tsx
    cart/page.tsx
    payments/page.tsx
    notifications/page.tsx
    rfq/
      page.tsx               ← RFQ broadcasts
      templates/page.tsx
      analytics/page.tsx
      digest/page.tsx        ← RFQ Digest (config, preview, history, unsubscribe tokens)
    analytics/page.tsx
    price-trends/page.tsx
    suppliers/page.tsx
    cost-optimization/page.tsx
    invoices/page.tsx
    login/page.tsx
  components/
    Sidebar.tsx              ← Navigation (all pages listed)
    ...
  next.config.js             ← /api/* proxy rewrite
```

---

## Frontend pages (18 total)

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
| RFQ Analytics | `/rfq/analytics` | Response rates, avg quote prices, vendor win rates per broadcast |
| RFQ Digest | `/rfq/digest` | Weekly email digest: config, recipients, schedule, preview, history, unsubscribe tokens |
| Analytics | `/analytics` | Funnel bar chart + pipeline trend |
| Price Trends | `/price-trends` | Historical price tracking, benchmarks, seed button |
| Suppliers | `/suppliers` | Scorecard (A/B/C grades) + smart vendor recommendations |
| Cost Optimizer | `/cost-optimization` | Opportunities, spend analyzer, volume discount tiers |
| Invoices | `/invoices` | Invoice list, create, send, mark paid |
| Login | `/login` | Auth (login + register toggle) |

---

## API reference (24 router groups)

| Group | Base path | Key endpoints |
|-------|-----------|---------------|
| auth | `/api/v1/auth` | POST /login, /register, GET /me |
| vendors | `/api/v1/vendors` | CRUD + category scoring |
| products | `/api/v1/products` | CRUD |
| leads | `/api/v1/leads` | CRUD + stage updates |
| orders | `/api/v1/orders` | B2C order tracking |
| rfq | `/api/v1/rfq` | Broadcasts, delivery attempts, vendor responses |
| rfq-analytics | `/api/v1/rfq/analytics` | GET analytics (response rate, prices, win rates) |
| rfq-digest | `/api/v1/rfq/digest` | GET/POST config, POST send-now, GET history/preview/unsubscribe-tokens, GET unsubscribe |
| rfq-templates | `/api/v1/rfq/templates` | Template CRUD + line items |
| invoices | `/api/v1/invoices` | Create, list, send, mark paid |
| analytics-extended | `/api/v1` | price-trends, supplier-scoring, cost-optimization |
| vendor-recommendations | `/api/v1/vendor-recommendations` | Smart ranking by category |
| crm | `/api/v1/crm` | Pipeline + activity log |
| cart | `/api/v1/cart` | Add/remove/checkout |
| payments | `/api/v1/payments` | Intent creation, gateway selection |
| marketing | `/api/v1/marketing` | Campaigns |
| compliance | `/api/v1/compliance` | Audit trail |
| monitoring | `/api/v1/monitoring` | Health checks |
| operations | `/api/v1/operations` | Ops tasks |
| enrichment | `/api/v1/enrichment` | Vendor data enrichment |
| messages | `/api/v1/messages` | Vendor messaging |
| escalations | `/api/v1/escalations` | Escalation management |
| market-intelligence | `/api/v1/market-intelligence` | Price intel |
| automation | `/api/v1/automation` | Rule-based automation |
| i18n | `/api/v1/i18n` | Translations |
| integrations | `/api/v1/integrations` | Third-party connectors |
| tasks | `/api/v1/tasks` | Background task status |
| seed-all | `/api/v1/seed-all` | POST — master idempotent seed |

---

## Extended DB models (`backend/app/models_extended.py`)

| Table | Model | Purpose |
|-------|-------|---------|
| `price_history` | `PriceHistory` | Historical unit prices per vendor/product |
| `price_benchmarks` | `PriceBenchmark` | Aggregated category benchmarks |
| `supplier_scores` | `SupplierScore` | Scorecard: quality/reliability/price/comms/compliance |
| `supplier_rating_history` | `SupplierRatingHistory` | Score trend over time |
| `invoices` | `Invoice` | Invoice header (vendor, amount, status, terms) |
| `invoice_items` | `InvoiceItem` | Line items on an invoice |
| `rfq_templates` | `RFQTemplate` | Reusable RFQ templates |
| `rfq_template_items` | `RFQTemplateItem` | Products/requirements in a template |
| `vendor_rankings` | `VendorRanking` | Ranked vendor list per category |
| `cost_opportunities` | `CostOpportunity` | Identified savings opportunities |
| `discount_tiers` | `DiscountTier` | Volume discount tiers per vendor/category |
| `rfq_digest_config` | `RFQDigestConfig` | Single-row digest schedule + recipient list |
| `rfq_digest_log` | `RFQDigestLog` | Audit log of every digest send |
| `rfq_digest_unsubscribe` | `RFQDigestUnsubscribe` | Per-recipient one-click unsubscribe tokens |

---

## RFQ Email Digest — full feature overview

The digest feature automatically emails a formatted weekly RFQ performance summary to configured recipients.

### How it works

1. **Scheduler** — `task_runner.schedule(maybe_send_scheduled_digest, interval_seconds=3600)` is registered in `main.py` lifespan. Every hour it checks: is today the configured day-of-week? Is it the configured UTC hour? Has it already sent in the last 60 min? If all pass, it calls `send_digest()`.
2. **Stats** — `_compute_stats(db, window_days)` queries live RFQ tables (broadcasts → delivery attempts → vendor responses → parsed quotes) and returns: total broadcasts, vendors reached, total responses, response rate %, total quotes, avg unit price, avg lead time, top broadcast, top winning vendor.
3. **Per-recipient email** — For each recipient, a unique UUID token is generated and stored in `rfq_digest_unsubscribe`. The HTML and plaintext email bodies are built with the token embedded as an unsubscribe URL.
4. **Unsubscribe** — `GET /api/v1/rfq/digest/unsubscribe?token=<uuid>` is a public (no-auth) endpoint. It marks the token used, removes the email from `rfq_digest_config.recipient_emails`, and returns a styled confirmation HTML page.
5. **Logging** — Every send attempt is recorded in `rfq_digest_log` with status (success / partial / failed), sent/failed counts, error messages, and a full stats snapshot at send time.

### API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/rfq/digest/config` | Get current schedule + recipient list |
| POST | `/api/v1/rfq/digest/config` | Update schedule/recipients (query params + JSON body) |
| POST | `/api/v1/rfq/digest/send-now` | Trigger immediate send (for testing) |
| GET | `/api/v1/rfq/digest/preview` | Preview stats for the next digest |
| GET | `/api/v1/rfq/digest/history` | List of past send attempts |
| GET | `/api/v1/rfq/digest/unsubscribe?token=` | Public one-click unsubscribe (returns HTML page) |
| GET | `/api/v1/rfq/digest/unsubscribe-tokens` | Admin list of all tokens + used status |

### Email delivery
- **No email provider configured?** Every send falls back to console print — the digest log still records it as sent.
- **Set `APP_BASE_URL`** in production so unsubscribe links point to your public domain, not localhost.

---

## Background task system

No Redis or Celery required. Everything runs in-process.

```
task_runner.py
├── start_workers(count=3)     — starts 3 daemon threads consuming from a Queue
├── enqueue(fn, *args)         — push a task; returns task_id
├── get_result(task_id)        — poll status: queued / running / success / failed
├── list_tasks(status, limit)  — recent task results
├── schedule(fn, interval_s)   — register a periodic function
└── start_scheduler()          — starts a daemon thread that ticks every 5s
```

Registered scheduled tasks (added in `main.py` lifespan before `start_scheduler()`):
| Name | Interval | Function |
|------|----------|----------|
| `rfq-digest-check` | 3600s (1h) | `rfq_digest.maybe_send_scheduled_digest` — fires the digest on the right day/hour |

---

## Seed data (via `POST /api/v1/seed-all`)

All seeding is **idempotent** — safe to call multiple times, skips existing records.

| Domain | Count | Details |
|--------|-------|---------|
| Vendors | 15 | Electronics, Manufacturing, Raw Materials, Logistics, Software, Chemicals, Packaging, Services |
| Products | 15 | With SKU and category |
| Leads | 10 | Across all funnel stages |
| Price history | 270 records | Benchmarks for 9 categories |
| Supplier scores | 15 | quality/reliability/price/communication/compliance breakdown |
| Volume discount tiers | 72 | 3-tier per vendor/category pair |
| Cost opportunities | 6 | bulk discount, alt vendor, consolidation |
| Invoices | 10 | Mix of draft/sent/paid with vendor names and line items |
| RFQ broadcasts | 8 | With 19 vendor responses and 19 parsed quotes across all major categories |
| RFQ templates | 4 | Electronics, Manufacturing, Software, Logistics — each with 3–4 line items |

---

## Architecture decisions

| Decision | Rationale |
|----------|-----------|
| No Redis / Celery | In-process thread pool keeps the stack simple; handles all current workloads |
| SQLAlchemy `create_all` | No migration tool needed for dev; `DATABASE_URL` swap covers prod |
| `models_extended.py` imported in `database.py` | Guarantees extended tables exist before `create_all()` runs |
| Vendor dedup in `crud.create_vendor` | Normalized name matching prevents duplicates on repeated seeding |
| Payment abstraction | `payment_gateway.py` wraps Stripe / Razorpay / Mock; falls back to mock when keys absent |
| Email fallback chain | SendGrid → SMTP → console print; never raises on missing config |
| Per-recipient unsubscribe tokens | UUID token generated per send per recipient; stored in DB; single-use; no auth required to redeem |
| `APP_BASE_URL` env var | Controls unsubscribe link hostname; defaults to localhost for dev, set to prod domain in deployment |

---

## Gotchas

- `GET /api/v1/vendors` returns a **plain list**, not `{vendors: [...]}` — every frontend page must handle both: `Array.isArray(d) ? d : (d.vendors || [])`
- `models_extended.py` **must** be imported in `database.py` before `create_all()` — this is already wired; don't remove the import
- RFQ templates API uses **query params** (not JSON body) — FastAPI simple params, not Pydantic body models
- Price trend routes: `benchmark/{category}` must come before `{category}` in the router or FastAPI matches "benchmark" as a category ID
- Vendor `category` field is set by the categorization engine; `crud.create_vendor` does not set it — `seed.py` patches it manually after creation
- `Lead` model uses `full_name` (not `contact_name`) and `lead_score` (not `score`)
- Digest `send_now` returns `{status: "failed", reason: "no_recipients"}` if the recipient list is empty — this is expected, not a bug
- Set `APP_BASE_URL` in production — unsubscribe links in emails default to `http://localhost:8000` without it

---

## Key file index

| File | Purpose |
|------|---------|
| `backend/app/main.py` | FastAPI app, lifespan, router registration, scheduler setup |
| `backend/app/database.py` | Engine, `SessionLocal`, `init_db()`, extended model import |
| `backend/app/models.py` | Core ORM models |
| `backend/app/models_extended.py` | Feature + digest ORM models |
| `backend/app/crud.py` | Generic CRUD + vendor dedup |
| `backend/app/auth/router.py` | JWT auth endpoints |
| `backend/app/routers/seed.py` | Idempotent master seed endpoint |
| `backend/app/routers/rfq_analytics.py` | RFQ analytics API |
| `backend/app/routers/rfq_digest.py` | Digest config, send, history, unsubscribe API |
| `backend/app/routers/analytics_extended.py` | Price trends, supplier scoring, cost optimization |
| `backend/app/routers/invoices.py` | Invoice CRUD |
| `backend/app/routers/rfq_templates.py` | Template CRUD |
| `backend/app/routers/vendor_recommendations.py` | Smart vendor ranking |
| `backend/app/services/rfq_digest.py` | Digest stats, email builder, token logic, scheduler hook |
| `backend/app/services/email_service.py` | `send_email()` with SendGrid/SMTP/console fallback |
| `backend/app/services/task_runner.py` | Thread-pool + periodic scheduler |
| `backend/app/services/payment_gateway.py` | Stripe/Razorpay/Mock abstraction |
| `backend/app/services/price_trends.py` | Price history + benchmark computation |
| `backend/app/services/supplier_scoring.py` | Supplier scorecard logic |
| `backend/app/services/cost_optimization.py` | Cost savings opportunity detection |
| `frontend/app/**/page.tsx` | All 18 frontend pages |
| `frontend/components/Sidebar.tsx` | Navigation sidebar |
| `frontend/next.config.js` | `/api/*` proxy rewrite to backend |

---

## User preferences

- Everything documented and updated in `replit.md`
- All extended features (Price Trends, Supplier Scoring, Invoice Management, Bulk RFQ Templates, Smart Vendor Recommendations, Cost Optimization, RFQ Analytics, RFQ Digest) must work end-to-end with no errors
- Seed buttons on each feature page so data is visible immediately without manual entry
- No Redis, no Celery, no Docker — keep the stack simple and self-contained
