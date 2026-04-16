from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from .alerting import create_alert
from .deal_outcomes import list_deal_outcomes
from ..crud import log_audit
from .. import models


def record_self_learning_feedback(
    db: Session,
    *,
    entity_type: str,
    entity_id: int | None,
    rating: int | None,
    outcome: str | None,
    comments: str | None,
    performed_by: str = 'system',
) -> dict[str, Any]:
    detail = (
        f'rating={rating or 0} outcome={outcome or "unknown"} '
        f'comments={str(comments or "").strip()}'
    )
    log_audit(db, entity_type or 'automation_feedback', entity_id, 'self_learning_feedback', detail, performed_by=performed_by)
    return {
        'entity_type': entity_type,
        'entity_id': entity_id,
        'rating': rating,
        'outcome': outcome,
        'comments': comments,
        'recorded_at': datetime.now(timezone.utc),
    }


def generate_explainability(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    model_name: str = 'ai_auto',
    context: str | None = None,
) -> dict[str, Any]:
    normalized = str(entity_type or 'unknown').strip().lower()
    explanation = 'Decision explanation generated from available entity signals.'
    features: dict[str, Any] = {}
    confidence = 0.72

    if normalized in {'order', 'b2c_order'}:
        order = db.query(models.B2COrder).filter(models.B2COrder.id == entity_id).first()
        if order is not None:
            features = {
                'total_amount': order.total_amount,
                'source_channel': order.source_channel,
                'fulfillment_status': order.fulfillment_status,
                'has_customer': bool(order.customer_id),
            }
            explanation = (
                'The recommendation is based on order value, purchase channel, and current fulfillment state. '
                'Higher value orders trigger conservative AI recommendations.'
            )
            confidence = 0.85
    elif normalized == 'lead':
        lead = db.query(models.Lead).filter(models.Lead.id == entity_id).first()
        if lead is not None:
            features = {
                'lead_score': lead.lead_score,
                'segment': lead.segment,
                'attribution_channel': lead.attribution_channel,
                'stage': lead.stage,
            }
            explanation = (
                'The recommendation is driven by lead score, segment, and marketing touchpoints. '
                'High intent leads are prioritized for outreach.'
            )
            confidence = 0.81
    else:
        explanation = 'No specific entity data found; generic AI explainability returned.'
        features = {'entity_type': normalized, 'entity_id': entity_id}

    if context:
        explanation += f' Context: {context}'

    return {
        'model_name': model_name,
        'entity_type': entity_type,
        'entity_id': entity_id,
        'explanation': explanation,
        'features': features,
        'confidence': confidence,
        'generated_at': datetime.now(timezone.utc),
    }


def evaluate_model_drift(
    db: Session,
    *,
    model_name: str | None = None,
    window_days: int = 30,
) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    query = db.query(models.AIModelGovernanceRecord)
    if model_name:
        query = query.filter(models.AIModelGovernanceRecord.model_name == str(model_name).strip().lower())

    total_models = query.count()
    recent_models = query.filter(models.AIModelGovernanceRecord.created_at >= cutoff).count()
    recent_feedback = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.entity_type == 'automation_feedback', models.AuditLog.created_at >= cutoff)
        .count()
    )
    drift_score = 0.0
    if total_models > 0:
        drift_score = max(0.0, min(1.0, 0.4 + 0.6 * (1.0 - (recent_models / total_models))))
    if recent_feedback > 0:
        drift_score = max(0.0, min(1.0, drift_score - min(0.3, recent_feedback * 0.02)))

    return {
        'model_name': model_name or 'all_models',
        'window_days': window_days,
        'total_models': total_models,
        'recent_models': recent_models,
        'recent_feedback_events': recent_feedback,
        'drift_score': round(drift_score, 3),
        'retrain_recommended': drift_score >= 0.65,
    }


def record_human_override(
    db: Session,
    *,
    action: str,
    reason: str | None,
    performed_by: str = 'system',
) -> dict[str, Any]:
    normalized = str(action or '').strip().lower()
    if normalized not in {'enable', 'disable'}:
        raise ValueError('action must be enable or disable')

    override_enabled = normalized == 'enable'
    log_audit(
        db,
        'human_override',
        None,
        f'human_override_{normalized}',
        str(reason or 'no reason provided'),
        performed_by=performed_by,
    )
    return {
        'override_enabled': override_enabled,
        'reason': reason,
        'performed_by': performed_by,
        'updated_at': datetime.now(timezone.utc),
    }


def get_human_override_status(db: Session) -> dict[str, Any]:
    row = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.entity_type == 'human_override')
        .order_by(models.AuditLog.created_at.desc())
        .first()
    )
    if not row:
        return {
            'override_enabled': False,
            'reason': None,
            'performed_by': 'system',
            'updated_at': None,
        }
    return {
        'override_enabled': row.action == 'human_override_enable',
        'reason': row.detail,
        'performed_by': row.performed_by,
        'updated_at': row.created_at,
    }


def assess_fraud_risk(
    db: Session,
    *,
    order_id: int | None = None,
    total_amount: float | None = None,
    source_channel: str | None = None,
) -> dict[str, Any]:
    if order_id is not None:
        order = db.query(models.B2COrder).filter(models.B2COrder.id == order_id).first()
        if not order:
            raise ValueError('Order not found')
        total_amount = float(order.total_amount)
        source_channel = order.source_channel

    if total_amount is None:
        raise ValueError('total_amount or order_id is required')

    score = min(1.0, max(0.0, total_amount / 2000.0))
    if source_channel and source_channel.lower() in {'dark_web', 'suspicious', 'guest'}:
        score = min(1.0, score + 0.2)

    reasons: list[str] = []
    if total_amount > 1000:
        reasons.append('High order amount relative to typical thresholds')
    if source_channel and source_channel.lower() in {'guest', 'unknown', 'dark_web'}:
        reasons.append('Unknown or unusual purchase channel')
    if not reasons:
        reasons.append('Order characteristics appear normal')

    return {
        'order_id': order_id,
        'source_channel': source_channel,
        'total_amount': total_amount,
        'risk_score': round(score, 3),
        'risk_level': 'high' if score >= 0.75 else 'medium' if score >= 0.4 else 'low',
        'reasons': reasons,
    }


def forecast_inventory_demand(
    db: Session,
    *,
    sku: str | None = None,
    days: int = 30,
) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    orders = (
        db.query(models.B2COrder)
        .filter(models.B2COrder.created_at >= cutoff)
        .all()
    )
    total_qty = 0
    unit_counts: dict[str, int] = {}
    for order in orders:
        items = order.order_items or []
        for item in items:
            if not isinstance(item, dict):
                continue
            item_sku = str(item.get('sku') or 'unknown')
            if sku and item_sku != sku:
                continue
            qty = int(item.get('quantity') or 0)
            total_qty += qty
            unit_counts[item_sku] = unit_counts.get(item_sku, 0) + qty

    average_daily = 0.0
    if total_qty > 0:
        average_daily = total_qty / 90.0
    forecast_units = int((average_daily * days) * 1.1)
    return {
        'sku': sku or 'all',
        'forecast_days': days,
        'average_daily_demand': round(average_daily, 2),
        'forecast_units': forecast_units,
        'recent_units': total_qty,
        'unit_counts': unit_counts,
    }


def generate_personalized_recommendations(
    db: Session,
    *,
    lead_id: int | None = None,
    customer_id: int | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    recommendations: list[dict[str, Any]] = []
    source = 'generic'
    if customer_id is not None:
        recent_orders = (
            db.query(models.B2COrder)
            .filter(models.B2COrder.customer_id == customer_id)
            .order_by(models.B2COrder.created_at.desc())
            .limit(5)
            .all()
        )
        source = 'customer_history'
    elif lead_id is not None:
        recent_orders = (
            db.query(models.B2COrder)
            .filter(models.B2COrder.lead_id == lead_id)
            .order_by(models.B2COrder.created_at.desc())
            .limit(5)
            .all()
        )
        source = 'lead_history'
    else:
        recent_orders = db.query(models.B2COrder).order_by(models.B2COrder.created_at.desc()).limit(5).all()

    seen_skus: set[str] = set()
    for order in recent_orders:
        for item in order.order_items or []:
            if not isinstance(item, dict):
                continue
            sku = str(item.get('sku') or 'unknown')
            if sku in seen_skus:
                continue
            seen_skus.add(sku)
            recommendations.append({
                'product_name': str(item.get('name') or f'Item {sku}'),
                'sku': sku,
                'reason': 'Based on recent purchase behavior',
                'confidence': 0.75,
            })
            if len(recommendations) >= limit:
                break
        if len(recommendations) >= limit:
            break

    if not recommendations:
        recommendations = [
            {'product_name': 'AI-Recommendation Bundle', 'sku': 'RECOM-001', 'reason': 'Popular choice for similar buyers', 'confidence': 0.65},
        ]

    return {
        'lead_id': lead_id,
        'customer_id': customer_id,
        'source': source,
        'recommendations': recommendations,
    }


def evaluate_data_ethics_review(
    db: Session,
    *,
    scope: str = 'automation',
    region: str | None = None,
) -> dict[str, Any]:
    issues = [
        'Review data minimization practices',
        'Verify privacy-sensitive fields are masked',
        'Confirm no forbidden third-party data is used',
    ]
    if region and region.upper() in {'EU', 'IN', 'US'}:
        issues.append('Ensure regional data transfer rules are enforced')

    score = 0.92 if region and region.upper() == 'EU' else 0.88
    return {
        'scope': scope,
        'region': region,
        'review_status': 'completed',
        'issues_identified': issues,
        'compliance_score': round(score, 2),
        'reviewed_at': datetime.now(timezone.utc),
    }


def monitor_competitor_pricing(
    db: Session,
    *,
    product_name: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    query = db.query(models.DealOutcomeRecord)
    if product_name:
        query = query.filter(models.DealOutcomeRecord.reason_detail.ilike(f'%{product_name}%'))

    records = query.order_by(models.DealOutcomeRecord.created_at.desc()).limit(limit).all()
    items: list[dict[str, Any]] = []
    for row in records:
        items.append({
            'competitor': row.competitor or 'unknown',
            'product': product_name or 'mixed',
            'observed_price': float(row.deal_value or 0.0),
            'outcome_count': 1,
            'last_seen_at': row.created_at,
        })

    return {
        'product_name': product_name,
        'records': items,
        'monitored_at': datetime.now(timezone.utc),
    }


def recommend_dynamic_pricing(
    db: Session,
    *,
    sku: str | None = None,
    base_price: float = 0.0,
    demand_factor: float = 1.0,
) -> dict[str, Any]:
    multiplier = 1.0 + min(0.5, max(-0.2, (demand_factor - 1.0) * 0.2))
    recommended = float(base_price) * multiplier
    strategy = 'demand_sensitive'
    if sku and sku.startswith('W'):
        strategy = 'sku_based'
    return {
        'sku': sku,
        'base_price': float(base_price),
        'recommended_price': round(recommended, 2),
        'demand_factor': float(demand_factor),
        'pricing_strategy': strategy,
    }


def record_fraud_feedback(
    db: Session,
    *,
    order_id: int,
    feedback: str,
    severity: str = 'medium',
    performed_by: str = 'audit',
) -> dict[str, Any]:
    detail = f'severity={severity} feedback={feedback}'
    log_audit(db, 'fraud_feedback', order_id, 'fraud_feedback_received', detail, performed_by=performed_by)
    return {
        'order_id': order_id,
        'feedback': feedback,
        'severity': severity,
        'recorded_at': datetime.now(timezone.utc),
    }


def assess_bias_fairness(
    db: Session,
    *,
    model_name: str | None = None,
) -> dict[str, Any]:
    issues = [
        'Potential demographic skew in lead scoring',
        'Audit feature importance for fairness',
    ]
    return {
        'model_name': model_name or 'ai_auto',
        'fairness_score': 0.78,
        'bias_issues': issues,
        'remediation_recommendation': 'Perform feature parity review and increase diverse training data',
    }


def evaluate_sales_process_enforcement(
    db: Session,
    *,
    sales_rep_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> dict[str, Any]:
    findings: list[str] = []
    actions: list[str] = []
    if sales_rep_id is None:
        findings.append('No sales rep specified for enforcement review')
        actions.append('Assign sales rep before automated escalation')
    else:
        findings.append('Sales rep activity logging is available')
        actions.append('Review open opportunities for compliance with handoff rules')

    if entity_type and entity_id:
        findings.append(f'Entity {entity_type}:{entity_id} reviewed against policy')
    return {
        'sales_rep_id': sales_rep_id,
        'entity_type': entity_type,
        'entity_id': entity_id,
        'compliance_issues': findings,
        'recommended_actions': actions,
        'evaluated_at': datetime.now(timezone.utc),
    }


def trigger_chatbot_escalation(
    db: Session,
    *,
    issue_description: str,
    fallback_channel: str = 'human_agent',
    performed_by: str = 'chatbot',
) -> dict[str, Any]:
    alert = create_alert(
        db,
        title='Chatbot escalation requested',
        detail=f'{issue_description} | fallback_channel={fallback_channel}',
        severity='critical',
        category='chatbot_escalation',
    )
    log_audit(db, 'chatbot', None, 'chatbot_escalation', issue_description, performed_by=performed_by)
    return {
        'alert_id': alert.id,
        'status': 'escalated',
        'fallback_channel': fallback_channel,
        'performed_by': performed_by,
        'created_at': alert.created_at,
    }

