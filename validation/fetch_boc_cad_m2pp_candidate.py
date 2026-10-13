#!/usr/bin/env python3
import json
import urllib.request
from pathlib import Path

POLICY = Path('validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json')
LIQ = Path('live_data/sections/NATIVE_LIQ_DATA.json')
OUT = Path('validation/liquidity-cad-m2pp-candidate.json')
SERIES = 'V41552801'
URL = f'https://www.bankofcanada.ca/valet/observations/{SERIES}/json?recent=36'


def main():
    policy = json.loads(POLICY.read_text(encoding='utf-8'))
    liq = json.loads(LIQ.read_text(encoding='utf-8'))
    cfg = policy['mapped']['CAD.money']
    runtime = liq['CAD']['money']

    if cfg.get('series_key') != SERIES:
        raise SystemExit(f'policy series mismatch: {cfg.get("series_key")} != {SERIES}')
    if cfg.get('series_mapping_status') != 'EXACT_SERIES_KEY_RUNTIME_MATCH_CONFIRMED':
        raise SystemExit('CAD.money must be exact-mapped before collection')

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
    match_value = matches[0]
    if abs(match_value - runtime_value) > 1e-9:
        raise SystemExit(f'runtime/source mismatch on {runtime_date}: runtime={runtime_value}, source={match_value}')

    latest_date, latest_value = parsed[-1]
    if latest_date < runtime_date:
        raise SystemExit(f'official source regressed behind runtime: {latest_date} < {runtime_date}')
    if latest_date > policy['as_of']:
        raise SystemExit(f'future official observation relative to policy as_of: {latest_date}')

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
        'policy_as_of': policy['as_of'],
        'runtime': {'last_date': runtime_date, 'last_value': runtime_value},
        'runtime_match_confirmed': True,
        'latest_date': latest_date,
        'latest_value': latest_value,
        'candidate_update_available': latest_date > runtime_date,
        'status': 'GREEN_SOURCE_CANDIDATE_ONLY',
        'publication_performed': False,
        'runtime_mutated': False,
    }
    OUT.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
