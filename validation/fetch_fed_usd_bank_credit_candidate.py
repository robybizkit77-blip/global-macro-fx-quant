#!/usr/bin/env python3
import csv
import io
import json
import urllib.parse
import urllib.request
from pathlib import Path

LIQ = Path('live_data/sections/NATIVE_LIQ_DATA.json')
OUT = Path('validation/liquidity-usd-bank-credit-candidate.json')
SERIES = 'H8/H8/B1001NCBA'
PACKAGE = 'fce2318909bacbc8ce268096deddd180'
BASE = 'https://www.federalreserve.gov/datadownload/Output.aspx'


def fetch_csv():
    params = {
        'rel': 'H8',
        'series': PACKAGE,
        'lastObs': '80',
        'from': '',
        'to': '',
        'filetype': 'csv',
        'label': 'include',
        'layout': 'seriescolumn',
        'type': 'package',
    }
    url = BASE + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': 'global-macro-fx-quant/1.0'})
    with urllib.request.urlopen(req, timeout=45) as response:
        body = response.read().decode('utf-8-sig', errors='replace')
        content_type = response.headers.get('Content-Type', '')
    return url, body, content_type


def parse_csv(text):
    rows = list(csv.reader(io.StringIO(text)))
    header_idx = None
    series_col = None
    date_col = None
    for i, row in enumerate(rows):
        cells = [str(x).strip() for x in row]
        for j, cell in enumerate(cells):
            if cell == SERIES or cell.endswith('/B1001NCBA') or cell == 'B1001NCBA':
                header_idx = i
                series_col = j
                break
        if header_idx is not None:
            for j, cell in enumerate(cells):
                if cell.upper() in {'DATE', 'TIME_PERIOD', 'TIME PERIOD'}:
                    date_col = j
                    break
            if date_col is None:
                date_col = 0
            break
    if header_idx is None:
        sample = ' | '.join(','.join(r[:8]) for r in rows[:6])
        raise SystemExit(f'could not locate Fed H8 bank-credit series; sample={sample[:1200]}')

    parsed = []
    for row in rows[header_idx + 1:]:
        if len(row) <= max(series_col, date_col):
            continue
        date = str(row[date_col]).strip()[:10]
        raw = str(row[series_col]).strip().replace(',', '')
        if not date or raw in ('', 'NA', 'N/A', '.'):
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        parsed.append((date, value))
    if not parsed:
        raise SystemExit('no parseable Fed H8 bank-credit observations')
    dedup = {}
    for date, value in parsed:
        if date in dedup and abs(dedup[date] - value) > 1e-9:
            raise SystemExit(f'conflicting Fed H8 bank-credit observations for {date}')
        dedup[date] = value
    return sorted(dedup.items())


def main():
    liq = json.loads(LIQ.read_text(encoding='utf-8'))
    runtime = liq['USD']['credit']
    runtime_date = str(runtime['last_date']).strip()[:10]
    runtime_value = float(runtime['last_value'])

    url, text, content_type = fetch_csv()
    parsed = parse_csv(text)
    matches = [value for date, value in parsed if date == runtime_date]
    if len(matches) != 1:
        raise SystemExit(f'expected one official observation for runtime date {runtime_date}, got {len(matches)}')
    official_runtime_value = matches[0]
    if abs(official_runtime_value - runtime_value) > 1e-4:
        raise SystemExit(f'runtime/source mismatch on {runtime_date}: runtime={runtime_value}, source={official_runtime_value}')

    latest_date, latest_value = parsed[-1]
    if latest_date < runtime_date:
        raise SystemExit(f'official source regressed behind runtime: {latest_date} < {runtime_date}')

    result = {
        'schema': 'GMFQ_LIQUIDITY_USD_BANK_CREDIT_CANDIDATE_V1',
        'source': {
            'publisher': 'Board of Governors of the Federal Reserve System',
            'api': 'H.8 Data Download Program direct CSV',
            'series_id': SERIES,
            'package_id': PACKAGE,
            'url': url,
            'frequency': 'Weekly',
            'seasonal_adjustment': 'SA',
            'content_type': content_type,
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
