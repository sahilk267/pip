from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit


_ALLOWED_ACTOR_TYPES = {'vendor', 'client', 'customer'}
_ALLOWED_SENTIMENT = {'positive', 'neutral', 'negative'}


def record_order_deal_feedback(
    db: Session,
    *,
    order_id: int,
    actor_type: str,
    actor_id: int | None,
    sentiment: str,
    rating: int | None,
    feedback_text: str | None,
    feedback_metadata: dict,
    created_by: str,
) -> models.OrderDealFeedback:
    order = db.query(models.B2COrder).filter(models.B2COrder.id == int(order_id)).first()
    if order is None:
        raise ValueError('Order not found')

    normalized_actor_type = str(actor_type or '').strip().lower()
    if normalized_actor_type not in _ALLOWED_ACTOR_TYPES:
        raise ValueError('Unsupported actor type')

    normalized_sentiment = str(sentiment or '').strip().lower()
    if normalized_sentiment not in _ALLOWED_SENTIMENT:
        raise ValueError('Unsupported sentiment')

    if rating is not None and (int(rating) < 1 or int(rating) > 5):
        raise ValueError('Rating must be between 1 and 5')

    row = models.OrderDealFeedback(
        order_id=int(order.id),
        actor_type=normalized_actor_type,
        actor_id=int(actor_id) if actor_id is not None else None,
        sentiment=normalized_sentiment,
        rating=int(rating) if rating is not None else None,
        feedback_text=str(feedback_text or '').strip()[:3000] or None,
        feedback_metadata=feedback_metadata or {},
        created_by=str(created_by or 'support').strip()[:128] or 'support',
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(
        db,
        'order',
        order.id,
        'post_deal_feedback_recorded',
        f'feedback_id={row.id} actor_type={row.actor_type} sentiment={row.sentiment} rating={row.rating or "n/a"}',
        performed_by=row.created_by,
    )
    return row


def list_order_deal_feedback(db: Session, *, order_id: int) -> list[models.OrderDealFeedback]:
    order = db.query(models.B2COrder).filter(models.B2COrder.id == int(order_id)).first()
    if order is None:
        raise ValueError('Order not found')

    return (
        db.query(models.OrderDealFeedback)
        .filter(models.OrderDealFeedback.order_id == int(order_id))
        .order_by(models.OrderDealFeedback.created_at.desc(), models.OrderDealFeedback.id.desc())
        .all()
    )


def order_deal_feedback_summary(db: Session, *, window_days: int = 30) -> dict:
    window_days = max(1, int(window_days))
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    rows = (
        db.query(models.OrderDealFeedback)
        .filter(models.OrderDealFeedback.created_at >= cutoff)
        .all()
    )

    total = len(rows)
    ratings = [int(row.rating) for row in rows if row.rating is not None]
    average_rating = round(sum(ratings) / len(ratings), 4) if ratings else 0.0

    sentiment_counts = {
        'positive': sum(1 for row in rows if row.sentiment == 'positive'),
        'neutral': sum(1 for row in rows if row.sentiment == 'neutral'),
        'negative': sum(1 for row in rows if row.sentiment == 'negative'),
    }

    by_actor_type = {
        'vendor': sum(1 for row in rows if row.actor_type == 'vendor'),
        'client': sum(1 for row in rows if row.actor_type == 'client'),
        'customer': sum(1 for row in rows if row.actor_type == 'customer'),
    }

    return {
        'generated_at': datetime.now(timezone.utc),
        'window_days': window_days,
        'total_feedback': total,
        'average_rating': average_rating,
        'sentiment_counts': sentiment_counts,
        'by_actor_type': by_actor_type,
    }
