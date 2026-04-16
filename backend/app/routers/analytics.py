from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit
from ..database import get_db
from ..services.ai_model_governance import list_model_records
from ..services.alerting import create_alert, resolve_alert
from ..services.compliance import generate_compliance_report
from ..services.deal_outcomes import deal_outcome_analytics
from ..services.escalation_rules import list_escalation_records, list_escalation_rules
from ..services.external_integrations import list_integrations, list_sync_records
from ..services.legal_review import list_legal_reviews
from ..services.marketing_analytics import compute_marketing_analytics
from ..services.marketing_order_analytics import compute_marketing_order_analytics
from ..services.marketing_roi import compute_campaign_roi
from ..services.message_templates import list_message_templates
from ..services.order_feedback import order_deal_feedback_summary
from ..services.sales_funnel import compute_sales_funnel_metrics
from ..services.sales_playbooks import build_sales_playbook, build_sales_playbook_queue
from ..services.market_intelligence import list_feedback_loop_records

router = APIRouter(tags=['analytics'])


# ---------------------------------------------------------------------------
# 1. Drill-down analytics
# ---------------------------------------------------------------------------

@router.get('/api/v1/analytics/sales/drill-down')
def get_phase4_sales_drill_down(
    window_days: int = Query(default=30, ge=1, le=365),
    region: str | None = Query(default=None),
    segment: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """Drill-down analytics: funnel metrics, optionally filtered by region/segment."""
    metrics = compute_sales_funnel_metrics(db, window_days=window_days)

    # Apply opt-in drill-down filters via lead-level counts
    if region or segment:
        q = db.query(models.Lead)
        if segment:
            q = q.filter(models.Lead.segment == segment)
        filtered_leads = q.all()
        stage_counts_drilled: dict[str, int] = defaultdict(int)
        for lead in filtered_leads:
            stage_counts_drilled[str(lead.stage or 'unknown')] += 1
        metrics['drill_down'] = {
            'region': region,
            'segment': segment,
            'lead_count': len(filtered_leads),
            'stage_counts': dict(stage_counts_drilled),
        }

    return metrics


# ---------------------------------------------------------------------------
# 2. Predictive analytics
# ---------------------------------------------------------------------------

@router.get('/api/v1/analytics/sales/predictive')
def get_phase4_predictive_analytics(
    window_days: int = Query(default=30, ge=1, le=365),
    forecast_days: int = Query(default=30, ge=1, le=90),
    db: Session = Depends(get_db),
) -> dict:
    """Predictive analytics: project future conversions and churn risk."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(1, window_days))

    recent_converted = (
        db.query(models.Lead)
        .filter(models.Lead.stage == 'converted', models.Lead.created_at >= cutoff)
        .count()
    )
    total_active = (
        db.query(models.Lead)
        .filter(models.Lead.stage.notin_(['converted', 'lost', 'disqualified']))
        .count()
    )
    daily_conversion_rate = (recent_converted / max(1, window_days))
    projected_conversions = round(daily_conversion_rate * forecast_days, 2)

    # Churn risk: leads with no stage transition in window and low score
    stale_lead_ids = {
        row.lead_id
        for row in db.query(models.LeadStageTransition.lead_id)
        .filter(models.LeadStageTransition.changed_at >= cutoff)
        .all()
    }
    churn_risk_count = (
        db.query(models.Lead)
        .filter(
            models.Lead.stage.notin_(['converted', 'lost', 'disqualified']),
            models.Lead.lead_score < 15,
            models.Lead.id.notin_(stale_lead_ids) if stale_lead_ids else models.Lead.lead_score < 15,
        )
        .count()
    )

    win_loss = deal_outcome_analytics(db, window_days=window_days)
    return {
        'generated_at': now,
        'window_days': window_days,
        'forecast_days': forecast_days,
        'recent_conversions': recent_converted,
        'projected_conversions': projected_conversions,
        'total_active_leads': total_active,
        'churn_risk_leads': churn_risk_count,
        'win_rate': win_loss.get('win_rate', 0.0),
        'total_deal_value': win_loss.get('total_deal_value', 0.0),
    }


# ---------------------------------------------------------------------------
# 3. Anomaly detection
# ---------------------------------------------------------------------------

@router.post('/api/v1/analytics/anomaly-detection/run')
def run_phase4_anomaly_detection(
    window_minutes: int = Query(default=60, ge=5, le=1440),
    spike_threshold: int = Query(default=5, ge=1),
    performed_by: str = Query(default='analytics_system'),
    db: Session = Depends(get_db),
) -> dict:
    """Scan recent alerts for volume spikes; create an anomaly alert if threshold breached."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    recent_alert_count = (
        db.query(models.Alert)
        .filter(models.Alert.created_at >= cutoff, models.Alert.resolved == False)
        .count()
    )
    anomaly_triggered = recent_alert_count >= spike_threshold
    created_alert_id = None
    if anomaly_triggered:
        alert = create_alert(
            db,
            title='Anomaly detected: alert volume spike',
            detail=f'{recent_alert_count} unresolved alerts in last {window_minutes}min (threshold={spike_threshold})',
            severity='critical',
            category='anomaly_detection',
        )
        created_alert_id = alert.id
        log_audit(
            db, 'analytics', None, 'anomaly_detected',
            f'alert_count={recent_alert_count} window_minutes={window_minutes}',
            performed_by=performed_by,
        )
    return {
        'window_minutes': window_minutes,
        'recent_unresolved_alerts': recent_alert_count,
        'spike_threshold': spike_threshold,
        'anomaly_triggered': anomaly_triggered,
        'anomaly_alert_id': created_alert_id,
    }


@router.get('/api/v1/analytics/anomaly-detection/results')
def get_phase4_anomaly_results(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    """List recent anomaly detection alerts."""
    rows = (
        db.query(models.Alert)
        .filter(models.Alert.category == 'anomaly_detection')
        .order_by(models.Alert.created_at.desc(), models.Alert.id.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return [
        {
            'id': row.id,
            'title': row.title,
            'detail': row.detail,
            'severity': row.severity,
            'category': row.category,
            'resolved': row.resolved,
            'created_at': row.created_at,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# 4. Automated bug triage
# ---------------------------------------------------------------------------

@router.post('/api/v1/analytics/bug-triage/run')
def run_phase4_bug_triage(
    window_hours: int = Query(default=24, ge=1, le=168),
    performed_by: str = Query(default='analytics_system'),
    db: Session = Depends(get_db),
) -> dict:
    """Scan AuditLog for error/failure entries and categorize into severity buckets."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    failure_keywords = ['failed', 'error', 'exception', 'critical', 'timeout']

    rows = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.created_at >= cutoff)
        .all()
    )

    buckets: dict[str, list[dict]] = {'critical': [], 'high': [], 'medium': [], 'low': []}
    for row in rows:
        detail_lower = (row.detail or '').lower()
        action_lower = (row.action or '').lower()
        text = detail_lower + ' ' + action_lower
        if not any(kw in text for kw in failure_keywords):
            continue
        if 'critical' in text or 'exception' in text:
            severity = 'critical'
        elif 'failed' in text or 'error' in text:
            severity = 'high'
        elif 'timeout' in text:
            severity = 'medium'
        else:
            severity = 'low'
        buckets[severity].append({
            'audit_log_id': row.id,
            'entity_type': row.entity_type,
            'action': row.action,
            'detail': (row.detail or '')[:256],
            'created_at': row.created_at,
        })

    total_issues = sum(len(v) for v in buckets.values())
    log_audit(
        db, 'analytics', None, 'bug_triage_run',
        f'issues_found={total_issues} window_hours={window_hours}',
        performed_by=performed_by,
    )
    return {
        'window_hours': window_hours,
        'total_issues': total_issues,
        'by_severity': {k: len(v) for k, v in buckets.items()},
        'critical_issues': buckets['critical'][:10],
        'high_issues': buckets['high'][:10],
    }


@router.get('/api/v1/analytics/bug-triage/issues')
def get_phase4_bug_triage_issues(
    window_hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
) -> list[dict]:
    """List bug triage audit log entries (failures/errors) from window."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    failure_keywords = ['failed', 'error', 'exception', 'critical', 'timeout']
    rows = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.created_at >= cutoff)
        .order_by(models.AuditLog.created_at.desc())
        .limit(200)
        .all()
    )
    issues = []
    for row in rows:
        detail_lower = (row.detail or '').lower()
        action_lower = (row.action or '').lower()
        if any(kw in detail_lower + action_lower for kw in failure_keywords):
            issues.append({
                'id': row.id,
                'entity_type': row.entity_type,
                'action': row.action,
                'detail': (row.detail or '')[:256],
                'performed_by': row.performed_by,
                'created_at': row.created_at,
            })
    return issues


# ---------------------------------------------------------------------------
# 5. Dev productivity metrics (optional)
# ---------------------------------------------------------------------------

@router.get('/api/v1/analytics/dev-productivity')
def get_phase4_dev_productivity(
    window_days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
) -> dict:
    """Aggregate system actions by entity_type and performed_by for dev productivity metrics."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    rows = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.created_at >= cutoff)
        .all()
    )
    by_entity: dict[str, int] = defaultdict(int)
    by_actor: dict[str, int] = defaultdict(int)
    for row in rows:
        by_entity[str(row.entity_type or 'unknown')] += 1
        by_actor[str(row.performed_by or 'system')] += 1

    return {
        'generated_at': datetime.now(timezone.utc),
        'window_days': window_days,
        'total_actions': len(rows),
        'by_entity_type': dict(sorted(by_entity.items(), key=lambda x: -x[1])[:20]),
        'top_actors': dict(sorted(by_actor.items(), key=lambda x: -x[1])[:10]),
    }


# ---------------------------------------------------------------------------
# 6. Root cause analysis
# ---------------------------------------------------------------------------

@router.get('/api/v1/analytics/root-cause-analysis')
def get_phase4_root_cause_analysis(
    window_hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
) -> dict:
    """Correlate Alert spikes with AuditLog events for root cause patterns."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)

    alerts = (
        db.query(models.Alert)
        .filter(models.Alert.created_at >= cutoff)
        .all()
    )
    category_counts: dict[str, int] = defaultdict(int)
    severity_counts: dict[str, int] = defaultdict(int)
    for alert in alerts:
        category_counts[str(alert.category or 'unknown')] += 1
        severity_counts[str(alert.severity or 'unknown')] += 1

    top_category = max(category_counts, key=lambda k: category_counts[k], default='none')

    # Find AuditLog events in the same window that match the top alert category
    correlated_logs = (
        db.query(models.AuditLog)
        .filter(
            models.AuditLog.created_at >= cutoff,
            models.AuditLog.entity_type == top_category,
        )
        .order_by(models.AuditLog.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        'generated_at': datetime.now(timezone.utc),
        'window_hours': window_hours,
        'total_alerts': len(alerts),
        'by_category': dict(category_counts),
        'by_severity': dict(severity_counts),
        'likely_root_category': top_category,
        'correlated_audit_events': [
            {
                'id': row.id,
                'entity_type': row.entity_type,
                'action': row.action,
                'detail': (row.detail or '')[:256],
                'created_at': row.created_at,
            }
            for row in correlated_logs
        ],
    }


# ---------------------------------------------------------------------------
# 7. Alert fatigue suppression
# ---------------------------------------------------------------------------

@router.post('/api/v1/analytics/alert-fatigue/suppress')
def run_phase4_alert_fatigue_suppression(
    window_minutes: int = Query(default=60, ge=5, le=1440),
    category: str | None = Query(default=None),
    performed_by: str = Query(default='analytics_system'),
    db: Session = Depends(get_db),
) -> dict:
    """Auto-resolve duplicate/repeated alerts within a rolling time window."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    q = (
        db.query(models.Alert)
        .filter(models.Alert.created_at >= cutoff, models.Alert.resolved == False)
    )
    if category:
        q = q.filter(models.Alert.category == category)
    alerts = q.order_by(models.Alert.title, models.Alert.created_at).all()

    seen_titles: set[str] = set()
    suppressed_ids: list[int] = []
    for alert in alerts:
        key = str(alert.title or '').strip().lower()
        if key in seen_titles:
            resolve_alert(db, alert.id)
            suppressed_ids.append(alert.id)
        else:
            seen_titles.add(key)

    if suppressed_ids:
        log_audit(
            db, 'analytics', None, 'alert_fatigue_suppressed',
            f'suppressed={len(suppressed_ids)} window_minutes={window_minutes}',
            performed_by=performed_by,
        )

    return {
        'window_minutes': window_minutes,
        'category_filter': category,
        'total_evaluated': len(alerts),
        'suppressed_count': len(suppressed_ids),
        'suppressed_alert_ids': suppressed_ids,
    }


# ---------------------------------------------------------------------------
# 8. Analytics data anonymization
# ---------------------------------------------------------------------------

@router.get('/api/v1/analytics/anonymized-data')
def get_phase4_anonymized_data(
    limit: int = Query(default=100, ge=1, le=500),
    segment: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """Return anonymized lead analytics with PII masked (email hashed, name/phone redacted)."""
    q = db.query(models.Lead)
    if segment:
        q = q.filter(models.Lead.segment == segment)
    leads = q.order_by(models.Lead.id.desc()).limit(max(1, min(limit, 500))).all()

    anonymized = []
    for lead in leads:
        email_hash = (
            hashlib.sha256(lead.email.encode()).hexdigest()[:16]
            if lead.email else 'redacted'
        )
        anonymized.append({
            'anon_id': f'lead_{lead.id}',
            'email_hash': email_hash,
            'stage': lead.stage,
            'segment': lead.segment,
            'lead_score': lead.lead_score,
            'attribution_channel': lead.attribution_channel,
            'created_at': lead.created_at,
        })

    return {
        'generated_at': datetime.now(timezone.utc),
        'total': len(anonymized),
        'records': anonymized,
    }


# ---------------------------------------------------------------------------
# 9. Continuous improvement feedback
# ---------------------------------------------------------------------------

@router.get('/api/v1/analytics/continuous-improvement/feedback')
def get_phase4_continuous_improvement_feedback(
    window_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> dict:
    """Aggregate order/deal feedback for continuous improvement tracking."""
    return order_deal_feedback_summary(db, window_days=window_days)


# ---------------------------------------------------------------------------
# 10. Audit logging
# ---------------------------------------------------------------------------

@router.get('/api/v1/analytics/audit-logs')
def get_phase4_audit_logs(
    entity_type: str | None = Query(default=None),
    action: str | None = Query(default=None),
    performed_by: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[dict]:
    """List audit log entries with optional filters."""
    q = db.query(models.AuditLog)
    if entity_type:
        q = q.filter(models.AuditLog.entity_type == entity_type)
    if action:
        q = q.filter(models.AuditLog.action == action)
    if performed_by:
        q = q.filter(models.AuditLog.performed_by == performed_by)
    rows = q.order_by(models.AuditLog.created_at.desc(), models.AuditLog.id.desc()).limit(
        max(1, min(limit, 500))
    ).all()
    return [
        {
            'id': row.id,
            'entity_type': row.entity_type,
            'entity_id': row.entity_id,
            'action': row.action,
            'detail': row.detail,
            'performed_by': row.performed_by,
            'created_at': row.created_at,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# 11 & 12. Sales enablement recommendations and playbooks
# ---------------------------------------------------------------------------

@router.get('/api/v1/analytics/sales-enablement/recommendations')
def get_phase4_sales_enablement_recommendations(
    lead_id: int = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    """Sales enablement: next-best-action playbook for a specific lead."""
    lead = db.query(models.Lead).filter(models.Lead.id == lead_id).first()
    if lead is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail='Lead not found')
    return build_sales_playbook(db, lead)


@router.get('/api/v1/analytics/sales-playbooks')
def get_phase4_sales_playbooks(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """Sales playbooks queue: prioritized list of leads with recommended next actions."""
    return build_sales_playbook_queue(db, limit=limit)


# ---------------------------------------------------------------------------
# 13. Rep training / onboarding tracking
# ---------------------------------------------------------------------------

@router.post('/api/v1/analytics/rep-training/log')
def log_phase4_rep_training(
    rep_id: str = Query(...),
    module: str = Query(...),
    status: str = Query(default='completed'),
    performed_by: str = Query(default='hr_system'),
    db: Session = Depends(get_db),
) -> dict:
    """Log a rep training/onboarding completion event."""
    log_audit(
        db, 'rep_training', None, 'training_completed',
        f'rep_id={rep_id} module={module} status={status}',
        performed_by=performed_by,
    )
    return {
        'rep_id': rep_id,
        'module': module,
        'status': status,
        'logged_at': datetime.now(timezone.utc),
    }


@router.get('/api/v1/analytics/rep-training/status')
def get_phase4_rep_training_status(
    rep_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    """List rep training/onboarding audit log entries."""
    q = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.entity_type == 'rep_training')
        .order_by(models.AuditLog.created_at.desc())
    )
    if rep_id:
        q = q.filter(models.AuditLog.detail.contains(f'rep_id={rep_id}'))
    rows = q.limit(max(1, min(limit, 200))).all()
    return [
        {
            'id': row.id,
            'detail': row.detail,
            'performed_by': row.performed_by,
            'created_at': row.created_at,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# 14. Sales content analytics
# ---------------------------------------------------------------------------

@router.post('/api/v1/analytics/sales-content/track')
def track_phase4_sales_content(
    content_id: str = Query(...),
    content_type: str = Query(default='playbook'),
    rep_id: str | None = Query(default=None),
    performed_by: str = Query(default='sales_system'),
    db: Session = Depends(get_db),
) -> dict:
    """Track sales content access/usage (playbooks, battlecards, etc.)."""
    detail = f'content_id={content_id} content_type={content_type}'
    if rep_id:
        detail += f' rep_id={rep_id}'
    log_audit(db, 'sales_content', None, 'content_accessed', detail, performed_by=performed_by)
    return {
        'content_id': content_id,
        'content_type': content_type,
        'rep_id': rep_id,
        'tracked_at': datetime.now(timezone.utc),
    }


@router.get('/api/v1/analytics/sales-content/analytics')
def get_phase4_sales_content_analytics(
    window_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> dict:
    """Aggregate sales content access statistics."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    rows = (
        db.query(models.AuditLog)
        .filter(
            models.AuditLog.entity_type == 'sales_content',
            models.AuditLog.action == 'content_accessed',
            models.AuditLog.created_at >= cutoff,
        )
        .all()
    )
    by_content: dict[str, int] = defaultdict(int)
    by_type: dict[str, int] = defaultdict(int)
    for row in rows:
        detail = row.detail or ''
        # parse content_id=X content_type=Y from detail
        cid = 'unknown'
        ctype = 'unknown'
        for part in detail.split():
            if part.startswith('content_id='):
                cid = part.split('=', 1)[1]
            elif part.startswith('content_type='):
                ctype = part.split('=', 1)[1]
        by_content[cid] += 1
        by_type[ctype] += 1

    return {
        'generated_at': datetime.now(timezone.utc),
        'window_days': window_days,
        'total_accesses': len(rows),
        'by_content_id': dict(sorted(by_content.items(), key=lambda x: -x[1])[:20]),
        'by_content_type': dict(by_type),
    }


# ---------------------------------------------------------------------------
# 15 & 16. Knowledge base + AI Q&A
# ---------------------------------------------------------------------------

@router.post('/api/v1/analytics/knowledge-base/entries')
def add_phase4_knowledge_base_entry(
    title: str = Query(...),
    content: str = Query(...),
    category: str = Query(default='general'),
    created_by: str = Query(default='admin'),
    db: Session = Depends(get_db),
) -> dict:
    """Add an entry to the searchable knowledge base (stored as audit log)."""
    detail = f'title={title} category={category} content={content[:500]}'
    log_audit(db, 'kb_entry', None, 'kb_entry_added', detail, performed_by=created_by)
    return {
        'title': title,
        'category': category,
        'created_by': created_by,
        'created_at': datetime.now(timezone.utc),
    }


@router.get('/api/v1/analytics/knowledge-base/search')
def search_phase4_knowledge_base(
    q: str = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Search knowledge base entries by keyword."""
    rows = (
        db.query(models.AuditLog)
        .filter(
            models.AuditLog.entity_type == 'kb_entry',
            models.AuditLog.detail.contains(q),
        )
        .order_by(models.AuditLog.created_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    results = []
    for row in rows:
        detail = row.detail or ''
        title = 'unknown'
        category = 'general'
        for part in detail.split(' category='):
            if part.startswith('title='):
                title = part.split('=', 1)[1].split(' ')[0]
                break
        if ' category=' in detail:
            category = detail.split(' category=')[1].split(' ')[0]
        results.append({
            'id': row.id,
            'title': title,
            'category': category,
            'detail_snippet': detail[:256],
            'created_at': row.created_at,
        })
    return results


@router.post('/api/v1/analytics/ai-qa/ask')
def ask_phase4_ai_qa(
    question: str = Query(...),
    limit: int = Query(default=3, ge=1, le=10),
    db: Session = Depends(get_db),
) -> dict:
    """AI Q&A: search knowledge base for answers matching the question."""
    # Use first significant word as search term
    search_terms = [w.strip('?.,!').lower() for w in question.split() if len(w) > 3]
    matches: list[dict] = []
    seen_ids: set[int] = set()
    for term in search_terms[:5]:
        rows = (
            db.query(models.AuditLog)
            .filter(
                models.AuditLog.entity_type == 'kb_entry',
                models.AuditLog.detail.contains(term),
            )
            .order_by(models.AuditLog.created_at.desc())
            .limit(5)
            .all()
        )
        for row in rows:
            if row.id not in seen_ids and len(matches) < limit:
                seen_ids.add(row.id)
                matches.append({
                    'kb_entry_id': row.id,
                    'detail_snippet': (row.detail or '')[:300],
                    'created_at': row.created_at,
                })
    return {
        'question': question,
        'answer_count': len(matches),
        'answers': matches,
    }


# ---------------------------------------------------------------------------
# 17. Training/onboarding modules
# ---------------------------------------------------------------------------

@router.post('/api/v1/analytics/training-modules/log')
def log_phase4_training_module(
    rep_id: str = Query(...),
    module_name: str = Query(...),
    progress_pct: int = Query(default=100, ge=0, le=100),
    performed_by: str = Query(default='lms_system'),
    db: Session = Depends(get_db),
) -> dict:
    """Log rep progress on a training/onboarding module."""
    log_audit(
        db, 'training_module', None, 'module_progress',
        f'rep_id={rep_id} module={module_name} progress_pct={progress_pct}',
        performed_by=performed_by,
    )
    return {
        'rep_id': rep_id,
        'module_name': module_name,
        'progress_pct': progress_pct,
        'logged_at': datetime.now(timezone.utc),
    }


@router.get('/api/v1/analytics/training-modules/progress')
def get_phase4_training_module_progress(
    rep_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    """Aggregate training module progress by rep."""
    q = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.entity_type == 'training_module')
        .order_by(models.AuditLog.created_at.desc())
    )
    if rep_id:
        q = q.filter(models.AuditLog.detail.contains(f'rep_id={rep_id}'))
    rows = q.limit(max(1, min(limit, 200))).all()

    by_rep: dict[str, dict[str, int]] = defaultdict(dict)
    for row in rows:
        detail = row.detail or ''
        rid, mod, pct = 'unknown', 'unknown', 0
        for part in detail.split():
            if part.startswith('rep_id='):
                rid = part.split('=', 1)[1]
            elif part.startswith('module='):
                mod = part.split('=', 1)[1]
            elif part.startswith('progress_pct='):
                pct = int(part.split('=', 1)[1])
        by_rep[rid][mod] = pct

    return {
        'generated_at': datetime.now(timezone.utc),
        'total_records': len(rows),
        'progress_by_rep': dict(by_rep),
    }


# ---------------------------------------------------------------------------
# 18. Regional legal review (Phase 4 context: analytics modules)
# ---------------------------------------------------------------------------

@router.get('/api/v1/analytics/governance/legal-reviews')
def get_phase4_legal_reviews(
    region: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    """List regional legal reviews relevant to analytics/reporting (GDPR, CCPA, DPDP, PCI DSS)."""
    rows = list_legal_reviews(db, region=region, limit=limit)
    return [
        {
            'id': row.id,
            'region': row.region,
            'regulation': row.regulation,
            'entity_type': row.entity_type,
            'status': row.status,
            'reviewer': row.reviewer,
            'reviewed_at': row.reviewed_at,
            'notes': row.notes,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# 19. Multi-language support (Phase 4 context: analytics dashboards)
# ---------------------------------------------------------------------------

@router.get('/api/v1/analytics/governance/multi-language')
def get_phase4_multi_language(
    locale: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    """List message templates for analytics dashboard multi-language support."""
    rows = list_message_templates(db, limit=limit)
    return [
        {
            'id': row.id,
            'template_code': row.template_code,
            'default_locale': row.default_locale,
            'template_type': row.template_type,
            'translations': row.translations,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# 20. External analytics/LMS tool integration
# ---------------------------------------------------------------------------

@router.get('/api/v1/analytics/external-integrations')
def get_phase4_external_integrations(
    provider: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    """List external analytics/LMS tool integrations."""
    rows = list_integrations(db, provider=provider, limit=limit)
    return [
        {
            'id': row.id,
            'name': row.name,
            'provider': row.provider,
            'status': row.status,
            'entity_sync_types': row.entity_sync_types,
            'api_endpoint': row.api_endpoint,
            'sync_direction': row.sync_direction,
            'field_mappings': row.field_mappings,
            'integration_metadata': row.integration_metadata,
            'last_sync_at': row.last_sync_at,
            'configured_by': row.configured_by,
            'created_at': row.created_at,
        }
        for row in rows
    ]


@router.get('/api/v1/analytics/external-integrations/{integration_id}/sync-records')
def get_phase4_integration_sync_records(
    integration_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    """List sync records for an external analytics/LMS integration."""
    rows = list_sync_records(db, integration_id=integration_id, limit=limit)
    return [
        {
            'id': row.id,
            'integration_id': row.integration_id,
            'status': row.status,
            'records_synced': row.records_synced,
            'error_detail': row.error_detail,
            'synced_at': row.synced_at,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# 21. Escalation playbook (Phase 4 context: analytics/enablement failures)
# ---------------------------------------------------------------------------

@router.get('/api/v1/analytics/governance/escalation-playbook')
def get_phase4_escalation_playbook(
    entity_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    """Escalation playbook rules and recent records for analytics/enablement failures."""
    rules = list_escalation_rules(db, limit=limit)
    records = list_escalation_records(db, entity_type=entity_type, limit=limit)
    return {
        'rules': [
            {
                'id': r.id,
                'name': r.name,
                'entity_type': r.entity_type,
                'trigger_condition': r.trigger_condition,
                'action': r.action,
                'active': r.active,
            }
            for r in rules
        ],
        'recent_records': [
            {
                'id': r.id,
                'rule_id': r.rule_id,
                'entity_type': r.entity_type,
                'entity_id': r.entity_id,
                'status': r.status,
                'triggered_at': r.triggered_at,
            }
            for r in records
        ],
    }


# ---------------------------------------------------------------------------
# 22. AI model governance records (Phase 4: analytics and enablement modules)
# ---------------------------------------------------------------------------

@router.get('/api/v1/analytics/governance/ai-model-governance')
def get_phase4_ai_model_governance(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    """List AI model governance records for analytics and enablement modules."""
    rows = list_model_records(db, limit=limit)
    return [
        {
            'id': row.id,
            'model_name': row.model_name,
            'model_version': row.model_version,
            'model_type': row.model_type,
            'status': row.status,
            'approved_by': row.approved_by,
            'created_by': row.created_by,
            'created_at': row.created_at,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# 23. Governance/compliance records (Phase 4: analytics modules)
# ---------------------------------------------------------------------------

@router.get('/api/v1/analytics/governance/compliance-records')
def get_phase4_compliance_records(
    window_minutes: int = Query(default=1440, ge=1),
    db: Session = Depends(get_db),
) -> dict:
    """Governance and compliance records for analytics modules."""
    result = generate_compliance_report(db, window_minutes=window_minutes)
    if 'recent_entries' in result:
        result['recent_entries'] = [
            {
                'id': r.id,
                'action': r.action,
                'entity_type': r.entity_type,
                'detail': r.detail,
                'created_at': str(r.created_at),
            }
            for r in result['recent_entries']
        ]
    return result


# ---------------------------------------------------------------------------
# 24. Marketing attribution analytics
# ---------------------------------------------------------------------------

@router.get('/api/v1/analytics/marketing/attribution')
def get_phase4_marketing_attribution(
    window_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> dict:
    """Marketing attribution analytics: orders attributed to campaign dispatches."""
    return compute_marketing_order_analytics(db, window_days=window_days)


# ---------------------------------------------------------------------------
# 25. Marketing content performance analytics
# ---------------------------------------------------------------------------

@router.get('/api/v1/analytics/marketing/content-performance')
def get_phase4_marketing_content_performance(
    window_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> dict:
    """Marketing content performance: intent signals, automation events, lead attribution."""
    return compute_marketing_analytics(db, window_days=window_days)


# ---------------------------------------------------------------------------
# 25b. Marketing ROI
# ---------------------------------------------------------------------------

@router.get('/api/v1/analytics/marketing/roi')
def get_phase4_marketing_roi(
    window_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> dict:
    """Marketing campaign ROI metrics."""
    return compute_campaign_roi(db, window_days=window_days)


# ---------------------------------------------------------------------------
# 26. Marketing analytics feedback loop
# ---------------------------------------------------------------------------

@router.get('/api/v1/analytics/marketing/feedback-loop')
def get_phase4_marketing_feedback_loop(
    campaign_id: int | None = Query(default=None),
    lead_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Marketing analytics feedback loop records."""
    rows = list_feedback_loop_records(db, campaign_id=campaign_id, lead_id=lead_id, limit=limit)
    return [
        {
            'id': row.id,
            'campaign_id': row.campaign_id,
            'lead_id': row.lead_id,
            'signal': row.signal,
            'source': row.source,
            'metadata': row.feedback_metadata if hasattr(row, 'feedback_metadata') else {},
            'created_at': row.created_at,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# 27. B2C product and customer analytics
# ---------------------------------------------------------------------------

@router.get('/api/v1/analytics/b2c/product-analytics')
def get_phase4_b2c_product_analytics(
    window_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> dict:
    """B2C product and customer analytics: orders, attribution, revenue by channel."""
    order_analytics = compute_marketing_order_analytics(db, window_days=window_days)
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    orders = (
        db.query(models.B2COrder)
        .filter(models.B2COrder.created_at >= cutoff)
        .all()
    )
    total_orders = len(orders)
    total_revenue = sum(float(o.total_amount or 0) for o in orders)
    by_channel: dict[str, int] = defaultdict(int)
    for o in orders:
        by_channel[str(o.source_channel or 'unknown')] += 1

    return {
        'generated_at': datetime.now(timezone.utc),
        'window_days': window_days,
        'total_orders': total_orders,
        'total_revenue': round(total_revenue, 2),
        'orders_by_source_channel': dict(by_channel),
        'attribution_summary': order_analytics,
    }


# ---------------------------------------------------------------------------
# 28. Customer lifecycle analytics (B2C)
# ---------------------------------------------------------------------------

@router.get('/api/v1/analytics/b2c/customer-lifecycle')
def get_phase4_b2c_customer_lifecycle(
    window_days: int = Query(default=90, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> dict:
    """B2C customer lifecycle analytics: order frequency, LTV, cohort retention."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    orders = (
        db.query(models.B2COrder)
        .filter(models.B2COrder.created_at >= cutoff, models.B2COrder.lead_id != None)
        .order_by(models.B2COrder.lead_id, models.B2COrder.created_at)
        .limit(max(1, min(limit * 10, 2000)))
        .all()
    )

    per_lead: dict[int, list[models.B2COrder]] = defaultdict(list)
    for o in orders:
        if o.lead_id:
            per_lead[int(o.lead_id)].append(o)

    cohort_stats: list[dict] = []
    for lead_id, lead_orders in list(per_lead.items())[:limit]:
        ltv = round(sum(float(o.total_amount or 0) for o in lead_orders), 2)
        avg_order = round(ltv / len(lead_orders), 2) if lead_orders else 0.0
        cohort_stats.append({
            'lead_id': lead_id,
            'order_count': len(lead_orders),
            'lifetime_value': ltv,
            'avg_order_value': avg_order,
            'first_order_at': lead_orders[0].created_at if lead_orders else None,
            'last_order_at': lead_orders[-1].created_at if lead_orders else None,
        })

    cohort_stats.sort(key=lambda x: -x['lifetime_value'])
    total_customers = len(per_lead)
    repeat_customers = sum(1 for v in per_lead.values() if len(v) > 1)

    return {
        'generated_at': datetime.now(timezone.utc),
        'window_days': window_days,
        'total_customers_with_orders': total_customers,
        'repeat_customers': repeat_customers,
        'retention_rate': round(repeat_customers / max(1, total_customers), 4),
        'top_customers': cohort_stats[:limit],
    }
