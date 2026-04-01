# Admin UI & Categorization Plan

This doc outlines the Phase 1 admin surface that lets operators override classifications, review ingestion outcomes, and feed categorization insights back into the data network.

## Objectives
- Provide a vendor/product dashboard that highlights ingestion source, dedup score, and enrichment status.
- Surface categorization/confidence data for each vendor/product and allow admins to override or refine it.
- Track manual annotations that can seed future automation (e.g., product category, region, priority segment).

## Key Screens
1. **Discovery Health Panel**: shows connector status, item counts, last run time (hooks into `/api/v1/ingestion/discovery` and the `monitor_data_sources` audit log).
2. **Vendor Profile Table**: columns for name, source, normalized score, enrichment tags (revenue band, decision-maker), and actions (view/edit metadata, reopen dedup check).
3. **Categorization Feedback Workspace**: multi-select categories (from AI engines), manual overrides, confidence request field, and a comment log stored in the audit trail through a backend endpoint (to be implemented once `ai_engines` exposes rules).
4. **Product Catalog Normalization View**: list of product SKUs with normalization status, image/attribute preview, and manual input for missing attributes.

## Workstreams
- **Backend hooks**: expand `/api/v1/vendors`/`/api/v1/products` to include categorization/confidence metadata and categories (per `schemas`).
- **Feedback loop**: build an endpoint (e.g., `/api/v1/admin/feedback`) that records overrides and kicks off audit entries for governance.
- **Frontend components**: use Next.js pages under `/admin` with server-side fetching (via `getServerSideProps`) so dashboards read from the backend metrics and connector audit logs.

## Next Steps
1. Prototype the admin layouts with seeded data (can reuse the connectors and enrichment metadata from the backend).
2. Connect the categorization inputs to a future `ai_engines` service once the model is ready, allowing manual overrides to persist to the database.
3. Surface consent/conflict states for B2B/B2C customers (leads, consent) alongside vendor relationships for a holistic admin view.

## References
- `frontend/README.md` focus areas
- `PHASE-1-IMPLEMENTATION-PLAN.md` Step 7 and implementation notes
- `backend/app/crm_models.py` and `crud` for consent tracking
