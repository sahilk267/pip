from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit


def stable_hash(value: str) -> str:
    return hashlib.sha256(str(value).encode('utf-8')).hexdigest()[:64]


def check_and_register_multi_channel_dedup(
    db: Session,
    *,
    entity_type: str,
    dedup_key_raw: str,
    channel: str,
    window_hours: int = 24,
    performed_by: str = 'system',
) -> bool:
    normalized_entity = str(entity_type or '').strip().lower()[:64] or 'unknown'
    normalized_channel = str(channel or '').strip().lower()[:64] or 'unknown'
    dedup_key = stable_hash(dedup_key_raw)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, int(window_hours)))

    existing = (
        db.query(models.MultiChannelDedupRecord)
        .filter(
            models.MultiChannelDedupRecord.entity_type == normalized_entity,
            models.MultiChannelDedupRecord.dedup_key == dedup_key,
            models.MultiChannelDedupRecord.status == 'active',
            models.MultiChannelDedupRecord.last_seen_at >= cutoff,
        )
        .first()
    )

    if existing is None:
        row = models.MultiChannelDedupRecord(
            entity_type=normalized_entity,
            dedup_key=dedup_key,
            primary_channel=normalized_channel,
            channels_seen=[normalized_channel],
            duplicate_count=1,
            status='active',
        )
        db.add(row)
        db.commit()
        return False

    channels = existing.channels_seen or []
    is_cross_channel_duplicate = normalized_channel not in channels
    if normalized_channel not in channels:
        channels = list(channels) + [normalized_channel]
    existing.channels_seen = channels
    existing.last_seen_at = datetime.now(timezone.utc)
    existing.duplicate_count = int(existing.duplicate_count or 1) + 1
    db.add(existing)
    db.commit()

    if not is_cross_channel_duplicate:
        return False

    log_audit(
        db,
        'dedup',
        existing.id,
        'multi_channel_duplicate_detected',
        f'entity_type={normalized_entity} channels={"|".join(channels)} count={existing.duplicate_count}',
        performed_by=performed_by,
    )
    return True
