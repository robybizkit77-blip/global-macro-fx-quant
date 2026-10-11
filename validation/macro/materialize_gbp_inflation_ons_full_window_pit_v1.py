#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from html import unescape

INDEX = 'https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23/previous'
UA = 'GLOBAL-MACRO-FX-QUANT GBP inflation ONS full-window PIT materializer v1'
TITLE = 'CPI ANNUAL RATE 00: ALL ITEMS 2015=100'
START = datetime(2018, 1, 1)
END = datetime(2026, 9, 30)
EXPECTED_RELEASES = 105
MONTHS = {m: i for i, m in enumerate(('JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'), 1)}
DATE_RE = re.compile(r'(\d{1,2}\s+[A-Za-z]+\s+\d{4})')
CSV_LINK_RE = re.compile(r'href=["\'](?P<href>[^"\']*generator\?format=csv[^"\']*)["\']', re.I)
VERSION_RE = re.compile(r'(?:%2F|/)previous(?:%2F|/)v(?P<v>\d+)', re.I)
PERIOD_RE = re.compile(r'^(?P<year>\d{4})\s+(?P<month>JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)$', re.I)


def get(url: str, timeout: int = 45) -> bytes:
    last = None
    for attempt in range(6):
        req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,text/csv,*/*'})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            time.sleep(0.20)
            return raw
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code != 429 or attempt == 5:
                raise
            retry_after = exc.headers.get('Retry-After') if exc.headers else None
            try:
                delay = max(2.0, float(retry_after)) if retry_after else 3.0 * (attempt + 1)
            except ValueError:
                delay = 3.0 * (attempt + 1)
            time.sleep(delay)
    raise RuntimeError(f'ONS fetch failed: {last!r}')


def norm(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', ' ', unescape(s).lower()).strip()


def parse_index(raw: bytes) -> list[dict]:
    text = raw.decode('utf-8', errors='replace')
    plain = re.sub(r'<[^>]+>', ' ', text)
    plain = re.sub(r'\s+', ' ', plain)
    n = norm(plain)
    if 'd7g7' not in n or 'cpi annual rate 00 all items 2015 100' not in n:
        raise ValueError('ONS previous-version index is not canonical D7G7/MM23')
    rows = []
    for m in CSV_LINK_RE.finditer(text):
        href = unescape(m.group('href'))
        vm = VERSION_RE.search(href)
        if not vm:
            continue
        tail = text[m.end():m.end()+1200]
        dm = DATE_RE.search(re.sub(r'<[^>]+>', ' ', tail))
        if not dm:
            continue
        release_dt = datetime.strptime(dm.group(1), '%d %B %Y')
        if not (START <= release_dt <= END):
            continue
        rows.append({
            'version': int(vm.group('v')),
            'release_date': release_dt.strftime('%Y-%m-%d'),
            'csv_url': urllib.parse.urljoin(INDEX, href),
        })
    uniq = {r['version']: r for r in rows}
    out = [uniq[v] for v in sorted(uniq)]
    if len(out) != EXPECTED_RELEASES:
        raise ValueError(f'expected {EXPECTED_RELEASES} target releases, found {len(out)}')
    return out


def previous_month(release_date: str) -> str:
    d = datetime.strptime(release_date, '%Y-%m-%d')
    y, m = d.year, d.month - 1
    if m == 0:
        y, m = y - 1, 12
    mon = tuple(MONTHS.keys())[m-1]
    return f'{y:04d} {mon}'


def parse_latest_monthly(raw: bytes) -> tuple[str, float]:
    text = raw.decode('utf-8-sig', errors='replace')
    nt = norm(text)
    if 'd7g7' not in nt and 'cpi annual rate 00 all items 2015 100' not in nt:
        raise ValueError('vintage CSV lacks D7G7/title marker')
    rows = csv.reader(io.StringIO(text))
    values = []
    for row in rows:
        if not row:
            continue
        period = row[0].strip().upper()
        pm = PERIOD_RE.fullmatch(period)
        if not pm:
            continue
        value = None
        for cell in row[1:]:
            s = cell.strip().replace('%', '')
            try:
                value = float(s)
                break
            except ValueError:
                continue
        if value is None:
            continue
        key = (int(pm.group('year')), MONTHS[pm.group('month').upper()])
        values.append((key, period, value))
    if not values:
        raise ValueError('no monthly D7G7 observations parsed')
    _, period, value = max(values, key=lambda x: x[0])
    return period, value


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', required=True, type=pathlib.Path)
    args = ap.parse_args()

    index_raw = get(INDEX)
    versions = parse_index(index_raw)
    ledger = []
    for row in versions:
        raw = get(row['csv_url'])
        period, value = parse_latest_monthly(raw)
        expected_period = previous_month(row['release_date'])
        if period != expected_period:
            raise ValueError(f"v{row['version']} latest period {period} != expected {expected_period}")
        ledger.append({
            'version': row['version'],
            'release_date': row['release_date'],
            'available_for_decisions_from': row['release_date'],
            'decision_rule': 'decision_date > release_date',
            'reference_period': period,
            'value_pct': value,
            'csv_url': row['csv_url'],
            'raw_sha256': hashlib.sha256(raw).hexdigest(),
        })

    by_year = {}
    for row in ledger:
        y = row['release_date'][:4]
        by_year[y] = by_year.get(y, 0) + 1
    expected_by_year = {str(y): 12 for y in range(2018, 2026)} | {'2026': 9}
    coverage_ok = by_year == expected_by_year and len(ledger) == EXPECTED_RELEASES
    semantic_rows = [[r['version'], r['release_date'], r['reference_period'], r['value_pct'], r['csv_url'], r['raw_sha256']] for r in ledger]
    semantic_sha = hashlib.sha256(json.dumps(semantic_rows, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()

    out = {
        'schema': 'GMFQ_GBP_INFLATION_ONS_FULL_WINDOW_PIT_LEDGER_V1',
        'status': 'PIT_MATERIALIZED' if coverage_ok else 'WITHHELD',
        'authority': 'Office for National Statistics',
        'canonical_series': {
            'dataset': 'MM23',
            'series_id': 'D7G7',
            'label': TITLE,
            'unit': '%',
            'transformation': 'reported_yoy_rate',
        },
        'window': {'start_release': '2018-01-01', 'end_release': '2026-09-30'},
        'release_count': len(ledger),
        'by_release_year': by_year,
        'expected_by_release_year': expected_by_year,
        'coverage_ok': coverage_ok,
        'index_url': INDEX,
        'index_sha256': hashlib.sha256(index_raw).hexdigest(),
        'semantic_sha256': semantic_sha,
        'temporal_policy': {
            'release_time_verified': False,
            'same_day_use_allowed': False,
            'eligibility_rule': 'decision_date > release_date',
            'reason': 'Exact publication time is not asserted by this materializer; next-day eligibility is conservative and fail-closed.',
        },
        'ledger': ledger,
        'invariants': {
            'native_ons_vintages_only': True,
            'exact_series_semantics': True,
            'latest_observation_equals_previous_calendar_month': True,
            'no_cpih_substitution': True,
            'no_interpolation': True,
            'no_current_database_backfill': True,
            'production_write': False,
            'changes_live_data': False,
            'changes_engine_rules': False,
            'certification_implied': False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({
        'status': out['status'],
        'release_count': out['release_count'],
        'by_release_year': out['by_release_year'],
        'coverage_ok': out['coverage_ok'],
        'first': ledger[0],
        'last': ledger[-1],
        'semantic_sha256': out['semantic_sha256'],
    }, indent=2))
    return 0 if out['status'] == 'PIT_MATERIALIZED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
