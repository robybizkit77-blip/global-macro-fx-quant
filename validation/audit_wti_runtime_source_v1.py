#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import math
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D_PATH = ROOT / 'live_data' / 'sections' / 'D.json'
POLICY_PATH = ROOT / 'validation' / 'risk' / 'RISK_SOURCE_POLICY_V1_2026-10-12.json'
FRED_URL = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILWTICO&cosd=2016-01-01'


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
    if cfg.get('series_id') != 'DCOILWTICO' or cfg.get('publisher') != 'U.S. EIA via FRED':
        raise SystemExit(f'unexpected WTI source contract: {cfg}')

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
    if wti.get('last_date') != dates[-1] or not math.isclose(float(wti.get('last_value')), float(values[-1]), rel_tol=0, abs_tol=1e-12):
        raise SystemExit('runtime WTI last_date/last_value drift')

    tmp = Path(tempfile.gettempdir()) / 'DCOILWTICO-current.csv'
    subprocess.run([
        'curl','-fL','--compressed','--retry','5','--retry-all-errors','--retry-delay','2',
        '--connect-timeout','20','--max-time','180','-A','Mozilla/5.0',FRED_URL,'-o',str(tmp)
    ], check=True)
    text = tmp.read_text(encoding='utf-8-sig')
    rdr = csv.DictReader(io.StringIO(text))
    source = []
    for row in rdr:
        ds = (row.get('observation_date') or row.get('DATE') or '').strip()
        vs = (row.get('DCOILWTICO') or '').strip()
        if not ds or vs in ('', '.', 'NA', 'N/A'):
            continue
        try:
            val = float(vs)
        except ValueError:
            continue
        if val <= 0:
            raise SystemExit(f'invalid WTI value {val} on {ds}')
        source.append((ds, val))
    source.sort(key=lambda x: x[0])
    if len(source) < 500 or source[0][0] > '2016-01-31':
        raise SystemExit(f'WTI canonical download invalid: {len(source)} rows, first={source[0][0] if source else None}')
    if len({d for d, _ in source}) != len(source):
        raise SystemExit('duplicate WTI dates in source')

    source_map = dict(source)
    mismatches = []
    for day, value in zip(dates, values):
        sv = source_map.get(day)
        if sv is None or not math.isclose(float(value), float(sv), rel_tol=0, abs_tol=1e-9):
            mismatches.append({'date': day, 'runtime': value, 'source': sv})
    if mismatches:
        raise SystemExit('WTI runtime/source mismatch: ' + json.dumps(mismatches[:10]))

    anchor = dates[-1]
    missing = [(day, value) for day, value in source if day > anchor]
    latest_date, latest_value = source[-1]
    today = dt.datetime.now(dt.timezone.utc).date()
    latest_day = dt.date.fromisoformat(latest_date)
    receipt = {
        'schema': 'GMFQ_WTI_RUNTIME_SOURCE_AUDIT_V1',
        'policy_status': cfg['status'],
        'source': {
            'publisher': cfg['publisher'],
            'series_id': cfg['series_id'],
            'name': cfg['source_name'],
            'frequency': cfg['frequency'],
            'url': FRED_URL,
        },
        'runtime': {
            'observation_count': len(dates),
            'first_date': dates[0],
            'last_date': dates[-1],
            'last_value': values[-1],
            'source_field': wti.get('source'),
            'series_id_field': wti.get('series_id'),
            'frequency_field': wti.get('frequency'),
        },
        'source_history': {
            'observation_count': len(source),
            'first_date': source[0][0],
            'latest_date': latest_date,
            'latest_value': latest_value,
            'business_day_lag_vs_utc_today': business_days_between(latest_day, today),
        },
        'all_runtime_points_match_official_source': True,
        'missing_after_runtime_anchor_count': len(missing),
        'first_missing_date': missing[0][0] if missing else None,
        'last_missing_date': missing[-1][0] if missing else None,
        'safe_next_action': 'BUILD_DETERMINISTIC_FULL_HISTORY_REPLACEMENT' if len(dates) < 500 else 'APPEND_MISSING_OFFICIAL_OBSERVATIONS',
        'runtime_mutated': False,
        'publication_performed': False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
