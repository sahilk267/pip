"""Message templates router - translatable messages for communications."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    MessageTemplateCreate,
    MessageTemplateResponse,
)
from ..services.message_templates import (
    create_message_template,
    get_message_template,
    get_localized_message,
    list_message_templates,
    delete_message_template,
)

router = APIRouter()


@router.post('/api/v1/messages/templates', response_model=MessageTemplateResponse)
def create_template(
    payload: MessageTemplateCreate,
    db: Session = Depends(get_db),
) -> MessageTemplateResponse:
    try:
        row = create_message_template(
            db,
            template_code=payload.template_code,
            template_type=payload.template_type,
            translations=payload.translations,
            default_locale=payload.default_locale,
            usage_metadata=payload.usage_metadata,
            created_by='system',
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MessageTemplateResponse.model_validate(row)


@router.get('/api/v1/messages/templates/{template_code}')
def get_template(
    template_code: str,
    db: Session = Depends(get_db),
) -> dict:
    row = get_message_template(db, template_code=template_code)
    if not row:
        raise HTTPException(status_code=404, detail='Template not found')
    return MessageTemplateResponse.model_validate(row).model_dump()


@router.get('/api/v1/messages/templates/{template_code}/localized')
def get_localized(
    template_code: str,
    request: Request,
    locale: str = Query(default='en'),
    variables_json: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """Get localized message with variable substitution."""
    variables: dict = {}
    if variables_json:
        try:
            parsed = json.loads(variables_json)
            if isinstance(parsed, dict):
                variables = parsed
        except Exception:
            raise HTTPException(status_code=400, detail='variables_json must be a valid JSON object')

    for key, value in request.query_params.items():
        if key not in {'locale', 'variables_json'}:
            variables[key] = value

    message = get_localized_message(
        db,
        template_code=template_code,
        locale=locale,
        variables=variables,
    )
    if not message:
        raise HTTPException(status_code=404, detail='Template or locale not found')
    return {'locale': locale, 'message': message}


@router.get('/api/v1/messages/templates', response_model=list[MessageTemplateResponse])
def list_templates(
    template_type: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[MessageTemplateResponse]:
    rows = list_message_templates(db, template_type=template_type, limit=limit)
    return [MessageTemplateResponse.model_validate(row) for row in rows]


@router.delete('/api/v1/messages/templates/{template_code}')
def delete_template(
    template_code: str,
    db: Session = Depends(get_db),
) -> dict:
    success = delete_message_template(db, template_code=template_code, performed_by='system')
    if not success:
        raise HTTPException(status_code=404, detail='Template not found')
    return {'status': 'deleted', 'template_code': template_code}
