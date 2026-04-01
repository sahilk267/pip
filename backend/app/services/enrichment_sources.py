from __future__ import annotations

import csv
import json
import os
import urllib.parse
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Dict

BASE_DIR = Path(__file__).resolve().parents[3]
B2B_CSV = Path(os.getenv('B2B_ENRICHMENT_CSV', BASE_DIR / 'data' / 'enrichment' / 'b2b_revenue.csv'))
B2C_CSV = Path(os.getenv('B2C_ATTRIBUTE_CSV', BASE_DIR / 'data' / 'enrichment' / 'b2c_attribute_feed.csv'))
B2B_API = os.getenv('B2B_ENRICHMENT_API')
B2C_API = os.getenv('B2C_ATTRIBUTE_API')


def _normalize_key(value: str) -> str:
    return ''.join(ch.lower() if ch.isalnum() else '_' for ch in value.strip())


def _load_csv(path: Path) -> list[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding='utf-8') as fh:
        return list(csv.DictReader(fh))


def _map_rows(rows: list[Dict[str, str]], key_column: str) -> Dict[str, Dict[str, str]]:
    mapping: Dict[str, Dict[str, str]] = {}
    for row in rows:
        key_value = row.get(key_column)
        if not key_value:
            continue
        normalized = _normalize_key(key_value)
        mapping[normalized] = {k: v for k, v in row.items() if k != key_column and v}
    return mapping


def _call_api(url: str, params: Dict[str, str]) -> Dict[str, str]:
    query = urllib.parse.urlencode(params)
    full_url = f"{url}?{query}" if query else url
    req = urllib.request.Request(full_url)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode())
    except Exception:
        return {}


@lru_cache
def _b2b_data() -> Dict[str, Dict[str, str]]:
    return _map_rows(_load_csv(B2B_CSV), 'name')


@lru_cache
def _b2c_data() -> Dict[str, Dict[str, str]]:
    return _map_rows(_load_csv(B2C_CSV), 'sku')


def fetch_vendor_enrichment(name: str) -> Dict[str, str]:
    if B2B_API:
        api_result = _call_api(B2B_API, {'name': name})
        if api_result:
            return api_result
    return _b2b_data().get(_normalize_key(name), {})


def fetch_product_attributes(sku: str) -> Dict[str, str]:
    if B2C_API:
        api_result = _call_api(B2C_API, {'sku': sku})
        if api_result:
            return api_result
    row = _b2c_data().get(_normalize_key(sku), {})
    if not row:
        return {}
    # Normalize keys/values so downstream categorization + UI are stable.
    attributes = {
        'category': (row.get('category') or '').strip() or None,
        'image_url': (row.get('image_url') or '').strip() or None,
    }
    attribute_tags = row.get('attribute_tags', '')
    for part in attribute_tags.split(';'):
        if ':' in part:
            key, value = part.split(':', 1)
            norm_key = _normalize_key(key)
            norm_val = value.strip()
            attributes[norm_key] = norm_val or None
    # Drop empty values to keep product JSON compact.
    return {k: v for k, v in attributes.items() if v}
