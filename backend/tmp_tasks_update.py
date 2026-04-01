from pathlib import Path
path = Path('backend/app/tasks.py')
text = path.read_text()
needle = 'from .database import SessionLocal\nfrom . import models, crud'
if needle not in text:
    raise SystemExit('needle missing')
if 'services.discovery' not in text:
    text = text.replace(needle, needle + '\nfrom .services.discovery import run_discovery', 1)
if  compute-data-quality-metrics-every-hour  not in text:
    path.write_text(text)
else:
    path.write_text(text)
