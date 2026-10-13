#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')
DEFAULT_OUT = Path('validation/liquidity-usd-bank-credit-h8-xml-candidate.json')
URL = 'https://www.federalreserve.gov/datadownload/Output.aspx?filetype=zip&rel=H8'
SERIES = 'B1001NCBA'


def norm_date(v):
    s = str(v).strip()
    for fmt in ('%Y-%m-%d', '%Y-%m', '%d %b %Y', '%d %B %Y'):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime('%Y-%m-%d') if fmt != '%Y-%m' else dt.strftime('%Y-%m')
        except ValueError:
            pass
    raise SystemExit(f'unparseable USD.credit date {v!r}')


def fetch_zip():
    req = urllib.request.Request(URL, headers={'User-Agent': 'GMFQ-validation/1.0', 'Accept': 'application/zip,application/octet-stream,*/*'})
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read()
    if len(body) < 1_000_000:
        raise SystemExit(f'H8 ZIP unexpectedly small: {len(body)} bytes')
    return body


def parse_series(body):
    with zipfile.ZipFile(io.BytesIO(body)) as zf:
        raw = zf.read('H8_data.xml')
    source = {}
    metadata = None
    in_target = False
    # Capture observations while inside the target Series. This avoids clearing Obs
    # elements before the parent Series end event is reached.
    for event, elem in ET.iterparse(io.BytesIO(raw), events=('start', 'end')):
        tag = elem.tag.rsplit('}', 1)[-1]
        if event == 'start' and tag == 'Series':
            in_target = elem.attrib.get('SERIES_NAME') == SERIES
            if in_target:
                metadata = dict(elem.attrib)
            continue
        if event == 'end' and in_target and tag == 'Obs':
            d = elem.attrib.get('TIME_PERIOD')
            v = elem.attrib.get('OBS_VALUE')
            if d and v not in (None, ''):
                source[d] = float(v)
            elem.clear()
            continue
        if event == 'end' and tag == 'Series':
            if in_target:
                break
            in_target = False
            elem.clear()
            continue
        if event == 'end' and not in_target:
            elem.clear()
    if metadata is None or not source:
        raise SystemExit(f'Fed H8 series {SERIES} not found in official XML')
    if metadata.get('FREQ') != '19' or metadata.get('SA') != 'SA' or metadata.get('ITEM') != '1001':
        raise SystemExit(f'unexpected H8 metadata for {SERIES}: {metadata}')
    return metadata, source


def runtime_series():
    liq = json.loads(RUNTIME.read_text(encoding='utf-8'))
    row = liq['USD']['credit']
    dates = list(row.get('dates') or [])
    values = list(row.get('values') or [])
    if not dates or len(dates) != len(values):
        raise SystemExit('invalid USD.credit runtime arrays')
    parsed = [(norm_date(d), float(v), str(d)) for d, v in zip(dates, values)]
    return row, parsed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(DEFAULT_OUT))
    args = ap.parse_args()

    row, parsed = runtime_series()
    metadata, source = parse_series(fetch_zip())

    # If runtime is day-resolved, require exact-date matching. If it is monthly,
    # fail closed rather than inventing an aggregation rule.
    if any(len(d) == 7 for d, _, _ in parsed):
        raise SystemExit('USD.credit runtime is monthly; no weekly-to-monthly aggregation rule is certified')
    rt = {d: v for d, v, _ in parsed}
    overlap = sorted(set(rt) & set(source))
    mismatches = [
        {'date': d, 'runtime': rt[d], 'official': source[d], 'diff': rt[d] - source[d]}
        for d in overlap if abs(rt[d] - source[d]) > 1e-6
    ]
    exact = len(overlap) - len(mismatches)
    runtime_last = norm_date(row.get('last_date'))
    last_value = float(row.get('last_value'))
    last_match = runtime_last in source and abs(last_value - source[runtime_last]) <= 1e-6
    recent = overlap[-20:]
    recent_exact = len(recent) == 20 and all(abs(rt[d] - source[d]) <= 1e-6 for d in recent)
    latest = max(source)
    new = [{'date': d, 'value': source[d]} for d in sorted(source) if d > runtime_last]

    green = len(overlap) >= 52 and last_match and recent_exact
    result = {
        'schema': 'GMFQ_LIQUIDITY_USD_BANK_CREDIT_H8_XML_CANDIDATE_V1',
        'status': 'GREEN_SOURCE_CANDIDATE_ONLY' if green else 'WITHHELD_RUNTIME_SOURCE_MISMATCH',
        'source': {
            'publisher': 'Federal Reserve Board',
            'release': 'H.8 Assets and Liabilities of Commercial Banks in the United States',
            'series_id': SERIES,
            'url': URL,
            'transport': 'official full-release SDMX/XML ZIP',
            'frequency': 'WEEKLY',
            'seasonal_adjustment': 'SA',
            'unit_multiplier': metadata.get('UNIT_MULT'),
        },
        'runtime': {'count': len(rt), 'last_date': runtime_last, 'last_value': last_value},
        'proof': {
            'overlap_count': len(overlap),
            'exact_match_count': exact,
            'mismatch_count': len(mismatches),
            'mismatches': mismatches[:40],
            'runtime_last_matches_official': last_match,
            'recent_20_exact': recent_exact,
        },
        'runtime_match_confirmed': green,
        'latest_date': latest,
        'latest_value': source[latest],
        'candidate_update_available': bool(new),
        'new_observations': new,
        'runtime_mutated': False,
        'publication_performed': False,
    }
    Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
