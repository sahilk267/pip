from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .. import models


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def compute_marketing_order_analytics(db: Session, window_days: int = 30) -> dict:
    now = datetime.now(timezone.utc)
    window_days = max(1, int(window_days))
    cutoff = now - timedelta(days=window_days)

    orders = (
        db.query(models.B2COrder)
        .filter(models.B2COrder.created_at >= cutoff)
        .order_by(models.B2COrder.created_at.asc(), models.B2COrder.id.asc())
        .all()
    )

    lead_ids = sorted({int(order.lead_id) for order in orders if order.lead_id is not None})
    dispatches_by_lead: dict[int, list[models.MarketingCampaignDispatch]] = defaultdict(list)
    if lead_ids:
        dispatches = (
            db.query(models.MarketingCampaignDispatch)
            .filter(models.MarketingCampaignDispatch.lead_id.in_(lead_ids))
            .order_by(models.MarketingCampaignDispatch.created_at.asc(), models.MarketingCampaignDispatch.id.asc())
            .all()
        )
        for row in dispatches:
            if row.lead_id is not None:
                dispatches_by_lead[int(row.lead_id)].append(row)

    attributed_orders = 0
    unattributed_orders = 0
    attributed_revenue = 0.0
    unattributed_revenue = 0.0

    by_provider: dict[str, dict[str, float]] = defaultdict(lambda: {'orders': 0, 'revenue': 0.0})
    by_channel: dict[str, dict[str, float]] = defaultdict(lambda: {'orders': 0, 'revenue': 0.0})
    by_campaign_type: dict[str, dict[str, float]] = defaultdict(lambda: {'orders': 0, 'revenue': 0.0})

    for order in orders:
        order_created = _as_utc(order.created_at) or now
        revenue = float(order.total_amount or 0.0)
        attributed_dispatch = None

        lead_dispatches = dispatches_by_lead.get(int(order.lead_id or 0), [])
        for row in lead_dispatches:
            row_created = _as_utc(row.created_at) or now
            if row_created <= order_created:
                attributed_dispatch = row
            else:
                break

        if attributed_dispatch is None:
            unattributed_orders += 1
            unattributed_revenue += revenue
            continue

        attributed_orders += 1
        attributed_revenue += revenue

        provider = str(attributed_dispatch.provider or 'unknown').strip().lower() or 'unknown'
        channel = str(attributed_dispatch.channel or 'unknown').strip().lower() or 'unknown'
        campaign_type = str(attributed_dispatch.campaign_type or 'unknown').strip().lower() or 'unknown'

        by_provider[provider]['orders'] += 1
        by_provider[provider]['revenue'] += revenue
        by_channel[channel]['orders'] += 1
        by_channel[channel]['revenue'] += revenue
        by_campaign_type[campaign_type]['orders'] += 1
        by_campaign_type[campaign_type]['revenue'] += revenue

    def _normalize(bucket: dict[str, dict[str, float]]) -> dict[str, dict[str, float | int]]:
        return {
            key: {
                'orders': int(values['orders']),
                'revenue': round(float(values['revenue']), 2),
            }
            for key, values in sorted(bucket.items())
        }

    return {
        'generated_at': now,
        'window_days': window_days,
        'orders_total': len(orders),
        'orders_attributed': attributed_orders,
        'orders_unattributed': unattributed_orders,
        'attributed_revenue': round(attributed_revenue, 2),
        'unattributed_revenue': round(unattributed_revenue, 2),
        'attribution_by_provider': _normalize(by_provider),
        'attribution_by_channel': _normalize(by_channel),
        'attribution_by_campaign_type': _normalize(by_campaign_type),
    }
