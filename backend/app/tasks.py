from __future__ import annotations

from datetime import datetime, timezone
import os

from celery import Celery
from celery.schedules import crontab
from celery.signals import task_failure

from .database import SessionLocal
from . import models, crud
from .services.enrichment import enrich_product_attributes, run_enrichment
from .services.monitoring import check_connectors, watch_schema_changes
from .services.categorization import categorize_pending_vendors_and_products
from .services.lead_intelligence import apply_lead_segmentation, enrich_b2b_leads
from .services.crm_communications import send_due_follow_up_reminders
from .services.sales_funnel import compute_sales_funnel_metrics
from .services.marketing_automation import dispatch_campaigns, sync_dispatch_statuses
from .services.marketing_analytics import compute_marketing_analytics
from .services.marketing_campaigns import trigger_campaigns
from .services.marketing_intent import refresh_marketing_intent_scores
from .services.marketing_order_analytics import compute_marketing_order_analytics
from .services.marketing_roi import compute_campaign_roi
from .services.rfq_delivery import sync_delivery_attempts
from .services.rfq_escalation import run_automated_escalation
from .services.rfq_vendor_response import vendor_response_analytics as compute_rfq_vendor_response_analytics

broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')

celery_app = Celery('procurement_phase1', broker=broker_url, backend=result_backend)
celery_app.conf.timezone = 'UTC'
celery_app.conf.beat_schedule = {
    'refresh-vendor-metadata-every-hour': {
        'task': 'backend.app.tasks.refresh_vendor_metadata',
        'schedule': crontab(minute=0, hour='*/1'),
        'options': {'queue': 'enrichment'},
    },
    'enrich-vendor-profiles-every-two-hours': {
        'task': 'backend.app.tasks.enrich_vendor_profiles',
        'schedule': crontab(minute=15, hour='*/2'),
        'options': {'queue': 'enrichment'},
    },
    'enrich-product-attributes-every-three-hours': {
        'task': 'backend.app.tasks.enrich_product_attributes_task',
        'schedule': crontab(minute=20, hour='*/3'),
        'options': {'queue': 'enrichment'},
    },
    'categorize-catalog-every-four-hours': {
        'task': 'backend.app.tasks.categorize_catalog',
        'schedule': crontab(minute=25, hour='*/4'),
        'options': {'queue': 'enrichment'},
    },
    'compute-data-quality-metrics-every-hour': {
        'task': 'backend.app.tasks.compute_data_quality_metrics',
        'schedule': crontab(minute=30),
        'options': {'queue': 'monitoring'},
    },
    'monitor-connectors-every-hour': {
        'task': 'backend.app.tasks.monitor_data_sources',
        'schedule': crontab(minute=45),
        'options': {'queue': 'monitoring'},
    },
    'segment-leads-every-six-hours': {
        'task': 'backend.app.tasks.segment_leads_batch',
        'schedule': crontab(minute=50, hour='*/6'),
        'options': {'queue': 'enrichment'},
    },
    'enrich-b2b-leads-every-hour': {
        'task': 'backend.app.tasks.enrich_b2b_leads_batch',
        'schedule': crontab(minute=10),
        'options': {'queue': 'enrichment'},
    },
    'send-follow-up-reminders-every-hour': {
        'task': 'backend.app.tasks.send_follow_up_reminders',
        'schedule': crontab(minute=5),
        'options': {'queue': 'monitoring'},
    },
    'sales-funnel-snapshot-every-two-hours': {
        'task': 'backend.app.tasks.compute_sales_funnel_snapshot',
        'schedule': crontab(minute=35, hour='*/2'),
        'options': {'queue': 'monitoring'},
    },
    'refresh-marketing-intent-every-two-hours': {
        'task': 'backend.app.tasks.refresh_marketing_intent',
        'schedule': crontab(minute=40, hour='*/2'),
        'options': {'queue': 'enrichment'},
    },
    'marketing-analytics-snapshot-every-four-hours': {
        'task': 'backend.app.tasks.compute_marketing_analytics_snapshot',
        'schedule': crontab(minute=55, hour='*/4'),
        'options': {'queue': 'monitoring'},
    },
    'trigger-nurture-reengagement-every-six-hours': {
        'task': 'backend.app.tasks.trigger_nurture_reengagement_campaigns',
        'schedule': crontab(minute=12, hour='*/6'),
        'options': {'queue': 'monitoring'},
    },
    'dispatch-marketing-automation-every-six-hours': {
        'task': 'backend.app.tasks.dispatch_marketing_automation_campaigns',
        'schedule': crontab(minute=18, hour='*/6'),
        'options': {'queue': 'monitoring'},
    },
    'sync-marketing-dispatch-statuses-every-six-hours': {
        'task': 'backend.app.tasks.sync_marketing_dispatch_statuses',
        'schedule': crontab(minute=22, hour='*/6'),
        'options': {'queue': 'monitoring'},
    },
    'campaign-roi-snapshot-every-six-hours': {
        'task': 'backend.app.tasks.compute_campaign_roi_snapshot',
        'schedule': crontab(minute=24, hour='*/6'),
        'options': {'queue': 'monitoring'},
    },
    'marketing-order-attribution-snapshot-every-six-hours': {
        'task': 'backend.app.tasks.compute_marketing_order_attribution_snapshot',
        'schedule': crontab(minute=26, hour='*/6'),
        'options': {'queue': 'monitoring'},
    },
    'trigger-upsell-cross-sell-every-eight-hours': {
        'task': 'backend.app.tasks.trigger_upsell_cross_sell_campaigns',
        'schedule': crontab(minute=28, hour='*/8'),
        'options': {'queue': 'monitoring'},
    },
    'sync-rfq-delivery-statuses-every-two-hours': {
        'task': 'backend.app.tasks.sync_rfq_delivery_statuses',
        'schedule': crontab(minute=32, hour='*/2'),
        'options': {'queue': 'monitoring'},
    },
    'snapshot-rfq-vendor-response-analytics-every-six-hours': {
        'task': 'backend.app.tasks.snapshot_rfq_vendor_response_analytics',
        'schedule': crontab(minute=44, hour='*/6'),
        'options': {'queue': 'monitoring'},
    },
    'run-rfq-auto-escalation-every-two-hours': {
        'task': 'backend.app.tasks.run_rfq_auto_escalation',
        'schedule': crontab(minute=48, hour='*/2'),
        'options': {'queue': 'monitoring'},
    },
}

_RETRY = {'max_retries': 2, 'countdown': 45}


@task_failure.connect
def _alert_failed_celery_task(sender=None, task_id=None, exception=None, **kwargs):
    if exception is None or sender is None:
        return
    from .services.alerting import create_alert

    title = f'Celery task failed: {getattr(sender, "name", sender)}'
    detail = f'task_id={task_id} error={exception!r}'
    try:
        with SessionLocal() as db:
            create_alert(
                db,
                title=title[:256],
                detail=detail[:2000],
                severity='critical',
                category='celery',
            )
    except Exception:
        pass


@celery_app.task(name='backend.app.tasks.refresh_vendor_metadata')
def refresh_vendor_metadata() -> str:
    """Annotate vendors with the most recent refresh timestamp."""
    timestamp = datetime.now(timezone.utc).isoformat()
    with SessionLocal() as db:
        vendors = db.query(models.Vendor).order_by(models.Vendor.updated_at.asc()).limit(25).all()
        for vendor in vendors:
            metadata = vendor.vendor_metadata or {}
            metadata['last_enriched_at'] = timestamp
            vendor.vendor_metadata = metadata
            db.add(vendor)
            crud.log_audit(db, 'vendor', vendor.id, 'enrichment', f'Set last_enriched_at={timestamp}')
        db.commit()
    return f'Enriched {len(vendors)} vendor records at {timestamp}'


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs=_RETRY,
    name='backend.app.tasks.enrich_vendor_profiles',
)
def enrich_vendor_profiles(self) -> str:
    """Merge B2B enrichment payloads (CSV or B2B_ENRICHMENT_API) into vendor metadata."""
    with SessionLocal() as db:
        stats = run_enrichment(db, limit=15)
        crud.log_audit(
            db,
            'vendor',
            None,
            'enrichment',
            f"Enriched {stats['enriched']} of {stats['scanned']} vendors from enrichment sources",
        )
    return f"Enrichment applied to {stats['enriched']} vendors"


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs=_RETRY,
    name='backend.app.tasks.enrich_product_attributes_task',
)
def enrich_product_attributes_task(self) -> str:
    """Merge B2C attributes (CSV or B2C_ATTRIBUTE_API) into product records."""
    with SessionLocal() as db:
        stats = enrich_product_attributes(db, limit=25)
        crud.log_audit(
            db,
            'product',
            None,
            'enrichment',
            f"Annotated {stats['annotated']} of {stats['scanned']} products with attribute feed",
        )
    return f"Product attributes updated for {stats['annotated']} rows"


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs=_RETRY,
    name='backend.app.tasks.categorize_catalog',
)
def categorize_catalog(self) -> str:
    """Apply rule-based categorization from ai_engines/categorization_rules.json."""
    with SessionLocal() as db:
        stats = categorize_pending_vendors_and_products(db, limit=50)
        crud.log_audit(
            db,
            'catalog',
            None,
            'categorization',
            f"Rule engine: {stats}",
        )
    return f"Categorization: {stats}"


@celery_app.task(name='backend.app.tasks.segment_leads_batch')
def segment_leads_batch() -> str:
    """Recompute lead segments, attribution, and scores."""
    with SessionLocal() as db:
        stats = apply_lead_segmentation(db, limit=500)
        crud.log_audit(
            db,
            'lead',
            None,
            'segmentation',
            f"Lead intelligence batch: {stats}",
        )
    return f"Lead segmentation: {stats}"


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs=_RETRY,
    name='backend.app.tasks.enrich_b2b_leads_batch',
)
def enrich_b2b_leads_batch(self) -> str:
    """Enrich B2B lead revenue/decision-maker fields from enrichment sources."""
    with SessionLocal() as db:
        stats = enrich_b2b_leads(db, limit=200)
        crud.log_audit(
            db,
            'lead',
            None,
            'b2b_enrichment',
            f'B2B lead enrichment batch: {stats}',
        )
    return f'B2B lead enrichment: {stats}'


@celery_app.task(name='backend.app.tasks.send_follow_up_reminders')
def send_follow_up_reminders() -> str:
    """Generate reminders for due CRM follow-ups."""
    with SessionLocal() as db:
        stats = send_due_follow_up_reminders(db, limit=200)
        crud.log_audit(
            db,
            'crm',
            None,
            'follow_up_batch',
            f"CRM follow-up reminders: {stats}",
        )
    return f"CRM follow-up reminders: {stats['reminders_sent']} sent"


@celery_app.task(name='backend.app.tasks.compute_sales_funnel_snapshot')
def compute_sales_funnel_snapshot() -> str:
    """Compute and log sales funnel snapshot metrics."""
    with SessionLocal() as db:
        metrics = compute_sales_funnel_metrics(db, window_days=30)
        crud.log_audit(
            db,
            'crm',
            None,
            'funnel_snapshot',
            f"Sales funnel snapshot: leads={metrics['total_leads']} stages={metrics['stage_counts']}",
        )
    return f"Sales funnel snapshot computed for {metrics['total_leads']} leads"


@celery_app.task(name='backend.app.tasks.refresh_marketing_intent')
def refresh_marketing_intent() -> str:
    """Recompute marketing intent scores for leads from stored signals."""
    with SessionLocal() as db:
        stats = refresh_marketing_intent_scores(db, limit=500)
        crud.log_audit(
            db,
            'marketing',
            None,
            'intent_refresh',
            f"Marketing intent refresh: {stats}",
        )
    return f"Marketing intent refresh: {stats['leads_scored']} updated"


@celery_app.task(name='backend.app.tasks.compute_marketing_analytics_snapshot')
def compute_marketing_analytics_snapshot() -> str:
    """Compute and log marketing analytics snapshot metrics."""
    with SessionLocal() as db:
        metrics = compute_marketing_analytics(db, window_days=30)
        crud.log_audit(
            db,
            'marketing',
            None,
            'analytics_snapshot',
            (
                'Marketing analytics snapshot: '
                f"events={metrics['total_automation_events']} "
                f"channels={len(metrics['conversion_by_channel'])} "
                f"signals={sum(metrics['intent_signals_by_type'].values())}"
            ),
        )
    return f"Marketing analytics snapshot computed for {metrics['window_days']}d"


@celery_app.task(name='backend.app.tasks.trigger_nurture_reengagement_campaigns')
def trigger_nurture_reengagement_campaigns() -> str:
    """Trigger nurture and re-engagement marketing campaigns for eligible leads."""
    with SessionLocal() as db:
        result = trigger_campaigns(db, campaign_type='auto', limit=300, performed_by='celery')
        crud.log_audit(
            db,
            'marketing',
            None,
            'campaign_scheduler',
            (
                'Scheduled nurture/re-engagement trigger: '
                f"triggered={result['triggered']} candidates={result['total_candidates']}"
            ),
        )
    return f"Campaign triggers queued: {result['triggered']}"


@celery_app.task(name='backend.app.tasks.dispatch_marketing_automation_campaigns')
def dispatch_marketing_automation_campaigns() -> str:
    """Dispatch eligible campaign targets to marketing automation providers."""
    with SessionLocal() as db:
        result = dispatch_campaigns(db, campaign_type='auto', limit=300, performed_by='celery')
        crud.log_audit(
            db,
            'marketing',
            None,
            'automation_scheduler',
            (
                'Scheduled marketing automation dispatch: '
                f"dispatched={result['dispatched']} providers={result['providers']}"
            ),
        )
    return f"Marketing automation dispatched: {result['dispatched']}"


@celery_app.task(name='backend.app.tasks.sync_marketing_dispatch_statuses')
def sync_marketing_dispatch_statuses() -> str:
    """Poll provider dispatch statuses and update local delivery state."""
    with SessionLocal() as db:
        result = sync_dispatch_statuses(db, limit=500, performed_by='celery')
        crud.log_audit(
            db,
            'marketing',
            None,
            'automation_sync_scheduler',
            (
                'Scheduled marketing dispatch sync: '
                f"scanned={result['scanned']} sent={result['sent']} failed={result['failed']}"
            ),
        )
    return f"Marketing dispatch sync complete: {result['scanned']} scanned"


@celery_app.task(name='backend.app.tasks.compute_campaign_roi_snapshot')
def compute_campaign_roi_snapshot() -> str:
    """Compute and log campaign ROI snapshot metrics."""
    with SessionLocal() as db:
        result = compute_campaign_roi(db, window_days=30)
        crud.log_audit(
            db,
            'marketing',
            None,
            'campaign_roi_snapshot',
            (
                'Campaign ROI snapshot: '
                f"spend={result['estimated_spend']} "
                f"revenue={result['estimated_revenue']} "
                f"roi={result['overall_roi']}"
            ),
        )
    return f"Campaign ROI snapshot computed for {result['window_days']}d"


@celery_app.task(name='backend.app.tasks.compute_marketing_order_attribution_snapshot')
def compute_marketing_order_attribution_snapshot() -> str:
    """Compute and log marketing-to-order attribution snapshot metrics."""
    with SessionLocal() as db:
        result = compute_marketing_order_analytics(db, window_days=30)
        crud.log_audit(
            db,
            'marketing',
            None,
            'marketing_order_attribution_snapshot',
            (
                'Marketing order attribution snapshot: '
                f"orders={result['orders_total']} "
                f"attributed={result['orders_attributed']} "
                f"revenue={result['attributed_revenue']}"
            ),
        )
    return f"Marketing order attribution snapshot computed for {result['window_days']}d"


@celery_app.task(name='backend.app.tasks.trigger_upsell_cross_sell_campaigns')
def trigger_upsell_cross_sell_campaigns() -> str:
    """Trigger and dispatch upsell/cross-sell campaigns for eligible leads."""
    with SessionLocal() as db:
        result = dispatch_campaigns(db, campaign_type='upsell_cross_sell', limit=250, performed_by='celery')
        crud.log_audit(
            db,
            'marketing',
            None,
            'upsell_cross_sell_scheduler',
            (
                'Scheduled upsell/cross-sell dispatch: '
                f"triggered={result['triggered']} dispatched={result['dispatched']}"
            ),
        )
    return f"Upsell/cross-sell campaigns dispatched: {result['dispatched']}"


@celery_app.task(name='backend.app.tasks.sync_rfq_delivery_statuses')
def sync_rfq_delivery_statuses() -> str:
    """Poll queued RFQ deliveries and update to delivered/failed states."""
    with SessionLocal() as db:
        result = sync_delivery_attempts(db, limit=500, performed_by='celery')
        crud.log_audit(
            db,
            'rfq',
            None,
            'rfq_delivery_scheduler',
            (
                'Scheduled RFQ delivery sync: '
                f"scanned={result['scanned']} delivered={result['delivered']} failed={result['failed']}"
            ),
        )
    return f"RFQ delivery sync complete: {result['scanned']} scanned"


@celery_app.task(name='backend.app.tasks.snapshot_rfq_vendor_response_analytics')
def snapshot_rfq_vendor_response_analytics() -> str:
    """Aggregate vendor response rates for RFQ deliveries and log snapshot."""
    with SessionLocal() as db:
        result = compute_rfq_vendor_response_analytics(db, window_days=30)
        crud.log_audit(
            db,
            'rfq',
            None,
            'rfq_vendor_response_snapshot',
            (
                'RFQ vendor response analytics snapshot: '
                f"deliveries={result['total_deliveries']} "
                f"responses={result['total_responses']} "
                f"reply_rate={result['reply_rate']}"
            ),
        )
    return f"RFQ vendor response analytics snapshot: {result['total_deliveries']} deliveries"


@celery_app.task(name='backend.app.tasks.run_rfq_auto_escalation')
def run_rfq_auto_escalation() -> str:
    """Escalate stale RFQ broadcasts with no vendor responses and optionally expand vendor search."""
    with SessionLocal() as db:
        result = run_automated_escalation(db, response_sla_hours=24, expansion_limit=3, performed_by='celery')
        crud.log_audit(
            db,
            'rfq',
            None,
            'rfq_escalation_scheduler',
            (
                'Scheduled RFQ escalation run: '
                f"scanned={result['scanned']} escalated={result['escalated']} "
                f"alerts={result['alerts_created']} expanded={result['expansion_attempts']}"
            ),
        )
    return f"RFQ escalation run complete: {result['escalated']} escalated"



@celery_app.task(name='backend.app.tasks.compute_data_quality_metrics')
def compute_data_quality_metrics() -> str:
    """Simple quality metrics job that logs vendor/product counts."""
    with SessionLocal() as db:
        vendor_count = db.query(models.Vendor).count()
        product_count = db.query(models.Product).count()
        timestamp = datetime.now(timezone.utc).isoformat()
        detail = f'Vendors={vendor_count}, Products={product_count}'
        crud.log_audit(db, 'metrics', None, 'quality', f'Quality {detail} at {timestamp}')
    return f'Quality metrics computed at {timestamp}'


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs=_RETRY,
    name='backend.app.tasks.monitor_data_sources',
)
def monitor_data_sources(self) -> str:
    """Capture connector health, alert on failures, and surface schema drifts."""
    with SessionLocal() as db:
        statuses = check_connectors(db)
        diffs = watch_schema_changes(db)
        crud.log_audit(
            db,
            'monitor',
            None,
            'connector_health',
            f'Connector counts: {statuses}',
        )
        if diffs:
            crud.log_audit(
                db,
                'monitor',
                None,
                'schema_watch',
                f'Schema warnings: {diffs}',
            )
    return f"Connector health recorded for {len(statuses)} sources with {len(diffs)} schema issues"
