from fastapi import APIRouter

from ..schemas import LocaleStringsResponse
from ..services.i18n_preview import strings_for_locale

router = APIRouter()


@router.get('/api/v1/i18n/strings', response_model=LocaleStringsResponse)
def locale_strings(locale: str = 'en') -> LocaleStringsResponse:
    key = (locale or 'en').split('-')[0].lower()
    return LocaleStringsResponse(locale=key, strings=strings_for_locale(locale))


@router.get('/api/v1/security/i18n/strings', response_model=LocaleStringsResponse)
def security_locale_strings(locale: str = 'en') -> LocaleStringsResponse:
    key = (locale or 'en').split('-')[0].lower()
    return LocaleStringsResponse(locale=key, strings=strings_for_locale(locale))
