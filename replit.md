# Procurement Intelligence Platform

## Overview
An AI-powered B2B+B2C commerce platform for automated vendor discovery, product catalog ingestion, RFQ broadcasting, quote comparison, negotiation, checkout, and deal closing.

## Tech Stack
- **Backend**: Python FastAPI + SQLAlchemy + Alembic
- **Database**: SQLite (dev) / PostgreSQL (prod)
- **Task Queue**: Celery + Redis
- **Server**: Uvicorn (dev), Gunicorn + UvicornWorker (prod)
- **Frontend**: Not yet implemented (Next.js 14 planned)

## Project Structure
```
backend/           # FastAPI app
  app/
    main.py        # App entry point, routes, startup
    database.py    # SQLAlchemy engine & session (SQLite default)
    models.py      # SQLAlchemy ORM models
    crm_models.py  # CRM-specific models
    schemas.py     # Pydantic schemas (2000+ lines)
    crud.py        # Database CRUD operations
    routers/       # API route handlers (18 routers)
    services/      # Business logic layer
    connectors/    # External data source connectors
    static/        # Static HTML admin pages
  requirements.txt # Python dependencies
  alembic/         # Database migrations
frontend/          # Next.js 14 (planned, not yet implemented)
workers/           # Celery background workers
ai_engines/        # AI/ML modules
```

## Running the App
- **Workflow**: "Start application" runs `uvicorn app.main:app --host 0.0.0.0 --port 5000 --reload` from `backend/`
- **Landing page**: `/` — links to API docs, admin pages
- **API docs**: `/docs` (Swagger), `/redoc`
- **Admin pages**: `/admin/categorization`, `/admin/crm-dashboard`

## Environment Variables
See `.env.example`. Key vars:
- `DATABASE_URL` — defaults to `sqlite:///./dev.db` if not set
- `CELERY_BROKER_URL` — Redis URL for Celery
- `CELERY_RESULT_BACKEND` — Redis URL for results

## Deployment
- Target: autoscale
- Run: `gunicorn --bind=0.0.0.0:5000 --reuse-port -k uvicorn.workers.UvicornWorker app.main:app`
- Must run from `backend/` directory

## Dependencies Installed
- fastapi, uvicorn[standard], sqlalchemy, alembic, pydantic[email], email-validator
- psycopg2-binary, celery[redis], redis, gunicorn
