from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import init_db
from .routers.admin_categorization import router as admin_categorization_router
from .routers.ingestion import router as ingestion_router
from .routers.crm import router as crm_router
from .routers.compliance import router as compliance_router
from .routers.monitoring import router as monitoring_router
from .routers.operations import router as operations_router
from .routers.i18n_api import router as i18n_router
from .routers.integrations import router as integrations_router
from .routers.enrichment import router as enrichment_router
from .routers.marketing import router as marketing_router
from .routers.orders import router as orders_router
from .routers.cart import router as cart_router
from .routers.rfq import router as rfq_router
from .routers.automation import router as automation_router
from .routers.messages import router as messages_router
from .routers.escalations import router as escalations_router
from .routers.market_intelligence import router as market_intelligence_router

_STATIC = Path(__file__).resolve().parent / 'static'

app = FastAPI(
    title='Procurement Intelligence - Phase 1',
    version='0.1.0',
    description='Vendor/product ingestion plus CRM endpoints.',
)


@app.on_event('startup')
def startup_event() -> None:
    init_db()


@app.get('/admin/categorization', include_in_schema=False)
def admin_categorization_page() -> FileResponse:
    page = _STATIC / 'admin' / 'categorization.html'
    return FileResponse(page)


@app.get('/admin/crm-dashboard', include_in_schema=False)
def admin_crm_dashboard_page() -> FileResponse:
    page = _STATIC / 'admin' / 'crm-dashboard.html'
    return FileResponse(page)


if _STATIC.exists():
    app.mount('/static', StaticFiles(directory=str(_STATIC)), name='static')

app.include_router(ingestion_router)
app.include_router(crm_router)
app.include_router(compliance_router)
app.include_router(monitoring_router)
app.include_router(operations_router)
app.include_router(i18n_router)
app.include_router(integrations_router)
app.include_router(admin_categorization_router)
app.include_router(enrichment_router)
app.include_router(marketing_router)
app.include_router(orders_router)
app.include_router(cart_router)
app.include_router(rfq_router)
app.include_router(automation_router)
app.include_router(messages_router)
app.include_router(escalations_router)
app.include_router(market_intelligence_router)
