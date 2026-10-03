#!/usr/bin/env python3
import json
from pathlib import Path

SRC = Path('validation/pit_batch/bea/BEA_PIO_PIT_BATCH_V1_2026-10-03.json')
OUT = Path('validation/pit_batch/bea/BEA_PIO_PIT_AUDIT_V1_2026-10-03.json')
FIELDS = [
    'release_date',
    'personal_income_first_release_mom_pct',
    'real_dpi_first_release_mom_pct',
    'real_pce_first_release_mom_pct',
]

data = json.loads(SRC.read_text(encoding='utf-8'))
rows = data['rows']
missing = {f: [] for f in FIELDS}
for r in rows:
    for f in FIELDS:
        if r.get(f) is None:
            missing[f].append(r['observation_month'])

per_series = {
    f: {
        'available': len(rows) - len(months),
        'total': len(rows),
        'coverage_pct': round(100 * (len(rows) - len(months)) / len(rows), 2) if rows else 0,
        'missing_months': months,
    }
    for f, months in missing.items()
}

payload = {
    'schema': 'GMFQ_BEA_PIO_PIT_AUDIT_V1',
    'rows_found': len(rows),
    'rows_complete_all_fields': sum(all(r.get(f) is not None for f in FIELDS) for r in rows),
    'per_field': per_series,
}
OUT.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
print(json.dumps(payload, indent=2))
