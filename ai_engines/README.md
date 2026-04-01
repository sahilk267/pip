# AI Engines (Phase 1)

## Purpose
Provide the initial categorization, deduplication, scoring, and segmentation models for vendor/client/product data.

## Getting Started
1. Collect sample datasets that will power deduplication or categorization services.
2. Containerize the model inference so it can be called by backend APIs or workers.
3. Track experiments in this folder to move toward production-ready scoring.

## Focus Areas for Phase 1
- Rule-based categorization for vendors/products lives in `categorization_rules.json` (loaded by `backend/app/services/categorization.py` and the `categorize_catalog` Celery task). Extend this JSON to refine taxonomy coverage before promoting ML models.
- Build a basic categorization model that can map products/vendors to the taxonomy in Phase 1 docs.
- Surface confidence and feedback metrics so admins can correct misclassifications.
- Support lead scoring that considers revenue, buying signals, and consent.
- Document feedback loop steps under project-management/PHASE-1-BACKLOG.md.

