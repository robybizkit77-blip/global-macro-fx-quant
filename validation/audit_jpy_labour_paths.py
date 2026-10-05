#!/usr/bin/env python3
import json
from pathlib import Path

FILES = [
    Path('live_data/sections/D.json'),
    Path('live_data/sections/MACRO_SERIES.json'),
    Path('live_data/sections/MACRO_THERMOMETER_DATA.json'),
]
TOKENS = ('jpy','japan','unemp','labour','labor','disoccup','employment','jobless')


def walk(obj, path=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, path + (str(k),))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, path + (str(i),))
    else:
        yield path, obj


def relevant(path, value):
    text = '/'.join(path).lower()
    if 'jpy' in text or 'japan' in text:
        return any(t in text for t in TOKENS[2:]) or value in (2.4, 2.5, '2.4', '2.5', '2026-07', '2026-08', '2026-07-01', '2026-08-01')
    return False

report = {
    'schema_version': 'GMFQ_JPY_LABOUR_PATH_AUDIT_V1',
    'status': 'READ_ONLY',
    'authoritative_candidate': {
        'source': 'Statistics Bureau of Japan Labour Force Survey',
        'release_date': '2026-10-02',
        'period': '2026-08',
        'unemployment_rate_sa': 2.5,
        'monthly_change_pp': 0.1,
    },
    'files': {},
}

for f in FILES:
    data = json.loads(f.read_text())
    hits = []
    for p, v in walk(data):
        if relevant(p, v):
            hits.append({'path': '/'.join(p), 'value': v})
    report['files'][str(f)] = {
        'hit_count': len(hits),
        'hits': hits,
    }

out = Path('validation/JPN_LABOUR_PROPAGATION_AUDIT_2026-10-05.json')
out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
print(json.dumps(report, indent=2, ensure_ascii=False))
