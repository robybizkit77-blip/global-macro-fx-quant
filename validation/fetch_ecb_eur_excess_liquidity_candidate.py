#!/usr/bin/env python3
import csv
import io
import json
import urllib.parse
import urllib.request
from pathlib import Path

POLICY = Path('validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json')
LIQ = Path('live_data/sections/NATIVE_LIQ_DATA.json')
OUT = Path('validation/liquidity-eur-excess-candidate.json')
SERIES_ID = 'ILM.D.U2.C.EXLIQ.U2.EUR'
DATASET = 'ILM'
KEY = 'D.U2.C.EXLIQ.U2.EUR'
BASE = 'https://data-api.ecb.europa.eu/service/data'


def fetch_rows():
    params = urllib.parse.urlencode({'format': 'csvdata', 'startPeriod': '2026-01-01'})
    url = f'{BASE}/{DATASET}/{KEY}?{params}'
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'global-macro-fx-quant/1.0',
            'Accept': 'text/csv,application/vnd.sdmx.data+csv;version=2.0.0',
        },
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        text = response.read().decode('utf-8-sig')
    rows = list(csv.DictReader(io.StringIO(text)))
    parsed = []
    for row in rows:
        date = (row.get('TIME_PERIOD') or '')[:10]
        value_raw = row.get('OBS_VALUE')
        if not date or value_raw in (None, ''):
            continue
        parsed.append((date, float(value_raw)))
    if not parsed:
        raise SystemExit('ECB excess-liquidity source returned no parseable observations')
    dedup = {}
    for date, value in parsed:
        if date in dedup and abs(dedup[date] - value) > 1e-9:
            raise SystemExit(f'conflicting ECB observations on {date}')
        dedup[date] = value
    return url, sorted(dedup.items())


def main():
    policy = json.loads(POLICY.read_text(encoding='utf-8'))
    cfg = policy['mapped']['EUR.liquidity']
    if cfg.get('series_key') != SERIES_ID:
        raise SystemExit(f'policy series mismatch: {cfg.get("series_key")} != {SERIES_ID}')
    if cfg.get('automation_ready') is not True:
        raise SystemExit('EUR.liquidity policy must be automation-ready before collection')

    liq = json.loads(LIQ.read_text(encoding='utf-8'))
    runtime = liq['EUR']['liquidity']
    runtime_date = str(runtime['last_date'])[:10]
    runtime_value = float(runtime['last_value'])

    url, parsed = fetch_rows()
    source = dict(parsed)
    if runtime_date not in source:
        raise SystemExit(f'official ECB source has no observation for runtime date {runtime_date}')
    official_runtime_value = source[runtime_date]
    if abs(official_runtime_value - runtime_value) > 1e-9:
        raise SystemExit(
            f'runtime/source mismatch on {runtime_date}: runtime={runtime_value}, source={official_runtime_value}'
        )

    latest_date, latest_value = parsed[-1]
    if latest_date < runtime_date:
        raise SystemExit(f'official source regressed behind runtime: {latest_date} < {runtime_date}')
    policy_as_of = str(policy['as_of'])[:10]
    if latest_date > policy_as_of:
        raise SystemExit(f'future observation relative to policy as_of: {latest_date} > {policy_as_of}')

    receipt = {
        'schema': 'GMFQ_LIQUIDITY_EUR_EXCESS_CANDIDATE_V1',
        'source': {
            'publisher': 'European Central Bank',
            'api': 'ECB Data API',
            'series_id': SERIES_ID,
            'url': url,
            'frequency': 'Daily',
        },
        'policy_as_of': policy_as_of,
        'runtime': {'last_date': runtime_date, 'last_value': runtime_value},
        'official_runtime_value': official_runtime_value,
        'runtime_match_confirmed': True,
        'latest_date': latest_date,
        'latest_value': latest_value,
        'candidate_update_available': latest_date > runtime_date,
        'status': 'GREEN_SOURCE_CANDIDATE_ONLY',
        'publication_performed': False,
        'runtime_mutated': False,
    }
    OUT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
