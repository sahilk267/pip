"""External integration service - manage ERP, CRM, and tool integrations."""

from sqlalchemy.orm import Session
from datetime import datetime, timezone
from .. import models
from ..crud import log_audit


def register_integration(
    db: Session,
    *,
    name: str,
    provider: str,
    entity_sync_types: list[str],
    api_endpoint: str | None = None,
    sync_direction: str = 'bidirectional',
    field_mappings: dict | None = None,
    integration_metadata: dict | None = None,
    configured_by: str = 'system',
) -> models.ExternalIntegration:
    """Register a new external system integration."""
    name_norm = str(name or '').strip()
    if not name_norm:
        raise ValueError('Integration name is required')
    
    provider_norm = str(provider or 'custom').strip()[:64] or 'custom'
    sync_dir = str(sync_direction or 'bidirectional').strip()
    if sync_dir not in ['outbound', 'inbound', 'bidirectional']:
        raise ValueError('sync_direction must be outbound, inbound, or bidirectional')

    row = models.ExternalIntegration(
        name=name_norm[:128],
        provider=provider_norm,
        status='active',
        entity_sync_types=entity_sync_types or [],
        api_endpoint=str(api_endpoint or '').strip()[:512] or None,
        credentials_encrypted=None,  # Would be encrypted with fernet in production
        sync_direction=sync_dir,
        field_mappings=field_mappings or {},
        integration_metadata=integration_metadata or {},
        configured_by=str(configured_by or 'system').strip()[:128] or 'system',
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(
        db,
        'integration',
        row.id,
        'external_integration_registered',
        f'name={row.name} provider={row.provider} sync_types={row.entity_sync_types}',
        performed_by=configured_by,
    )
    return row


def get_integration(db: Session, *, integration_id: int) -> models.ExternalIntegration | None:
    """Fetch an integration by ID."""
    return db.query(models.ExternalIntegration).filter(
        models.ExternalIntegration.id == integration_id
    ).first()


def list_integrations(
    db: Session,
    *,
    provider: str | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[models.ExternalIntegration]:
    """List all integrations, optionally filtered."""
    query = db.query(models.ExternalIntegration)
    
    if provider:
        provider_norm = str(provider or '').strip()
        query = query.filter(models.ExternalIntegration.provider == provider_norm)
    
    if status:
        status_norm = str(status or '').strip()
        query = query.filter(models.ExternalIntegration.status == status_norm)
    
    return query.order_by(models.ExternalIntegration.name).limit(limit).all()


def update_integration(
    db: Session,
    *,
    integration_id: int,
    status: str | None = None,
    api_endpoint: str | None = None,
    field_mappings: dict | None = None,
    sync_direction: str | None = None,
    performed_by: str = 'system',
) -> models.ExternalIntegration:
    """Update an integration configuration."""
    integration = get_integration(db, integration_id=integration_id)
    if not integration:
        raise ValueError(f'Integration {integration_id} not found')
    
    if status:
        status_norm = str(status or '').strip()
        if status_norm not in ['active', 'paused', 'archived']:
            raise ValueError('Status must be active, paused, or archived')
        integration.status = status_norm
    
    if api_endpoint is not None:
        integration.api_endpoint = str(api_endpoint).strip()[:512] or None
    
    if field_mappings is not None:
        integration.field_mappings = field_mappings
    
    if sync_direction:
        sync_dir = str(sync_direction).strip()
        if sync_dir not in ['outbound', 'inbound', 'bidirectional']:
            raise ValueError('sync_direction must be outbound, inbound, or bidirectional')
        integration.sync_direction = sync_dir
    
    db.add(integration)
    db.commit()
    db.refresh(integration)
    
    log_audit(
        db,
        'integration',
        integration.id,
        'external_integration_updated',
        f'name={integration.name} status={integration.status}',
        performed_by=performed_by,
    )
    return integration


def record_sync(
    db: Session,
    *,
    integration_id: int,
    entity_type: str,
    entity_id: int,
    sync_direction: str,
    external_id: str | None = None,
    status: str = 'pending',
    sync_payload: dict | None = None,
    error_message: str | None = None,
) -> models.IntegrationSyncRecord:
    """Record a sync attempt to external system."""
    integration = get_integration(db, integration_id=integration_id)
    if not integration:
        raise ValueError(f'Integration {integration_id} not found')
    
    entity_type_norm = str(entity_type or '').strip().lower()[:32] or 'unknown'
    sync_dir_norm = str(sync_direction or 'outbound').strip()
    
    row = models.IntegrationSyncRecord(
        integration_id=integration.id,
        entity_type=entity_type_norm,
        entity_id=int(entity_id),
        sync_direction=sync_dir_norm,
        external_id=str(external_id or '').strip()[:256] or None,
        status=str(status or 'pending').strip()[:32],
        sync_payload=sync_payload or {},
        error_message=str(error_message or '').strip() or None,
        synced_at=datetime.now(timezone.utc) if status == 'synced' else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    if status == 'synced':
        integration.last_sync_at = datetime.now(timezone.utc)
        db.add(integration)
        db.commit()

    log_audit(
        db,
        'sync',
        row.id,
        'integration_sync_recorded',
        f'integration={integration.name} entity={entity_type_norm}/{entity_id} status={status}',
        performed_by='system',
    )
    return row


def list_sync_records(
    db: Session,
    *,
    integration_id: int | None = None,
    entity_type: str | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[models.IntegrationSyncRecord]:
    """List sync records, optionally filtered."""
    query = db.query(models.IntegrationSyncRecord)
    
    if integration_id:
        query = query.filter(models.IntegrationSyncRecord.integration_id == integration_id)
    
    if entity_type:
        entity_type_norm = str(entity_type or '').strip().lower()
        query = query.filter(models.IntegrationSyncRecord.entity_type == entity_type_norm)
    
    if status:
        status_norm = str(status or '').strip()
        query = query.filter(models.IntegrationSyncRecord.status == status_norm)
    
    return query.order_by(models.IntegrationSyncRecord.created_at.desc()).limit(limit).all()
