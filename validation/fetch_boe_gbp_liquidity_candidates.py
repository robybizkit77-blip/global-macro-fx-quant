#!/usr/bin/env python3
import csv
import io
import json
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

POLICY = Path('validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json')
LIQ = Path('live_data/sections/NATIVE_LIQ_DATA.json')
OUT = Path('validation/liquidity-gbp-boe-candidates.json')
BASE = 'https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp'

SERIES = {
    'GBP.liquidity': {
        'series_id': 'RPWB56A',
        'runtime_key': 'liquidity',
        'frequency': 'Weekly',
        'name': 'Central Bank sterling reserve balance liabilities',
    },
    'GBP.credit': {
        'series_id': 'LPMVTYI',
        'runtime_key': 'credit',
        'frequency': 'Monthly',
        'name': '12 month growth rate of total sterling net secured lending to individuals, seasonally adjusted',
    },
}


def normalize_date(text):
    raw = str(text or '').strip()
    if not raw:
        return ''
    try:
        return datetime.fromisoformat(raw).date().isoformat()
    except ValueError:
        pass
    for fmt in ('%d %b %Y', '%d %b %y', '%d/%b/%Y', '%d-%b-%Y'):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    return raw


def boe_date(iso_date):
    return datetime.fromisoformat(iso_date).strftime('%d/%b/%Y')


def fetch_csv(series_id, policy_as_of):
    params = {
        'csv.x': 'yes',
        'Datefrom': '01/Jan/2026',
        'Dateto': boe_date(policy_as_of),
        'SeriesCodes': series_id,
        'UsingCodes': 'Y',
        'CSVF': 'TN',
        'VPD': 'Y',
        'VFD': 'N',
    }
    url = BASE + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (compatible; global-macro-fx-quant/1.0)',
            'Accept': 'text/csv,text/plain,*/*',
        },
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        text = response.read().decode('utf-8-sig', errors='replace')
    return url, text


def parse_csv(text, series_id):
    rows = list(csv.reader(io.StringIO(text)))
    header_idx = None
    series_col = None
    date_col = 0
    for i, row in enumerate(rows):
        cells = [str(x).strip() for x in row]
        if series_id in cells:
            header_idx = i
            series_col = cells.index(series_id)
            for j, cell in enumerate(cells):
                if cell.upper() in {'DATE', 'TIME_PERIOD', 'TIME PERIOD'}:
                    date_col = j
                    break
            break
    if header_idx is None:
        sample = ' | '.join(','.join(r[:5]) for r in rows[:5])
        raise SystemExit(f'could not locate BoE CSV header for {series_id}; sample={sample[:800]}')

    parsed = []
    for row in rows[header_idx + 1:]:
        if not row or len(row) <= max(series_col, date_col):
            continue
        date = normalize_date(row[date_col])
        raw = str(row[series_col]).strip().replace(',', '')
        if not date or len(date) < 10 or raw.lower() in ('', '..', 'n/a'):
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        parsed.append((date, value))

    if not parsed:
        raise SystemExit(f'no parseable BoE observations for {series_id}')
    parsed.sort(key=lambda x: x[0])
    dedup = {}
    for date, value in parsed:
        if date in dedup and abs(dedup[date] - value) > 1e-9:
            raise SystemExit(f'conflicting BoE observations for {series_id} on {date}')
        dedup[date] = value
    return sorted(dedup.items())


def main():
    policy = json.loads(POLICY.read_text(encoding='utf-8'))
    liq = json.loads(LIQ.read_text(encoding='utf-8'))
    results = {}

    for policy_key, spec in SERIES.items():
        cfg = policy['mapped'][policy_key]
        if cfg.get('series_key') != spec['series_id']:
            raise SystemExit(f'{policy_key} policy series mismatch: {cfg.get("series_key")} != {spec["series_id"]}')
        if cfg.get('series_mapping_status') != 'EXACT_SERIES_KEY_RUNTIME_MATCH_CONFIRMED':
            raise SystemExit(f'{policy_key} must be exact-mapped before collection')

        runtime = liq['GBP'][spec['runtime_key']]
        runtime_date = normalize_date(runtime['last_date'])
        runtime_value = float(runtime['last_value'])

        url, text = fetch_csv(spec['series_id'], policy['as_of'])
        observations = parse_csv(text, spec['series_id'])
        matches = [value for date, value in observations if date == runtime_date]
        if len(matches) != 1:
            raise SystemExit(f'{policy_key}: expected one official observation for runtime date {runtime_date}, got {len(matches)}')
        official_runtime_value = matches[0]
        if abs(official_runtime_value - runtime_value) > 1e-9:
            raise SystemExit(
                f'{policy_key}: runtime/source mismatch on {runtime_date}: '
                f'runtime={runtime_value}, source={official_runtime_value}'
            )

        latest_date, latest_value = observations[-1]
        if latest_date < runtime_date:
            raise SystemExit(f'{policy_key}: official source regressed behind runtime: {latest_date} < {runtime_date}')
        if latest_date > policy['as_of']:
            raise SystemExit(f'{policy_key}: future official observation relative to policy as_of: {latest_date}')

        results[policy_key] = {
            'source': {
                'publisher': 'Bank of England',
                'api': 'BoE Database automatic CSV download',
                'series_id': spec['series_id'],
                'name': spec['name'],
                'url': url,
                'frequency': spec['frequency'],
            },
            'runtime': {'last_date': runtime_date, 'last_value': runtime_value},
            'official_runtime_value': official_runtime_value,
            'runtime_match_confirmed': True,
            'latest_date': latest_date,
            'latest_value': latest_value,
            'candidate_update_available': latest_date > runtime_date,
            'status': 'GREEN_SOURCE_CANDIDATE_ONLY',
        }

    receipt = {
        'schema': 'GMFQ_LIQUIDITY_GBP_BOE_CANDIDATES_V1',
        'policy_as_of': policy['as_of'],
        'series_count': len(results),
        'results': results,
        'status': 'GREEN_SOURCE_CANDIDATE_ONLY',
        'publication_performed': False,
        'runtime_mutated': False,
    }
    OUT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
