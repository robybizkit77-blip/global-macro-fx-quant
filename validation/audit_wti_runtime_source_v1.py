#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import html.parser
import json
import math
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D_PATH = ROOT / 'live_data' / 'sections' / 'D.json'
POLICY_PATH = ROOT / 'validation' / 'risk' / 'RISK_SOURCE_POLICY_V1_2026-10-12.json'
EIA_URL = 'https://www.eia.gov/dnav/pet/hist/RWTCD.htm'


class TableParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == 'tr':
            self.row = []
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ('td', 'th') and self.cell is not None and self.row is not None:
            self.row.append(' '.join(''.join(self.cell).split()))
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            if self.row:
                self.rows.append(self.row)
            self.row = None
            self.cell = None


def parse_week_start(label: str):
    m = re.search(r'(20\d{2})\s+([A-Z][a-z]{2})-\s*(\d{1,2})\s+to\s+([A-Z][a-z]{2})-\s*(\d{1,2})', label)
    if not m:
        return None
    return dt.date(int(m.group(1)), dt.datetime.strptime(m.group(2), '%b').month, int(m.group(3)))


def business_days_between(start: dt.date, end: dt.date) -> int:
    if end < start:
        return -1
    n = 0
    cur = start
    while cur < end:
        cur += dt.timedelta(days=1)
        if cur.weekday() < 5:
            n += 1
    return n


def main() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding='utf-8'))
    cfg = policy['secondary_runtime_series']['WTI']
    if cfg.get('status') != 'SOURCE_RECOVERED_NOT_PRIMARY_GATE':
        raise SystemExit(f'unexpected WTI policy status: {cfg}')
    if cfg.get('series_id') != 'DCOILWTICO':
        raise SystemExit(f'unexpected WTI mirror series contract: {cfg}')

    d = json.loads(D_PATH.read_text(encoding='utf-8'))
    risk = d.get('risk')
    if not isinstance(risk, dict) or not isinstance(risk.get('WTI'), dict):
        raise SystemExit('D.risk.WTI missing')
    wti = risk['WTI']
    dates = wti.get('dates')
    values = wti.get('values')
    if not isinstance(dates, list) or not isinstance(values, list) or len(dates) != len(values) or not dates:
        raise SystemExit('invalid runtime WTI dates/values arrays')
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise SystemExit('runtime WTI dates not unique/monotonic')

    declared_last_date = wti.get('last_date')
    declared_last_value = wti.get('last_value')
    if declared_last_date is not None and declared_last_date != dates[-1]:
        raise SystemExit(f'contradictory WTI last_date metadata: declared={declared_last_date} array={dates[-1]}')
    if declared_last_value is not None and not math.isclose(float(declared_last_value), float(values[-1]), rel_tol=0, abs_tol=1e-12):
        raise SystemExit(f'contradictory WTI last_value metadata: declared={declared_last_value} array={values[-1]}')
    if wti.get('series_id') is not None and wti.get('series_id') != cfg['series_id']:
        raise SystemExit(f'contradictory WTI series_id metadata: {wti.get("series_id")}')

    runtime_header = {
        'schema': 'GMFQ_WTI_RUNTIME_PRECHECK_V3',
        'observation_count': len(dates),
        'first_array_date': dates[0],
        'last_array_date': dates[-1],
        'last_array_value': values[-1],
        'declared_last_date': declared_last_date,
        'declared_last_value': declared_last_value,
        'source_field': wti.get('source'),
        'series_id_field': wti.get('series_id'),
        'frequency_field': wti.get('frequency'),
        'metadata_complete': all(wti.get(k) is not None for k in ('last_date','last_value','source','series_id','frequency')),
    }
    print(json.dumps(runtime_header, indent=2, ensure_ascii=False), flush=True)

    tmp = Path(tempfile.gettempdir()) / 'RWTCD.htm'
    subprocess.run([
        'curl','-fL','--http1.1','--compressed','--retry','5','--retry-all-errors','--retry-delay','2',
        '--connect-timeout','20','--max-time','120','-A','Mozilla/5.0',EIA_URL,'-o',str(tmp)
    ], check=True)
    raw = tmp.read_text(encoding='utf-8', errors='replace')
    parser = TableParser()
    parser.feed(raw)

    source = []
    for row in parser.rows:
        if not row:
            continue
        start = parse_week_start(row[0])
        if start is None:
            continue
        for offset, raw_value in enumerate(row[1:6]):
            value_text = raw_value.strip().replace(',', '')
            if not value_text or value_text in {'-', '--', 'NA', 'N/A', 'W'}:
                continue
            try:
                value = float(value_text)
            except ValueError:
                continue
            day = start + dt.timedelta(days=offset)
            if day.weekday() >= 5:
                continue
            source.append((day.isoformat(), value))

    source.sort(key=lambda x: x[0])
    if len(source) < 6000 or source[0][0] > '2000-01-31':
        raise SystemExit(f'direct EIA WTI history unexpectedly short: {len(source)} rows, first={source[0][0] if source else None}')
    if len({day for day, _ in source}) != len(source):
        raise SystemExit('duplicate WTI dates in direct EIA source')

    source_map = dict(source)
    comparisons = []
    mismatches = []
    for day, value in zip(dates, values):
        sv = source_map.get(day)
        match = sv is not None and math.isclose(float(value), float(sv), rel_tol=0, abs_tol=1e-9)
        item = {'date': day, 'runtime': value, 'official_eia': sv, 'match': match}
        comparisons.append(item)
        if not match:
            mismatches.append(item)

    latest_date, latest_value = source[-1]
    today = dt.datetime.now(dt.timezone.utc).date()
    latest_day = dt.date.fromisoformat(latest_date)
    diagnostic = {
        'schema': 'GMFQ_WTI_RUNTIME_SOURCE_AUDIT_V3',
        'source': {
            'publisher': 'U.S. Energy Information Administration',
            'name': 'Cushing, OK WTI Spot Price FOB',
            'direct_series_code': 'RWTC',
            'daily_page': 'RWTCD',
            'fred_mirror_series_id': cfg['series_id'],
            'url': EIA_URL,
        },
        'runtime': {
            'observation_count': len(dates),
            'first_date': dates[0],
            'last_date': dates[-1],
            'last_value': values[-1],
            'metadata_complete': runtime_header['metadata_complete'],
        },
        'runtime_vs_direct_eia': comparisons,
        'mismatch_count': len(mismatches),
        'source_history': {
            'observation_count': len(source),
            'first_date': source[0][0],
            'latest_date': latest_date,
            'latest_value': latest_value,
            'business_day_lag_vs_utc_today': business_days_between(latest_day, today),
        },
        'safe_next_action': 'REPLACE_NONCANONICAL_PLACEHOLDER_WITH_DIRECT_EIA_HISTORY' if mismatches else 'BUILD_DETERMINISTIC_FULL_HISTORY_REPLACEMENT_FROM_VALIDATED_SOURCE',
        'runtime_mutated': False,
        'publication_performed': False,
    }
    print(json.dumps(diagnostic, indent=2, ensure_ascii=False), flush=True)

    if mismatches:
        raise SystemExit('WTI placeholder does not match canonical direct EIA series: ' + json.dumps(mismatches, ensure_ascii=False))


if __name__ == '__main__':
    main()
