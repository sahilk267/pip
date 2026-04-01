import os

# Tests always use an isolated SQLite file so drop_all never targets Postgres from .env.
_test_db = os.path.abspath(os.path.join(os.path.dirname(__file__), '.pytest.db'))
os.environ['DATABASE_URL'] = f'sqlite:///{_test_db}'

import pytest

from backend.app.database import Base, engine, init_db, SessionLocal
from backend.app import models
from backend.app import crm_models


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    init_db()
    with SessionLocal() as db:
        for model in (models.AuditLog, models.LeadStageTransition, models.CRMCommunication, models.Product, models.Vendor, models.Lead, models.DataSource, models.Alert, crm_models.Customer):
            db.query(model).delete()
        db.commit()
    yield
