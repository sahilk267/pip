from fastapi import APIRouter

from ..schemas import EscalationPlaybookResponse
from ..services.escalation import get_playbook

router = APIRouter()


@router.get('/api/v1/operations/escalation-playbook', response_model=EscalationPlaybookResponse)
def escalation_playbook(locale: str = 'en') -> EscalationPlaybookResponse:
    return EscalationPlaybookResponse(steps=get_playbook(locale=locale))


@router.get('/api/v1/security/data-breach/incident-response-playbook', response_model=EscalationPlaybookResponse)
def security_data_breach_incident_response_playbook(locale: str = 'en') -> EscalationPlaybookResponse:
    return EscalationPlaybookResponse(steps=get_playbook(locale=locale))
