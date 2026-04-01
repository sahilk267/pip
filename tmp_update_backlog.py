from pathlib import Path
path = Path('project-management/PHASE-1-BACKLOG.md')
text = path.read_text()
old = '| Build monitoring dashboard for connector health and enrichment status | Platform Team | In Progress | Planning dashboards tied to Celery audit logs and monitor_data_sources counts. |\n'
new = '| Build monitoring dashboard for connector health and enrichment status | Platform Team | Completed | backend/app/routers/monitoring.py exposes /api/v1/monitoring/dashboard, backend/app/services/monitoring.py raises alerts, and backend/tests/test_monitoring.py covers monitoring snapshots. |\n'
if old not in text:
    raise SystemExit('line missing')
text = text.replace(old, new, 1)
path.write_text(text)
