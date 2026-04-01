"""Minimal string bundles for future UI localization (Phase 1 stub)."""

from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    'en': {
        'app.title': 'Procurement Intelligence',
        'crm.dashboard': 'CRM dashboard',
        'consent.opt_in': 'Opt in',
        'consent.opt_out': 'Opt out',
        'admin.categorization': 'Category overrides',
        'marketing.automation.accepted': 'Accepted',
        'marketing.automation.accepted_detail': 'Logged to AuditLog; configure marketing provider in Phase 2.',
        'integrations.external_crm.accepted_detail': 'Logged to AuditLog; configure provider credentials in Phase 2.',
        'operations.escalation.1.title': 'Acknowledge alert',
        'operations.escalation.1.action': 'Open monitoring dashboard; note connector name, timestamp, and error text.',
        'operations.escalation.2.title': 'Triage connector',
        'operations.escalation.2.action': 'Re-run `/api/v1/ingestion/discovery` manually after verifying credentials and target availability.',
        'operations.escalation.3.title': 'Schema drift',
        'operations.escalation.3.action': 'If alert references schema drift, review Alembic migrations vs live DB; deploy migration or revert problematic deploy.',
        'operations.escalation.4.title': 'Categorization backlog',
        'operations.escalation.4.action': 'For repeated miscategorization, adjust `ai_engines/categorization_rules.json` and use admin override endpoints.',
        'operations.escalation.5.title': 'Close loop',
        'operations.escalation.5.action': 'Resolve `Alert` records once verified; attach compliance note via audit if customer-impacting.',
        'compliance.policy.note.1': 'Advisory robots mode: log-only unless SCRAPING_ROBOTS_MODE=enforced (future).',
        'compliance.policy.note.2': 'Rotate credentials and respect site ToS before production scraping.',
        'compliance.check.rate_limit': 'Per-connector spacing via CONNECTOR_MIN_INTERVAL_SEC (current {min_interval}).',
        'compliance.check.retry_backoff': 'CONNECTOR_MAX_RETRIES={max_retries}, exponential base {backoff}s.',
        'compliance.check.audit_trail': 'Connector fetch outcomes can be logged via AuditLog from execution wrapper.',
        'compliance.check.anti_bot': 'Connector failures with anti-bot signals raise critical alerts for manual escalation.',
        'compliance.check.regional_legal': 'Optional SCRAPING_APPROVED_CONNECTORS gate blocks non-approved connectors.',
        'compliance.check.adaptive': 'Per-connector dynamic delay increases with failure streak and decays on success.',
    },
    'hi': {
        'app.title': 'खरीद खुफिया',
        'crm.dashboard': 'सीआरएम डैशबोर्ड',
        'consent.opt_in': 'सहमति दें',
        'consent.opt_out': 'सहमति वापस लें',
        'admin.categorization': 'श्रेणी संशोधन',
        'marketing.automation.accepted': 'स्वीकृत',
        'marketing.automation.accepted_detail': 'ऑडिट लॉग में दर्ज; चरण 2 में मार्केटिंग प्रोवाइडर कॉन्फ़िगर करें।',
        'integrations.external_crm.accepted_detail': 'ऑडिट लॉग में दर्ज; चरण 2 में प्रोवाइडर क्रेडेंशियल कॉन्फ़िगर करें।',
        'operations.escalation.1.title': 'अलर्ट की पुष्टि करें',
        'operations.escalation.1.action': 'मॉनिटरिंग डैशबोर्ड खोलें; कनेक्टर नाम, समय और त्रुटि संदेश नोट करें।',
        'operations.escalation.2.title': 'कनेक्टर जाँच',
        'operations.escalation.2.action': 'क्रेडेंशियल और लक्ष्य उपलब्धता जांचने के बाद `/api/v1/ingestion/discovery` फिर चलाएँ।',
        'operations.escalation.3.title': 'स्कीमा ड्रिफ्ट',
        'operations.escalation.3.action': 'यदि अलर्ट में स्कीमा ड्रिफ्ट है, Alembic माइग्रेशन और लाइव DB की तुलना करें; आवश्यक माइग्रेशन लागू करें या समस्या वाली डिप्लॉय वापस लें।',
        'operations.escalation.4.title': 'श्रेणीकरण बैकलॉग',
        'operations.escalation.4.action': 'बार-बार गलत श्रेणीकरण होने पर `ai_engines/categorization_rules.json` समायोजित करें और एडमिन ओवरराइड endpoints उपयोग करें।',
        'operations.escalation.5.title': 'क्लोज़-लूप',
        'operations.escalation.5.action': 'सत्यापन के बाद `Alert` रिकॉर्ड resolve करें; ग्राहक-प्रभाव होने पर ऑडिट में compliance नोट जोड़ें।',
        'compliance.policy.note.1': 'Advisory robots मोड: SCRAPING_ROBOTS_MODE=enforced होने तक केवल लॉगिंग (भविष्य)।',
        'compliance.policy.note.2': 'प्रोडक्शन स्क्रैपिंग से पहले क्रेडेंशियल रोटेट करें और साइट ToS का पालन करें।',
        'compliance.check.rate_limit': 'CONNECTOR_MIN_INTERVAL_SEC के माध्यम से प्रति-कनेक्टर अंतराल (वर्तमान {min_interval}).',
        'compliance.check.retry_backoff': 'CONNECTOR_MAX_RETRIES={max_retries}, घातीय बेस {backoff}s.',
        'compliance.check.audit_trail': 'execution wrapper से कनेक्टर fetch परिणाम AuditLog में दर्ज किए जा सकते हैं।',
        'compliance.check.anti_bot': 'anti-bot संकेत वाले कनेक्टर failures पर manual escalation के लिए critical alert बनता है।',
        'compliance.check.regional_legal': 'वैकल्पिक SCRAPING_APPROVED_CONNECTORS गेट गैर-अनुमोदित कनेक्टर्स को रोकता है।',
        'compliance.check.adaptive': 'प्रति-कनेक्टर dynamic delay failure streak के साथ बढ़ता है और success पर घटता है।',
    },
}


def strings_for_locale(locale: str) -> dict[str, str]:
    key = (locale or 'en').split('-')[0].lower()
    return dict(STRINGS.get(key, STRINGS['en']))


def tr(locale: str, key: str, default: str | None = None, **kwargs) -> str:
    strings = strings_for_locale(locale)
    value = strings.get(key, default if default is not None else key)
    if kwargs:
        try:
            return value.format(**kwargs)
        except Exception:
            return value
    return value
