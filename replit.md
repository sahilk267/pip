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
- **Vendor Management:** Ingestion, enrichment (CSV-based), categorization, 4 source connectors
- **Product Catalog:** B2C products with SKU, pricing, category
- **CRM / Leads:** Lead capture, stage tracking, funnel analytics, AB testing
- **B2C Orders:** Order creation, fulfillment tracking, shipping, payment gateway, order confirmation email
- **RFQ System:** Broadcast RFQs to vendors, collect responses, parse quotes, negotiate; vendor notification emails
- **Payment Gateway:** Stripe / Razorpay / Mock — intent → confirm → refund lifecycle with audit trail
- **Email Service:** SMTP / SendGrid / Console fallback — welcome, order confirmation, vendor notifications
- **Background Tasks:** In-process thread-pool (3 workers) + periodic scheduler — no Redis needed
- **Marketing:** Campaign dispatch, A/B testing, consent management
- **Analytics:** Sales drill-down, anomaly detection, funnel metrics, CRM dashboard
- **AI Automation:** Category assignment, lead scoring, market intelligence stubs
- **Notifications:** Alert center + audit log viewer (frontend)
- **Cart:** Shopping cart with checkout flow (frontend)

## Database
- **Dev:** SQLite (`backend/dev.db`)
- **Prod:** PostgreSQL (via `DATABASE_URL` env var)
- **Migrations:** 34+ Alembic migrations in `backend/alembic/versions/`
- **Seed state:** 15 vendors, 15 products, 5 orders, 3 payment gateways, 10 leads, 2 users

## Auth System
- **File:** `backend/app/auth/` (utils.py, router.py, schemas.py, user_model.py)
- **User model:** `users` table — id, email, hashed_password, full_name, role, is_active
- **JWT:** HS256, 24h expiry, configurable via `JWT_SECRET_KEY` env var
- **Roles:** admin, sales_rep, customer, vendor

## Services (`backend/app/services/`)
| Service | File | Purpose |
|---------|------|---------|
| Payment Gateway | `payment_gateway.py` | Stripe/Razorpay/Mock — intent, confirm, refund, webhook |
| Email Service | `email_service.py` | SMTP/SendGrid/Console — welcome, order, vendor notifications |
| Task Runner | `task_runner.py` | Thread-pool (3 workers) + periodic scheduler |
| B2C Commerce | `b2c_commerce.py` | Cart, checkout, payment gateway management |
| Orders | `orders.py` | B2C order creation with dedup and tracking |
| Order Shipping | `order_shipping.py` | Shipment create + status sync |
| Order Feedback | `order_feedback.py` | Deal feedback recording |
| Enrichment | `enrichment_service.py` | CSV-based B2B/B2C data enrichment |

## API Routers (20 total)
- `/api/v1/auth` — register, login, me
- `/api/v1/vendors` — vendor CRUD + enrichment
- `/api/v1/products` — product CRUD
- `/api/v1/leads` — CRM lead management
- `/api/v1/orders/b2c` — B2C commerce + shipping + payment intents
- `/api/v1/rfq` — RFQ broadcasts + quote comparison
- `/api/v1/crm` — funnel, dashboard, communications
- `/api/v1/analytics` — sales, marketing, anomaly detection
- `/api/v1/marketing` — campaigns, A/B tests
- `/api/v1/compliance` — GDPR, consent
- `/api/v1/monitoring` — alerts, audit logs, system health
- `/api/v1/operations` — pricing, approvals
- `/api/v1/enrichment` — vendor/product enrichment
- `/api/v1/cart` — B2C cart
- `/api/v1/messages` — message templates
- `/api/v1/escalations` — escalation rules
- `/api/v1/market-intelligence` — signals, opportunities
- `/api/v1/automation` — AI automation stubs
- `/api/v1/i18n` — internationalization
- `/api/v1/integrations` — external integrations
- `/api/v1/payments` — payment gateway CRUD (new)
- `/api/v1/tasks` — background task monitoring (new)

## Frontend Pages
- `/` — Dashboard (KPI cards, funnel chart, quick links)
- `/vendors` — Vendor list + add form
- `/products` — Product catalog + add form
- `/crm` — Lead management with stage updates
- `/orders` — B2C orders tracking
- `/cart` — Shopping cart + checkout flow (new)
- `/payments` — Payment gateway selection + intent creation (new)
- `/notifications` — Alerts + audit log viewer (new)
- `/rfq` — RFQ broadcasts + create
- `/analytics` — Charts (funnel bar, pipeline trend)
- `/login` — Auth (login + register toggle)

## Email Triggers (automatic)
1. **User registers** → welcome email
2. **RFQ broadcast created** → vendor notification emails (all vendors in DB)
3. **B2C order created** → order confirmation email (if `shipping_address.email` provided)

## Payment Gateway Flow
1. `POST /api/v1/payments/intent` — create PaymentTransaction (status: created)
2. `POST /api/v1/payments/{id}/confirm` — confirm payment (status: confirmed, sets paid_at)
3. `POST /api/v1/payments/{id}/refund` — full or partial refund (status: refunded)
4. `GET /api/v1/payments/gateways` — list configured gateways (mock, stripe, razorpay)
5. Webhooks: `POST /api/v1/payments/webhook/stripe` and `/webhook/razorpay`

## RFQ Workflow
- **Step 1:** Enter product details (name, qty, target price, deadline, notes)
- **Step 2:** Smart vendor ranking by category fit, name relevance, quote history
- **Step 3:** Broadcast → vendor notification emails sent automatically
- **Quotes View:** Side-by-side comparison sorted by price, lead time, response speed

## Deployment
- **Target:** Autoscale
- **Backend command:** `gunicorn --bind=0.0.0.0:5000 -k uvicorn.workers.UvicornWorker app.main:app`
- **Build:** `cd backend && pip install -r requirements.txt`

## Environment Variables
| Variable | Purpose | Default |
|----------|---------|---------|
| `DATABASE_URL` | PostgreSQL URL for production | SQLite dev.db |
| `JWT_SECRET_KEY` | JWT signing secret | dev-key (change in prod!) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT expiry | 1440 (24h) |
| `STRIPE_SECRET_KEY` | Real Stripe integration | mock fallback |
| `RAZORPAY_KEY_ID` | Real Razorpay integration | mock fallback |
| `RAZORPAY_KEY_SECRET` | Real Razorpay integration | mock fallback |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook validation | skip validation |
| `SENDGRID_API_KEY` | Real SendGrid emails | console fallback |
| `SMTP_HOST` | SMTP email server | console fallback |
| `SMTP_PORT` | SMTP port | 587 |
| `SMTP_USER` | SMTP username | — |
| `SMTP_PASS` | SMTP password | — |
| `EMAIL_FROM` | From address for emails | noreply@procurement.ai |
| `DEFAULT_PAYMENT_GATEWAY` | Default gateway | stripe |
| `BACKEND_URL` | Backend URL for Next.js | http://localhost:8000 |

## Bug Fixes Applied
- Route ordering fix in orders.py (feedback/summary before /{order_id}/feedback)
- Replaced deprecated `@app.on_event('startup')` with `asynccontextmanager` lifespan
- Added indexes to Lead.email, Lead.stage, Lead.segment
- Removed passlib dependency (bcrypt incompatibility) — use bcrypt directly
- Enrichment CSVs present in `data/enrichment/`
- Fixed payment_gateway.py: `confirmed_at` → `paid_at`, removed invalid `order.payment_status`
- Fixed log_audit() call signature in payment_gateway.py
- Removed duplicate /security/ alias endpoints from monitoring.py and analytics.py
