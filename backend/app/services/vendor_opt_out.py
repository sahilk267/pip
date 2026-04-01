from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit


_ALLOWED_RULE_TYPES = {'opt_out', 'blacklist'}


def _normalize_channel(channel: str | None) -> str:
    value = str(channel or 'all').strip().lower()
    return value[:32] or 'all'


def _normalize_rule_type(rule_type: str | None) -> str:
    value = str(rule_type or 'opt_out').strip().lower()
    return value if value in _ALLOWED_RULE_TYPES else 'opt_out'


def upsert_vendor_opt_out_rule(
    db: Session,
    *,
    vendor_id: int,
    channel: str,
    is_opted_out: bool,
    rule_type: str,
    reason: str | None,
    created_by: str,
) -> models.VendorOptOutRule:
    vendor = db.query(models.Vendor).filter(models.Vendor.id == int(vendor_id)).first()
    if vendor is None:
        raise ValueError('Vendor not found')

    normalized_channel = _normalize_channel(channel)
    normalized_type = _normalize_rule_type(rule_type)

    row = (
        db.query(models.VendorOptOutRule)
        .filter(
            models.VendorOptOutRule.vendor_id == vendor.id,
            models.VendorOptOutRule.channel == normalized_channel,
            models.VendorOptOutRule.rule_type == normalized_type,
        )
        .first()
    )

    if row is None:
        row = models.VendorOptOutRule(
            vendor_id=vendor.id,
            channel=normalized_channel,
            is_opted_out=bool(is_opted_out),
            rule_type=normalized_type,
            reason=(str(reason or '').strip()[:512] or None),
            created_by=str(created_by or 'compliance').strip()[:128] or 'compliance',
        )
    else:
        row.is_opted_out = bool(is_opted_out)
        row.reason = (str(reason or '').strip()[:512] or None)
        row.created_by = str(created_by or 'compliance').strip()[:128] or 'compliance'

    db.add(row)
    db.commit()
    db.refresh(row)

    action = 'vendor_blacklist_rule_upserted' if normalized_type == 'blacklist' else 'vendor_opt_out_rule_upserted'
    log_audit(
        db,
        'vendor',
        vendor.id,
        action,
        f'channel={normalized_channel} is_opted_out={row.is_opted_out}',
        performed_by=row.created_by,
    )
    return row


def list_vendor_opt_out_rules(
    db: Session,
    *,
    vendor_id: int | None = None,
    only_active: bool = True,
    limit: int = 200,
) -> list[models.VendorOptOutRule]:
    query = db.query(models.VendorOptOutRule)
    if vendor_id is not None:
        query = query.filter(models.VendorOptOutRule.vendor_id == int(vendor_id))
    if only_active:
        query = query.filter(models.VendorOptOutRule.is_opted_out.is_(True))

    limit = max(1, min(int(limit), 1000))
    return (
        query.order_by(models.VendorOptOutRule.updated_at.desc(), models.VendorOptOutRule.id.desc())
        .limit(limit)
        .all()
    )


def get_blocked_vendor_ids_for_channel(db: Session, *, vendor_ids: list[int], channel: str) -> set[int]:
    normalized_channel = _normalize_channel(channel)
    candidate_vendor_ids = sorted({int(vendor_id) for vendor_id in vendor_ids if int(vendor_id) > 0})
    if not candidate_vendor_ids:
        return set()

    rows = (
        db.query(models.VendorOptOutRule.vendor_id)
        .filter(
            models.VendorOptOutRule.vendor_id.in_(candidate_vendor_ids),
            models.VendorOptOutRule.is_opted_out.is_(True),
            or_(
                models.VendorOptOutRule.channel == 'all',
                models.VendorOptOutRule.channel == normalized_channel,
            ),
        )
        .all()
    )
    return {int(row.vendor_id) for row in rows}
