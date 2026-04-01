from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import models
from ..crud import log_audit


def upsert_exchange_rate(
    db: Session,
    *,
    base_currency: str,
    quote_currency: str,
    rate: float,
    source: str = 'manual',
    rate_metadata: dict | None = None,
    created_by: str = 'finance',
) -> models.CurrencyExchangeRate:
    base = str(base_currency or '').strip().upper()[:8]
    quote = str(quote_currency or '').strip().upper()[:8]
    if not base or not quote:
        raise ValueError('base_currency and quote_currency are required')
    if float(rate or 0.0) <= 0.0:
        raise ValueError('rate must be > 0')

    row = models.CurrencyExchangeRate(
        base_currency=base,
        quote_currency=quote,
        rate=float(rate),
        source=str(source or 'manual').strip().lower()[:64] or 'manual',
        as_of=datetime.now(timezone.utc),
        rate_metadata=rate_metadata or {},
        created_by=str(created_by or 'finance').strip()[:128] or 'finance',
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(
        db,
        'currency_rate',
        row.id,
        'currency_exchange_rate_upserted',
        f'{base}/{quote} rate={row.rate}',
        performed_by=row.created_by,
    )
    return row


def upsert_tax_rule(
    db: Session,
    *,
    region: str,
    country_code: str,
    tax_name: str,
    tax_type: str,
    tax_rate: float,
    applies_to: str = 'order',
    rule_metadata: dict | None = None,
    created_by: str = 'finance',
) -> models.TaxComplianceRule:
    normalized_type = str(tax_type or 'exclusive').strip().lower()
    if normalized_type not in {'inclusive', 'exclusive'}:
        raise ValueError('tax_type must be inclusive or exclusive')
    if float(tax_rate or 0.0) < 0.0:
        raise ValueError('tax_rate must be >= 0')

    row = models.TaxComplianceRule(
        region=str(region or '').strip().upper()[:64] or 'GLOBAL',
        country_code=str(country_code or '').strip().upper()[:8] or 'GLOBAL',
        tax_name=str(tax_name or '').strip()[:64] or 'Tax',
        tax_type=normalized_type,
        tax_rate=float(tax_rate),
        applies_to=str(applies_to or 'order').strip().lower()[:32] or 'order',
        status='active',
        effective_from=datetime.now(timezone.utc),
        rule_metadata=rule_metadata or {},
        created_by=str(created_by or 'finance').strip()[:128] or 'finance',
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    log_audit(
        db,
        'tax_rule',
        row.id,
        'tax_compliance_rule_upserted',
        f'country={row.country_code} tax={row.tax_name} rate={row.tax_rate}',
        performed_by=row.created_by,
    )
    return row


def _latest_rate(db: Session, base_currency: str, quote_currency: str) -> models.CurrencyExchangeRate | None:
    return (
        db.query(models.CurrencyExchangeRate)
        .filter(
            models.CurrencyExchangeRate.base_currency == str(base_currency).strip().upper(),
            models.CurrencyExchangeRate.quote_currency == str(quote_currency).strip().upper(),
        )
        .order_by(models.CurrencyExchangeRate.as_of.desc(), models.CurrencyExchangeRate.id.desc())
        .first()
    )


def convert_amount(
    db: Session,
    *,
    amount: float,
    from_currency: str,
    to_currency: str,
) -> tuple[float, float]:
    from_code = str(from_currency or '').strip().upper()[:8]
    to_code = str(to_currency or '').strip().upper()[:8]
    if from_code == to_code:
        return round(float(amount or 0.0), 2), 1.0

    row = _latest_rate(db, base_currency=from_code, quote_currency=to_code)
    if row is None:
        inverse = _latest_rate(db, base_currency=to_code, quote_currency=from_code)
        if inverse is None or float(inverse.rate or 0.0) <= 0.0:
            raise ValueError(f'No exchange rate found for {from_code}/{to_code}')
        rate = 1.0 / float(inverse.rate)
    else:
        rate = float(row.rate)

    return round(float(amount or 0.0) * rate, 2), rate


def compute_tax(
    db: Session,
    *,
    amount: float,
    country_code: str,
    applies_to: str = 'order',
) -> tuple[float, float, str]:
    rule = (
        db.query(models.TaxComplianceRule)
        .filter(
            models.TaxComplianceRule.country_code == str(country_code or '').strip().upper()[:8],
            models.TaxComplianceRule.applies_to == str(applies_to or 'order').strip().lower()[:32],
            models.TaxComplianceRule.status == 'active',
        )
        .order_by(models.TaxComplianceRule.effective_from.desc(), models.TaxComplianceRule.id.desc())
        .first()
    )

    subtotal = round(float(amount or 0.0), 2)
    if rule is None:
        return subtotal, 0.0, 'NO_TAX_RULE'

    rate = float(rule.tax_rate or 0.0)
    if rule.tax_type == 'inclusive':
        tax_amount = round(subtotal - (subtotal / (1.0 + rate / 100.0)), 2) if rate > 0 else 0.0
        total = subtotal
    else:
        tax_amount = round(subtotal * (rate / 100.0), 2)
        total = round(subtotal + tax_amount, 2)

    return total, tax_amount, str(rule.tax_name)


def pricing_preview(
    db: Session,
    *,
    amount: float,
    from_currency: str,
    to_currency: str,
    country_code: str,
) -> dict:
    converted_amount, fx_rate = convert_amount(
        db,
        amount=amount,
        from_currency=from_currency,
        to_currency=to_currency,
    )
    total_with_tax, tax_amount, tax_name = compute_tax(
        db,
        amount=converted_amount,
        country_code=country_code,
        applies_to='order',
    )

    return {
        'base_amount': round(float(amount or 0.0), 2),
        'base_currency': str(from_currency or '').strip().upper()[:8],
        'target_currency': str(to_currency or '').strip().upper()[:8],
        'fx_rate': round(float(fx_rate), 8),
        'converted_amount': round(float(converted_amount), 2),
        'tax_name': tax_name,
        'tax_amount': round(float(tax_amount), 2),
        'total_amount': round(float(total_with_tax), 2),
        'country_code': str(country_code or '').strip().upper()[:8],
    }
