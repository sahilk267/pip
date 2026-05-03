# Procurement Intelligence — Implementation Checklist
> Based on PROJECT_STATUS.md deep analysis

---

## PHASE A: Bug Fixes & Quick Wins
- [x] Fix route ordering bug (orders/feedback/summary before /{order_id}/feedback)
- [x] Fix @app.on_event deprecation → use lifespan
- [x] Add DB indexes (Lead.segment, Lead.stage, Lead.email)
- [x] Create enrichment CSV sample files (b2b_revenue.csv, b2c_attribute_feed.csv)
- [x] Fix requirements.txt (add all missing deps)

## PHASE B: Authentication & Security
- [x] User model (id, email, hashed_password, role, is_active)
- [x] Alembic migration for users table
- [x] Register endpoint POST /api/v1/auth/register
- [x] Login endpoint POST /api/v1/auth/login (returns JWT)
- [x] JWT middleware / get_current_user dependency
- [x] Protect write endpoints with auth
- [x] Role-based access (admin, sales_rep, customer)

## PHASE C: Next.js Frontend
- [x] Next.js 14 project scaffold (TypeScript + TailwindCSS)
- [x] API client layer (axios/fetch with auth headers)
- [x] Auth pages (Login, Register)
- [x] Dashboard page (KPI cards: vendors, products, leads, orders)
- [x] Vendors page (list, search, add vendor)
- [x] Products page (list, search, add product)
- [x] CRM / Leads page (list, stage update)
- [x] Orders page (B2C orders list + tracking)
- [x] RFQ page (broadcasts list + create)
- [x] Analytics page (charts: funnel, marketing ROI)
- [x] Navigation + layout

## PHASE D: Missing Wiring & Integrations
- [x] Auto-trigger sales notification on B2C order creation
- [x] Auto-trigger customer update on fulfillment status change
- [x] Payment gateway config endpoint wired (env-based gateway selection)
- [x] Email dispatch stub → structured for provider plug-in

## PHASE E: Cleanup & Docs
- [x] Remove /security/ alias duplicate endpoints bloat
- [x] Update README with real phase completion status
- [x] Seed data script verified working
