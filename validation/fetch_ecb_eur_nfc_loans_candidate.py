#!/usr/bin/env python3
import csv
import io
import json
import urllib.parse
import urllib.request
from pathlib import Path

LIQ = Path('live_data/sections/NATIVE_LIQ_DATA.json')
OUT = Path('validation/liquidity-eur-nfc-loans-candidate.json')
SERIES_ID = 'BSI.M.U2.Y.U.A20.A.1.U2.2240.Z01.E'
DATASET = 'BSI'
KEY = 'M.U2.Y.U.A20.A.1.U2.2240.Z01.E'
BASE = 'https://data-api.ecb.europa.eu/service/data'


def fetch_rows():
    params = urllib.parse.urlencode({'format': 'csvdata', 'startPeriod': '2024-01'})
    url = f'{BASE}/{DATASET}/{KEY}?{params}'
    req = urllib.request.Request(url, headers={
        'User-Agent': 'global-macro-fx-quant/1.0',
        'Accept': 'text/csv,application/vnd.sdmx.data+csv;version=2.0.0',
    })
    with urllib.request.urlopen(req, timeout=45) as response:
        text = response.read().decode('utf-8-sig')
    rows = list(csv.DictReader(io.StringIO(text)))
    parsed = []
    for row in rows:
        date = (row.get('TIME_PERIOD') or '')[:7]
        raw = row.get('OBS_VALUE')
        if not date or raw in (None, ''):
            continue
        parsed.append((date, float(raw)))
    if not parsed:
        raise SystemExit('ECB NFC-loans source returned no parseable observations')
    dedup = {}
    for date, value in parsed:
        if date in dedup and abs(dedup[date] - value) > 1e-9:
            raise SystemExit(f'conflicting ECB observations on {date}')
        dedup[date] = value
    return url, sorted(dedup.items())


def main():
    liq = json.loads(LIQ.read_text(encoding='utf-8'))
    runtime = liq['EUR']['credit']
    runtime_date = str(runtime['last_date']).strip()[:7]
    runtime_value = float(runtime['last_value'])
    url, parsed = fetch_rows()
    source = dict(parsed)
    if runtime_date not in source:
        raise SystemExit(f'official ECB source has no observation for runtime date {runtime_date}')
    official_runtime_value = source[runtime_date]
    if abs(official_runtime_value - runtime_value) > 1e-6:
        raise SystemExit(f'runtime/source mismatch on {runtime_date}: runtime={runtime_value}, source={official_runtime_value}')
    latest_date, latest_value = parsed[-1]
    if latest_date < runtime_date:
        raise SystemExit(f'official source regressed behind runtime: {latest_date} < {runtime_date}')
    result = {
        'schema': 'GMFQ_LIQUIDITY_EUR_NFC_LOANS_CANDIDATE_V1',
        'source': {
            'publisher': 'European Central Bank / ESCB',
            'api': 'ECB Data API',
            'series_id': SERIES_ID,
            'url': url,
            'frequency': 'Monthly',
            'adjustment': 'Working-day and seasonally adjusted',
            'unit': 'Millions of euro',
        },
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
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
