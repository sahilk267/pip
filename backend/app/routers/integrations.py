from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    ExternalIntegrationEvent,
    IntegrationAck,
    ExternalIntegrationCreate,
    ExternalIntegrationResponse,
    IntegrationSyncRecordResponse,
)
from ..crud import log_audit
from ..services.i18n_preview import strings_for_locale
from ..services.external_integrations import (
    register_integration,
    get_integration,
    list_integrations,
    update_integration,
    record_sync,
    list_sync_records,
)

router = APIRouter()


@router.post('/api/v1/integrations/external-crm/event', response_model=IntegrationAck)
def external_crm_event(
    event: ExternalIntegrationEvent,
    db: Session = Depends(get_db),
    locale: str = 'en',
) -> IntegrationAck:
    """Webhook-style stub: persists an audit entry for downstream CRM / MAP connectors."""
    detail = f"{event.provider}:{event.event_type} keys={list(event.payload.keys())[:8]}"
    log_audit(
        db,
        'integration',
        None,
        'external_crm_stub',
        detail,
        performed_by=event.performed_by,
    )
    return IntegrationAck(
        status='accepted',
        detail=strings_for_locale(locale).get(
            'integrations.external_crm.accepted_detail',
            'Logged to AuditLog; configure provider credentials in Phase 2.',
        ),
    )


# ---------- External Integration Management ----------

@router.post('/api/v1/integrations/external', response_model=ExternalIntegrationResponse)
def register_external_integration(
    payload: ExternalIntegrationCreate,
    db: Session = Depends(get_db),
) -> ExternalIntegrationResponse:
    try:
        row = register_integration(
            db,
            name=payload.name,
            provider=payload.provider,
            entity_sync_types=payload.entity_sync_types,
            api_endpoint=payload.api_endpoint,
            sync_direction=payload.sync_direction,
            field_mappings=payload.field_mappings,
            integration_metadata=payload.integration_metadata,
            configured_by='system',
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ExternalIntegrationResponse.model_validate(row)


@router.get('/api/v1/integrations/external/{integration_id}', response_model=ExternalIntegrationResponse)
def get_external_integration(
    integration_id: int,
    db: Session = Depends(get_db),
) -> ExternalIntegrationResponse:
    row = get_integration(db, integration_id=integration_id)
    if not row:
        raise HTTPException(status_code=404, detail='Integration not found')
    return ExternalIntegrationResponse.model_validate(row)


@router.get('/api/v1/security/secrets/integrations', response_model=list[ExternalIntegrationResponse])
@router.get('/api/v1/security/secrets/rotation', response_model=list[ExternalIntegrationResponse])
@router.get('/api/v1/integrations/external', response_model=list[ExternalIntegrationResponse])
def list_external_integrations(
    provider: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[ExternalIntegrationResponse]:
    rows = list_integrations(db, provider=provider, status=status, limit=limit)
    return [ExternalIntegrationResponse.model_validate(row) for row in rows]


@router.get('/api/v1/security/integrations/external', response_model=list[ExternalIntegrationResponse])
def list_security_external_integrations(
    provider: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[ExternalIntegrationResponse]:
    rows = list_integrations(db, provider=provider, status=status, limit=limit)
    return [ExternalIntegrationResponse.model_validate(row) for row in rows]


@router.patch('/api/v1/integrations/external/{integration_id}', response_model=ExternalIntegrationResponse)
def update_external_integration(
    integration_id: int,
    payload: dict,
    db: Session = Depends(get_db),
) -> ExternalIntegrationResponse:
    try:
        row = update_integration(
            db,
            integration_id=integration_id,
            status=payload.get('status'),
            api_endpoint=payload.get('api_endpoint'),
            field_mappings=payload.get('field_mappings'),
            sync_direction=payload.get('sync_direction'),
            performed_by='system',
        )
    except ValueError as exc:
        detail = str(exc)
        code = 404 if 'not found' in detail.lower() else 400
        raise HTTPException(status_code=code, detail=detail) from exc
    return ExternalIntegrationResponse.model_validate(row)


# ---------- Integration Sync Records ----------

@router.post('/api/v1/integrations/sync-records')
def record_integration_sync(
    integration_id: int = Query(...),
    entity_type: str = Query(...),
    entity_id: int = Query(...),
    sync_direction: str = Query(default='outbound'),
    external_id: str | None = Query(default=None),
    status: str = Query(default='pending'),
    error_message: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> IntegrationSyncRecordResponse:
    try:
        row = record_sync(
            db,
            integration_id=integration_id,
            entity_type=entity_type,
            entity_id=entity_id,
            sync_direction=sync_direction,
            external_id=external_id,
            status=status,
            error_message=error_message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return IntegrationSyncRecordResponse.model_validate(row)


@router.get('/api/v1/integrations/sync-records', response_model=list[IntegrationSyncRecordResponse])
def list_sync_history(
    integration_id: int | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[IntegrationSyncRecordResponse]:
    rows = list_sync_records(
        db,
        integration_id=integration_id,
        entity_type=entity_type,
        status=status,
        limit=limit,
    )
    return [IntegrationSyncRecordResponse.model_validate(row) for row in rows]
