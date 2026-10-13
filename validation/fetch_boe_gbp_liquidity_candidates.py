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


def normalize_runtime_date(value):
    return str(value or '').strip()


def normalize_boe_date(text):
    raw = str(text or '').strip()
    if not raw:
        return ''
    for fmt in ('%d %b %Y', '%d %b %y', '%d/%b/%Y', '%d-%b-%Y'):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    return raw


def fetch_csv():
    params = {
        'csv.x': 'yes',
        'Datefrom': '01/Jan/2026',
        'Dateto': 'now',
        'SeriesCodes': ','.join(spec['series_id'] for spec in SERIES.values()),
        'UsingCodes': 'Y',
        'CSVF': 'TN',
        'VPD': 'Y',
        'VFD': 'N',
    }
    url = BASE + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': 'global-macro-fx-quant/1.0'})
    with urllib.request.urlopen(req, timeout=45) as response:
        text = response.read().decode('utf-8-sig', errors='replace')
    return url, text


def parse_csv(text):
    rows = list(csv.reader(io.StringIO(text)))
    wanted = [spec['series_id'] for spec in SERIES.values()]
    header_idx = None
    header = None
    for i, row in enumerate(rows):
        cells = [str(x).strip() for x in row]
        if all(code in cells for code in wanted):
            header_idx = i
            header = cells
            break
    if header_idx is None:
        raise SystemExit(f'could not locate BoE CSV header containing {wanted}')

    idx = {code: header.index(code) for code in wanted}
    date_col = 0
    parsed = {code: [] for code in wanted}
    for row in rows[header_idx + 1:]:
        if not row:
            continue
        if len(row) <= max(idx.values()):
            continue
        date = normalize_boe_date(row[date_col])
        if not date or len(date) < 10:
            continue
        for code in wanted:
            raw = str(row[idx[code]]).strip().replace(',', '')
            if raw in ('', '..', 'n/a'):
                continue
            try:
                value = float(raw)
            except ValueError:
                continue
            parsed[code].append((date, value))

    for code in wanted:
        if not parsed[code]:
            raise SystemExit(f'no parseable BoE observations for {code}')
        parsed[code].sort(key=lambda x: x[0])
    return parsed


def main():
    policy = json.loads(POLICY.read_text(encoding='utf-8'))
    liq = json.loads(LIQ.read_text(encoding='utf-8'))
    url, text = fetch_csv()
    parsed = parse_csv(text)
    results = {}

    for policy_key, spec in SERIES.items():
        cfg = policy['mapped'][policy_key]
        if cfg.get('series_key') != spec['series_id']:
            raise SystemExit(f'{policy_key} policy series mismatch: {cfg.get("series_key")} != {spec["series_id"]}')
        if cfg.get('series_mapping_status') != 'EXACT_SERIES_KEY_RUNTIME_MATCH_CONFIRMED':
            raise SystemExit(f'{policy_key} must be exact-mapped before collection')

        runtime = liq['GBP'][spec['runtime_key']]
        runtime_date = normalize_runtime_date(runtime['last_date'])
        runtime_value = float(runtime['last_value'])
        observations = parsed[spec['series_id']]

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
