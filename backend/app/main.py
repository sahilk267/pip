from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
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
from .routers.analytics import router as analytics_router
from .auth.router import router as auth_router

_STATIC = Path(__file__).resolve().parent / 'static'


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title='Procurement Intelligence Platform',
    version='1.0.0',
    description='AI-powered B2B+B2C commerce — vendor discovery, RFQ, quotes, negotiation & analytics.',
    lifespan=lifespan,
)


@app.get('/', include_in_schema=False)
def root() -> HTMLResponse:
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Procurement Intelligence Platform</title>
  <style>
    :root { font-family: system-ui, sans-serif; background: #0f1419; color: #e7ecf1; }
    body { max-width: 960px; margin: 0 auto; padding: 2rem 1rem; }
    h1 { font-size: 1.75rem; font-weight: 700; margin-bottom: 0.25rem; }
    .subtitle { color: #9aacbc; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 1rem; }
    .card { background: #1a232e; border: 1px solid #2a3540; border-radius: 10px; padding: 1.25rem; }
    .card h3 { font-size: 1rem; margin: 0 0 0.5rem; }
    .card p { font-size: 0.85rem; color: #9aacbc; margin: 0 0 0.75rem; }
    .card a { display: inline-block; font-size: 0.8rem; color: #4b9fff; text-decoration: none; border: 1px solid #4b9fff; border-radius: 5px; padding: 0.3rem 0.75rem; }
    .card a:hover { background: #4b9fff; color: #000; }
    .badge { display: inline-block; font-size: 0.7rem; border-radius: 4px; padding: 0.15rem 0.5rem; margin-bottom: 0.5rem; }
    .badge-api { background: #1e3a5f; color: #4b9fff; }
    .badge-admin { background: #1e3d2a; color: #4bca7a; }
    .badge-auth { background: #3d1e3d; color: #ca7af0; }
    .section-title { font-size: 0.75rem; color: #9aacbc; text-transform: uppercase; letter-spacing: 0.08em; margin: 1.5rem 0 0.5rem; }
  </style>
</head>
<body>
  <h1>Procurement Intelligence Platform</h1>
  <p class="subtitle">AI-powered B2B+B2C commerce — vendor discovery, RFQ, quotes, negotiation &amp; analytics</p>

  <p class="section-title">Authentication</p>
  <div class="grid">
    <div class="card">
      <span class="badge badge-auth">Auth</span>
      <h3>Register / Login</h3>
      <p>Create an account or sign in to get a JWT token.</p>
      <a href="/docs#/auth">Auth Endpoints &rarr;</a>
    </div>
  </div>

  <p class="section-title">API Documentation</p>
  <div class="grid">
    <div class="card">
      <span class="badge badge-api">API</span>
      <h3>Swagger UI</h3>
      <p>Explore all REST endpoints interactively.</p>
      <a href="/docs">Open Swagger &rarr;</a>
    </div>
    <div class="card">
      <span class="badge badge-api">API</span>
      <h3>ReDoc Reference</h3>
      <p>Clean API reference documentation.</p>
      <a href="/redoc">Open ReDoc &rarr;</a>
    </div>
  </div>

  <p class="section-title">Admin Pages</p>
  <div class="grid">
    <div class="card">
      <span class="badge badge-admin">Admin</span>
      <h3>Category Management</h3>
      <p>Override vendor &amp; product category assignments.</p>
      <a href="/admin/categorization">Open &rarr;</a>
    </div>
    <div class="card">
      <span class="badge badge-admin">Admin</span>
      <h3>CRM Dashboard</h3>
      <p>Customer relationship management overview.</p>
      <a href="/admin/crm-dashboard">Open &rarr;</a>
    </div>
  </div>

  <p class="section-title">Quick API Links</p>
  <div class="grid">
    <div class="card">
      <span class="badge badge-api">API</span>
      <h3>Vendors</h3>
      <p>List and manage ingested vendor records.</p>
      <a href="/api/v1/vendors">Browse &rarr;</a>
    </div>
    <div class="card">
      <span class="badge badge-api">API</span>
      <h3>Products</h3>
      <p>Browse B2C product catalog.</p>
      <a href="/api/v1/products">Browse &rarr;</a>
    </div>
    <div class="card">
      <span class="badge badge-api">API</span>
      <h3>Leads / CRM</h3>
      <p>Manage leads and CRM funnel.</p>
      <a href="/api/v1/leads">Browse &rarr;</a>
    </div>
    <div class="card">
      <span class="badge badge-api">API</span>
      <h3>Orders</h3>
      <p>B2C orders, tracking, and payments.</p>
      <a href="/api/v1/orders/b2c">Browse &rarr;</a>
    </div>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)


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

app.include_router(auth_router)
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
app.include_router(analytics_router)
