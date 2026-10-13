#!/usr/bin/env python3
import argparse
import csv
import io
import json
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

LIQ = Path('live_data/sections/NATIVE_LIQ_DATA.json')
DEFAULT_OUT = Path('validation/liquidity-usd-bank-credit-candidate.json')
SERIES = 'H8/H8/B1001NCBA'
SERIES_SHORT = 'B1001NCBA'
PACKAGE = 'fce2318909bacbc8ce268096deddd180'
BASE = 'https://www.federalreserve.gov/datadownload/Output.aspx'
TABLE = 'https://www.federalreserve.gov/datadownload/DownloadTable.aspx'


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'tr':
            self._row = []
        elif tag.lower() in {'td', 'th'} and self._row is not None:
            self._cell = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in {'td', 'th'} and self._cell is not None and self._row is not None:
            self._row.append(' '.join(''.join(self._cell).split()))
            self._cell = None
        elif tag == 'tr' and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None


def request_text(url):
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'global-macro-fx-quant/1.0',
            'Accept': 'text/csv,text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
        },
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        body = response.read().decode('utf-8-sig', errors='replace')
        content_type = response.headers.get('Content-Type', '')
    return body, content_type


def params():
    return {
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


def parse_csv(text):
    rows = list(csv.reader(io.StringIO(text)))
    header_idx = None
    series_col = None
    date_col = None
    for i, row in enumerate(rows):
        cells = [str(x).strip() for x in row]
        for j, cell in enumerate(cells):
            if cell == SERIES or cell.endswith('/B1001NCBA') or cell == SERIES_SHORT:
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
        return []

    parsed = []
    for row in rows[header_idx + 1:]:
        if len(row) <= max(series_col, date_col):
            continue
        date = str(row[date_col]).strip()[:10]
        raw = str(row[series_col]).strip().replace(',', '')
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date) or raw in ('', 'NA', 'N/A', '.'):
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        parsed.append((date, value))
    return dedupe(parsed)


def parse_download_table(text):
    parser = TableParser()
    parser.feed(text)
    rows = parser.rows
    header = None
    series_row = None
    for row in rows:
        if any(re.fullmatch(r'\d{4}-\d{2}-\d{2}', c) for c in row):
            header = row
        if row and any(c == SERIES_SHORT or c == SERIES or c.endswith('/B1001NCBA') for c in row[:3]):
            series_row = row
    if header is None or series_row is None:
        return []

    dates = [(i, c) for i, c in enumerate(header) if re.fullmatch(r'\d{4}-\d{2}-\d{2}', c)]
    parsed = []
    for i, date in dates:
        if i >= len(series_row):
            continue
        raw = series_row[i].replace(',', '').strip()
        if raw in ('', 'NA', 'N/A', '.'):
            continue
        try:
            parsed.append((date, float(raw)))
        except ValueError:
            continue
    return dedupe(parsed)


def dedupe(parsed):
    dedup = {}
    for date, value in parsed:
        if date in dedup and abs(dedup[date] - value) > 1e-9:
            raise SystemExit(f'conflicting Fed H8 bank-credit observations for {date}')
        dedup[date] = value
    return sorted(dedup.items())


def fetch_official():
    q = urllib.parse.urlencode(params())
    csv_url = BASE + '?' + q
    csv_body, csv_type = request_text(csv_url)
    parsed = parse_csv(csv_body)
    attempts = [{
        'transport': 'H8_DDP_OUTPUT_CSV',
        'url': csv_url,
        'content_type': csv_type,
        'body_bytes': len(csv_body.encode('utf-8')),
        'parsed_observations': len(parsed),
    }]
    if parsed:
        return parsed, 'H8_DDP_OUTPUT_CSV', csv_url, csv_type, attempts

    table_url = TABLE + '?' + q
    table_body, table_type = request_text(table_url)
    parsed = parse_download_table(table_body)
    attempts.append({
        'transport': 'H8_DDP_DOWNLOAD_TABLE',
        'url': table_url,
        'content_type': table_type,
        'body_bytes': len(table_body.encode('utf-8')),
        'parsed_observations': len(parsed),
    })
    if parsed:
        return parsed, 'H8_DDP_DOWNLOAD_TABLE', table_url, table_type, attempts

    raise SystemExit('Fed H8 official transports returned no parseable B1001NCBA observations: ' + json.dumps(attempts))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(DEFAULT_OUT))
    args = ap.parse_args()
    out = Path(args.out)

    liq = json.loads(LIQ.read_text(encoding='utf-8'))
    runtime = liq['USD']['credit']
    runtime_date = str(runtime['last_date']).strip()[:10]
    runtime_value = float(runtime['last_value'])

    parsed, transport, url, content_type, attempts = fetch_official()
    matches = [value for date, value in parsed if date == runtime_date]
    if len(matches) != 1:
        raise SystemExit(f'expected one official observation for runtime date {runtime_date}, got {len(matches)}; transport={transport}; range={parsed[0][0]}..{parsed[-1][0]}')
    official_runtime_value = matches[0]
    if abs(official_runtime_value - runtime_value) > 1e-4:
        raise SystemExit(f'runtime/source mismatch on {runtime_date}: runtime={runtime_value}, source={official_runtime_value}')

    latest_date, latest_value = parsed[-1]
    if latest_date < runtime_date:
        raise SystemExit(f'official source regressed behind runtime: {latest_date} < {runtime_date}')
    new_observations = [
        {'date': date, 'value': value}
        for date, value in parsed
        if date > runtime_date
    ]

    result = {
        'schema': 'GMFQ_LIQUIDITY_USD_BANK_CREDIT_CANDIDATE_V1',
        'source': {
            'publisher': 'Board of Governors of the Federal Reserve System',
            'release': 'H.8 Assets and Liabilities of Commercial Banks in the United States',
            'series_id': SERIES,
            'package_id': PACKAGE,
            'transport': transport,
            'url': url,
            'frequency': 'Weekly',
            'seasonal_adjustment': 'SA',
            'content_type': content_type,
            'transport_attempts': attempts,
        },
        'runtime': {'last_date': runtime_date, 'last_value': runtime_value},
        'official_runtime_value': official_runtime_value,
        'runtime_match_confirmed': True,
        'latest_date': latest_date,
        'latest_value': latest_value,
        'new_observations': new_observations,
        'candidate_update_available': bool(new_observations),
        'status': 'GREEN_SOURCE_CANDIDATE_ONLY',
        'publication_performed': False,
        'runtime_mutated': False,
    }
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
