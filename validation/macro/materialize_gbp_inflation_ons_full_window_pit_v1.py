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
from html.parser import HTMLParser

INDEX = 'https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23/previous'
UA = 'GLOBAL-MACRO-FX-QUANT GBP inflation ONS full-window PIT materializer v1'
TITLE = 'CPI ANNUAL RATE 00: ALL ITEMS 2015=100'
START = datetime(2018, 1, 1)
END = datetime(2026, 9, 30)
EXPECTED_RELEASES = 105
MONTH_NAMES = ('JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC')
MONTHS = {m: i for i, m in enumerate(MONTH_NAMES, 1)}
DATE_RE = re.compile(r'\b(\d{1,2}\s+[A-Za-z]+\s+\d{4})\b')
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


class RowParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_tr = False
        self.current_text: list[str] = []
        self.current_hrefs: list[str] = []
        self.rows: list[tuple[str, list[str]]] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'tr':
            self.in_tr = True
            self.current_text = []
            self.current_hrefs = []
        elif self.in_tr and tag.lower() == 'a':
            href = dict(attrs).get('href')
            if href:
                self.current_hrefs.append(unescape(href))

    def handle_data(self, data):
        if self.in_tr:
            self.current_text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == 'tr' and self.in_tr:
            text = re.sub(r'\s+', ' ', ' '.join(self.current_text)).strip()
            self.rows.append((text, self.current_hrefs[:]))
            self.in_tr = False
            self.current_text = []
            self.current_hrefs = []


def parse_superseded_rows(raw: bytes) -> list[dict]:
    text = raw.decode('utf-8', errors='replace')
    plain = re.sub(r'<[^>]+>', ' ', text)
    n = norm(plain)
    if 'd7g7' not in n or 'cpi annual rate 00 all items 2015 100' not in n:
        raise ValueError('ONS previous-version index is not canonical D7G7/MM23')

    parser = RowParser()
    parser.feed(text)
    rows = []
    for row_text, hrefs in parser.rows:
        dm = DATE_RE.search(row_text)
        if not dm:
            continue
        csv_candidates = []
        for href in hrefs:
            if 'generator?format=csv' not in href.lower():
                continue
            vm = VERSION_RE.search(href)
            if vm:
                csv_candidates.append((int(vm.group('v')), urllib.parse.urljoin(INDEX, href)))
        if len(csv_candidates) != 1:
            continue
        version, csv_url = csv_candidates[0]
        superseded_dt = datetime.strptime(dm.group(1), '%d %B %Y')
        rows.append({
            'version': version,
            'date_superseded': superseded_dt.strftime('%Y-%m-%d'),
            'date_superseded_dt': superseded_dt,
            'csv_url': csv_url,
            'row_text': row_text,
        })

    uniq = {r['version']: r for r in rows}
    rows = sorted(uniq.values(), key=lambda r: r['date_superseded_dt'])
    if len(rows) < 100:
        raise ValueError(f'too few ONS superseded-version rows parsed: {len(rows)}')
    return rows


def build_effective_versions(rows: list[dict]) -> list[dict]:
    out = []
    for i in range(1, len(rows)):
        current = rows[i]
        previous_supersession = rows[i-1]['date_superseded_dt']
        effective_from = previous_supersession
        effective_until = current['date_superseded_dt']
        if START <= effective_from <= END:
            out.append({
                'version': current['version'],
                'effective_from': effective_from.strftime('%Y-%m-%d'),
                'effective_until_exclusive': effective_until.strftime('%Y-%m-%d'),
                'csv_url': current['csv_url'],
            })
    return out


def previous_month(effective_from: str) -> str:
    d = datetime.strptime(effective_from, '%Y-%m-%d')
    y, m = d.year, d.month - 1
    if m == 0:
        y, m = y - 1, 12
    return f'{y:04d} {MONTH_NAMES[m-1]}'


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
    superseded_rows = parse_superseded_rows(index_raw)
    versions = build_effective_versions(superseded_rows)

    if len(versions) not in {104, 105}:
        raise ValueError(f'unexpected effective release count before latest-version handling: {len(versions)}')

    # Critical temporal sentinel: the file superseded on 13-Feb-2018 must be the
    # vintage that became effective on 16-Jan-2018 and should contain Dec-2017 CPI.
    sentinel = next((r for r in versions if r['effective_from'] == '2018-01-16'), None)
    if not sentinel:
        raise ValueError('missing 2018-01-16 effective vintage sentinel')
    sentinel_raw = get(sentinel['csv_url'])
    sentinel_period, _ = parse_latest_monthly(sentinel_raw)
    if sentinel_period != '2017 DEC':
        raise ValueError(f"temporal sentinel failed: v{sentinel['version']} effective 2018-01-16 latest={sentinel_period}, expected 2017 DEC")

    ledger = []
    for row in versions:
        raw = sentinel_raw if row['version'] == sentinel['version'] else get(row['csv_url'])
        period, value = parse_latest_monthly(raw)
        expected_period = previous_month(row['effective_from'])
        if period != expected_period:
            raise ValueError(f"v{row['version']} latest period {period} != expected {expected_period} for effective_from {row['effective_from']}")
        ledger.append({
            'version': row['version'],
            'effective_from': row['effective_from'],
            'effective_until_exclusive': row['effective_until_exclusive'],
            'decision_rule': 'decision_date > effective_from',
            'reference_period': period,
            'value_pct': value,
            'csv_url': row['csv_url'],
            'raw_sha256': hashlib.sha256(raw).hexdigest(),
        })

    by_year = {}
    for row in ledger:
        y = row['effective_from'][:4]
        by_year[y] = by_year.get(y, 0) + 1
    expected_by_year = {str(y): 12 for y in range(2018, 2026)} | {'2026': 9}

    # The superseded table may not yet include the currently-active September 2026
    # vintage. Until the latest-version row is explicitly incorporated and checked,
    # fail closed instead of pretending full 105-release coverage.
    coverage_ok = by_year == expected_by_year and len(ledger) == EXPECTED_RELEASES
    semantic_rows = [[r['version'], r['effective_from'], r['effective_until_exclusive'], r['reference_period'], r['value_pct'], r['csv_url'], r['raw_sha256']] for r in ledger]
    semantic_sha = hashlib.sha256(json.dumps(semantic_rows, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()

    out = {
        'schema': 'GMFQ_GBP_INFLATION_ONS_FULL_WINDOW_PIT_LEDGER_V1',
        'status': 'PIT_MATERIALIZED' if coverage_ok else 'WITHHELD_CURRENT_VERSION_PENDING',
        'authority': 'Office for National Statistics',
        'canonical_series': {'dataset': 'MM23', 'series_id': 'D7G7', 'label': TITLE, 'unit': '%', 'transformation': 'reported_yoy_rate'},
        'window': {'start_effective_from': '2018-01-01', 'end_effective_from': '2026-09-30'},
        'release_count': len(ledger),
        'by_release_year': by_year,
        'expected_by_release_year': expected_by_year,
        'coverage_ok': coverage_ok,
        'index_url': INDEX,
        'index_sha256': hashlib.sha256(index_raw).hexdigest(),
        'semantic_sha256': semantic_sha,
        'temporal_policy': {
            'ons_table_semantics': 'Each archived file is associated with its Date superseded. Its effective_from is the previous supersession date.',
            'release_time_verified': False,
            'same_day_use_allowed': False,
            'eligibility_rule': 'decision_date > effective_from',
        },
        'ledger': ledger,
        'invariants': {
            'native_ons_vintages_only': True,
            'same_table_row_version_to_superseded_date_pairing': True,
            'effective_from_derived_from_previous_supersession': True,
            'temporal_sentinel_2018_01_16_is_dec_2017': True,
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
    print(json.dumps({'status': out['status'], 'release_count': len(ledger), 'by_release_year': by_year, 'coverage_ok': coverage_ok, 'sentinel': sentinel, 'first': ledger[0] if ledger else None, 'last': ledger[-1] if ledger else None, 'semantic_sha256': semantic_sha}, indent=2))
    return 0 if out['status'] == 'PIT_MATERIALIZED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
