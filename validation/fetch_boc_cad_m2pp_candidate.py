#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

LIQ = Path('live_data/sections/NATIVE_LIQ_DATA.json')
DEFAULT_OUT = Path('validation/liquidity-cad-m2pp-candidate.json')
SERIES = 'V41552801'
URL = f'https://www.bankofcanada.ca/valet/observations/{SERIES}/json?recent=36'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(DEFAULT_OUT))
    args = ap.parse_args()

    liq = json.loads(LIQ.read_text(encoding='utf-8'))
    runtime = liq['CAD']['money']

    req = urllib.request.Request(URL, headers={'User-Agent': 'global-macro-fx-quant/1.0'})
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.loads(response.read().decode('utf-8'))

    parsed = []
    for row in payload.get('observations', []):
        date = str(row.get('d') or '').strip()
        cell = row.get(SERIES) or {}
        value_raw = cell.get('v')
        if not date or value_raw in (None, ''):
            continue
        value = float(value_raw)
        if value <= 0:
            raise SystemExit(f'invalid CAD M2++ value on {date}: {value}')
        parsed.append((date, value))
    if not parsed:
        raise SystemExit('no CAD M2++ observations parsed from BoC Valet')
    parsed.sort(key=lambda x: x[0])

    runtime_date = str(runtime['last_date'])
    runtime_value = float(runtime['last_value'])
    matches = [value for date, value in parsed if date == runtime_date]
    if len(matches) != 1:
        raise SystemExit(f'expected one official observation for runtime date {runtime_date}, got {len(matches)}')
    if abs(matches[0] - runtime_value) > 1e-9:
        raise SystemExit(f'runtime/source mismatch on {runtime_date}: runtime={runtime_value}, source={matches[0]}')

    latest_date, latest_value = parsed[-1]
    if latest_date < runtime_date:
        raise SystemExit(f'official source regressed behind runtime: {latest_date} < {runtime_date}')

    new_observations = [
        {'date': date, 'value': value}
        for date, value in parsed
        if date > runtime_date
    ]

    result = {
        'schema': 'GMFQ_LIQUIDITY_CAD_M2PP_CANDIDATE_V1',
        'source': {
            'publisher': 'Bank of Canada',
            'api': 'Valet API',
            'series_id': SERIES,
            'name': 'M2++ (gross), seasonally adjusted',
            'url': URL,
            'frequency': 'Monthly',
        },
        'runtime': {'last_date': runtime_date, 'last_value': runtime_value},
        'runtime_match_confirmed': True,
        'latest_date': latest_date,
        'latest_value': latest_value,
        'candidate_update_available': bool(new_observations),
        'new_observations': new_observations,
        'status': 'GREEN_SOURCE_CANDIDATE_ONLY',
        'publication_performed': False,
        'runtime_mutated': False,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
