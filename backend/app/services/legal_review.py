"""Regional legal review checklist service.

Provides static checklist templates per regulation and persistence for
completed/in-progress reviews, covering GDPR, DPDP, CCPA, and PCI DSS.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit

_ALLOWED_STATUSES = {'pending', 'approved', 'flagged', 'waived'}
_ALLOWED_REGULATIONS = {'GDPR', 'DPDP', 'CCPA', 'PCI_DSS'}

_REGION_REGULATION_MAP: dict[str, list[str]] = {
    'EU': ['GDPR', 'PCI_DSS'],
    'IN': ['DPDP', 'PCI_DSS'],
    'US': ['CCPA', 'PCI_DSS'],
    'GLOBAL': ['GDPR', 'DPDP', 'CCPA', 'PCI_DSS'],
}

_CHECKLISTS: dict[str, list[dict]] = {
    'GDPR': [
        {'id': 'gdpr-1',   'label': 'Lawful basis for processing identified and documented',              'category': 'lawful_basis'},
        {'id': 'gdpr-2',   'label': 'Data subject consent obtained or legitimate interest established',   'category': 'consent'},
        {'id': 'gdpr-3',   'label': 'Privacy notice provided to data subjects at collection point',       'category': 'transparency'},
        {'id': 'gdpr-4',   'label': 'Data minimisation principle applied (only necessary data collected)', 'category': 'minimisation'},
        {'id': 'gdpr-5',   'label': 'Data retention policy defined and enforced',                         'category': 'retention'},
        {'id': 'gdpr-6',   'label': 'Right-to-erasure and data portability flows implemented',            'category': 'data_rights'},
        {'id': 'gdpr-7',   'label': 'Third-party data processors under DPA (Data Processing Agreement)',  'category': 'processors'},
        {'id': 'gdpr-8',   'label': 'Cross-border transfer safeguards in place (SCCs / adequacy decision)', 'category': 'transfers'},
        {'id': 'gdpr-9',   'label': 'Breach detection, notification, and 72-hour reporting process ready', 'category': 'breach'},
        {'id': 'gdpr-10',  'label': 'DPO appointed or appointing rationale documented',                   'category': 'governance'},
    ],
    'DPDP': [
        {'id': 'dpdp-1',  'label': 'Consent notice in English or regional language obtained',            'category': 'consent'},
        {'id': 'dpdp-2',  'label': 'Purpose limitation documented for each data category',               'category': 'purpose'},
        {'id': 'dpdp-3',  'label': 'Data principal rights (access, correction, erasure) flows in place', 'category': 'data_rights'},
        {'id': 'dpdp-4',  'label': 'Significant Data Fiduciary (SDF) checks completed if applicable',   'category': 'classification'},
        {'id': 'dpdp-5',  'label': 'Cross-border data transfer approval / standard clause compliance',   'category': 'transfers'},
        {'id': 'dpdp-6',  'label': 'Data Protection Officer appointed or justification recorded',        'category': 'governance'},
        {'id': 'dpdp-7',  'label': 'Breach notification to DPBI within 72 hours procedure established',  'category': 'breach'},
        {'id': 'dpdp-8',  'label': 'Child data safeguards: verifiable parental consent mechanism',       'category': 'child_data'},
    ],
    'CCPA': [
        {'id': 'ccpa-1',  'label': '"Do Not Sell My Personal Information" link/notice present',          'category': 'opt_out'},
        {'id': 'ccpa-2',  'label': 'Consumer rights: know, delete, correct, and non-discrimination',     'category': 'data_rights'},
        {'id': 'ccpa-3',  'label': 'Privacy policy updated with CCPA disclosures',                       'category': 'transparency'},
        {'id': 'ccpa-4',  'label': 'Categories of personal information collected disclosed',             'category': 'disclosure'},
        {'id': 'ccpa-5',  'label': 'Third-party data sharing and selling disclosed',                     'category': 'third_party'},
        {'id': 'ccpa-6',  'label': 'Consumer request response process within 45-day window',             'category': 'response_time'},
        {'id': 'ccpa-7',  'label': 'Service provider contracts include CCPA data use restrictions',      'category': 'processors'},
    ],
    'PCI_DSS': [
        {'id': 'pci-1',   'label': 'Cardholder data environment (CDE) scoped and documented',            'category': 'scope'},
        {'id': 'pci-2',   'label': 'No sensitive authentication data stored post-authorisation',          'category': 'data_storage'},
        {'id': 'pci-3',   'label': 'Encryption in transit (TLS 1.2+) for all card data flows',           'category': 'encryption'},
        {'id': 'pci-4',   'label': 'Vulnerability scanning and penetration testing scheduled',            'category': 'testing'},
        {'id': 'pci-5',   'label': 'Access control: least-privilege roles for CDE systems',              'category': 'access_control'},
        {'id': 'pci-6',   'label': 'Audit log retention for 12 months with 3-month online access',       'category': 'logging'},
        {'id': 'pci-7',   'label': 'Incident response plan covering card-data breach',                   'category': 'incident_response'},
        {'id': 'pci-8',   'label': 'SAQ or external QSA assessment completed',                           'category': 'assessment'},
    ],
}


def get_checklist_template(regulation: str, entity_type: str | None = None) -> list[dict]:
    """Return the static checklist template for a regulation (items without status/notes)."""
    normalized = str(regulation or '').strip().upper()
    if normalized not in _ALLOWED_REGULATIONS:
        raise ValueError(f'regulation must be one of: {", ".join(sorted(_ALLOWED_REGULATIONS))}')
    template = []
    for item in _CHECKLISTS[normalized]:
        template.append({
            'id': item['id'],
            'label': item['label'],
            'category': item['category'],
            'status': 'pending',
            'notes': '',
        })
    return template


def get_region_regulations(region: str) -> list[str]:
    normalized = str(region or 'GLOBAL').strip().upper()
    return list(_REGION_REGULATION_MAP.get(normalized, _REGION_REGULATION_MAP['GLOBAL']))


def record_legal_review(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    region: str,
    regulation: str,
    checklist_items: list[dict],
    reviewer: str,
    notes: str | None = None,
    status: str = 'pending',
    performed_by: str = 'legal',
) -> models.RegionalLegalReview:
    normalized_status = str(status or 'pending').strip().lower()
    if normalized_status not in _ALLOWED_STATUSES:
        raise ValueError('status must be one of: pending, approved, flagged, waived')

    normalized_regulation = str(regulation or '').strip().upper()
    if normalized_regulation not in _ALLOWED_REGULATIONS:
        raise ValueError(f'regulation must be one of: {", ".join(sorted(_ALLOWED_REGULATIONS))}')

    # Validate checklist_items is a list of dicts
    if not isinstance(checklist_items, list):
        raise ValueError('checklist_items must be a list')

    sanitized_items = []
    for item in checklist_items:
        if not isinstance(item, dict):
            continue
        sanitized_items.append({
            'id': str(item.get('id', '')).strip()[:32],
            'label': str(item.get('label', '')).strip()[:512],
            'category': str(item.get('category', '')).strip()[:64],
            'status': str(item.get('status', 'pending')).strip().lower()[:32],
            'notes': str(item.get('notes', '')).strip()[:1000],
        })

    now = datetime.now(timezone.utc)
    row = models.RegionalLegalReview(
        entity_type=str(entity_type or '').strip().lower()[:32] or 'rfq',
        entity_id=int(entity_id),
        region=str(region or 'GLOBAL').strip().upper()[:64] or 'GLOBAL',
        regulation=normalized_regulation,
        status=normalized_status,
        checklist_items=sanitized_items,
        reviewer=str(reviewer or 'legal').strip()[:128] or 'legal',
        notes=str(notes or '').strip()[:4000] or None,
        reviewed_at=now if normalized_status != 'pending' else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(
        db,
        row.entity_type,
        int(row.entity_id),
        'legal_review_recorded',
        f'region={row.region} regulation={row.regulation} status={row.status}',
        performed_by=performed_by,
    )
    return row


def update_legal_review(
    db: Session,
    *,
    review_id: int,
    status: str,
    checklist_items: list[dict] | None = None,
    notes: str | None = None,
    reviewer: str,
    performed_by: str = 'legal',
) -> models.RegionalLegalReview:
    normalized_status = str(status or '').strip().lower()
    if normalized_status not in _ALLOWED_STATUSES:
        raise ValueError('status must be one of: pending, approved, flagged, waived')

    row = db.query(models.RegionalLegalReview).filter(models.RegionalLegalReview.id == int(review_id)).first()
    if row is None:
        raise ValueError('Legal review not found')

    row.status = normalized_status
    row.reviewer = str(reviewer or 'legal').strip()[:128] or 'legal'
    if notes is not None:
        row.notes = str(notes).strip()[:4000] or None
    if checklist_items is not None:
        sanitized = []
        for item in checklist_items:
            if not isinstance(item, dict):
                continue
            sanitized.append({
                'id': str(item.get('id', '')).strip()[:32],
                'label': str(item.get('label', '')).strip()[:512],
                'category': str(item.get('category', '')).strip()[:64],
                'status': str(item.get('status', 'pending')).strip().lower()[:32],
                'notes': str(item.get('notes', '')).strip()[:1000],
            })
        row.checklist_items = sanitized

    if normalized_status != 'pending':
        row.reviewed_at = datetime.now(timezone.utc)

    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(
        db,
        row.entity_type,
        int(row.entity_id),
        'legal_review_updated',
        f'regulation={row.regulation} status={row.status}',
        performed_by=performed_by,
    )
    return row


def list_legal_reviews(
    db: Session,
    *,
    entity_type: str | None = None,
    region: str | None = None,
    regulation: str | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[models.RegionalLegalReview]:
    limit = max(1, min(int(limit), 500))
    q = db.query(models.RegionalLegalReview)
    if entity_type is not None:
        q = q.filter(models.RegionalLegalReview.entity_type == str(entity_type).strip().lower())
    if region is not None:
        q = q.filter(models.RegionalLegalReview.region == str(region).strip().upper())
    if regulation is not None:
        q = q.filter(models.RegionalLegalReview.regulation == str(regulation).strip().upper())
    if status is not None:
        q = q.filter(models.RegionalLegalReview.status == str(status).strip().lower())
    return q.order_by(models.RegionalLegalReview.created_at.desc(), models.RegionalLegalReview.id.desc()).limit(limit).all()
