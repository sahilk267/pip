"""Message template service - translatable templates for notifications and communications."""

from sqlalchemy.orm import Session
from .. import models
from ..crud import log_audit


def create_message_template(
    db: Session,
    *,
    template_code: str,
    template_type: str,
    translations: dict,
    default_locale: str = 'en',
    usage_metadata: dict | None = None,
    created_by: str = 'system',
) -> models.MessageTemplate:
    """Create or update a translatable message template."""
    template_code_norm = str(template_code or '').strip().lower()
    if not template_code_norm:
        raise ValueError('template_code is required')

    normalized_type = str(template_type or 'notification').strip()[:32] or 'notification'
    
    existing = db.query(models.MessageTemplate).filter(
        models.MessageTemplate.template_code == template_code_norm
    ).first()

    if existing:
        existing.template_type = normalized_type
        existing.default_locale = str(default_locale or 'en').lower()[:8] or 'en'
        existing.translations = translations or {}
        existing.usage_metadata = usage_metadata or {}
        db.add(existing)
        db.commit()
        db.refresh(existing)
        row = existing
    else:
        row = models.MessageTemplate(
            template_code=template_code_norm,
            template_type=normalized_type,
            default_locale=str(default_locale or 'en').lower()[:8] or 'en',
            translations=translations or {},
            usage_metadata=usage_metadata or {},
            created_by=str(created_by or 'system').strip()[:128] or 'system',
        )
        db.add(row)
        db.commit()
        db.refresh(row)

    log_audit(
        db,
        'template',
        row.id,
        'message_template_created_or_updated',
        f'code={row.template_code} type={row.template_type} locales={list(row.translations.keys())}',
        performed_by=created_by,
    )
    return row


def get_message_template(db: Session, *, template_code: str) -> models.MessageTemplate | None:
    """Fetch a template by code."""
    template_code_norm = str(template_code or '').strip().lower()
    return db.query(models.MessageTemplate).filter(
        models.MessageTemplate.template_code == template_code_norm
    ).first()


def get_localized_message(
    db: Session,
    *,
    template_code: str,
    locale: str = 'en',
    variables: dict | None = None,
) -> dict[str, str] | None:
    """Get template message in requested locale, with variable substitution."""
    template = get_message_template(db, template_code=template_code)
    if not template:
        return None

    locale_key = (locale or 'en').split('-')[0].lower()
    translations = template.translations or {}
    
    locale_data = translations.get(locale_key)
    if not locale_data:
        locale_data = translations.get('en')  # fallback to english
    
    if not locale_data:
        return None

    result = dict(locale_data)
    
    if variables:
        for key in ['subject', 'body']:
            if key in result:
                try:
                    result[key] = result[key].format(**variables)
                except Exception:
                    pass  # silently ignore formatting errors
    
    return result


def list_message_templates(
    db: Session,
    *,
    template_type: str | None = None,
    limit: int = 200,
) -> list[models.MessageTemplate]:
    """List all templates, optionally filtered by type."""
    query = db.query(models.MessageTemplate)
    
    if template_type:
        normalized_type = str(template_type or '').strip()[:32]
        query = query.filter(models.MessageTemplate.template_type == normalized_type)
    
    return query.order_by(models.MessageTemplate.template_code).limit(limit).all()


def delete_message_template(db: Session, *, template_code: str, performed_by: str = 'system') -> bool:
    """Delete a template."""
    template_code_norm = str(template_code or '').strip().lower()
    template = db.query(models.MessageTemplate).filter(
        models.MessageTemplate.template_code == template_code_norm
    ).first()
    
    if not template:
        return False
    
    log_audit(
        db,
        'template',
        template.id,
        'message_template_deleted',
        f'code={template.template_code}',
        performed_by=performed_by,
    )
    
    db.delete(template)
    db.commit()
    return True
