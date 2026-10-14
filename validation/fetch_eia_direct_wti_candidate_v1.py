#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import subprocess
import tempfile
from datetime import date, datetime
from pathlib import Path

import xlrd

SOURCE_URL = 'https://www.eia.gov/dnav/pet/hist_xls/RWTCd.xls'


def norm_date(value, datemode: int) -> str | None:
    if isinstance(value, (int, float)) and value:
        try:
            return xlrd.xldate_as_datetime(value, datemode).date().isoformat()
        except Exception:
            return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y', '%Y%m%d'):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def parse_xls(path: Path, as_of: str) -> list[dict]:
    book = xlrd.open_workbook(path)
    cutoff = date.fromisoformat(as_of)
    candidates: list[tuple[int, list[dict]]] = []
    for sheet in book.sheets():
        rows: list[dict] = []
        for r in range(sheet.nrows):
            vals = [sheet.cell_value(r, c) for c in range(sheet.ncols)]
            day = None
            day_idx = None
            for c, v in enumerate(vals):
                parsed = norm_date(v, book.datemode)
                if parsed:
                    day, day_idx = parsed, c
                    break
            if not day or date.fromisoformat(day) > cutoff:
                continue
            numeric = None
            for c, v in enumerate(vals):
                if c == day_idx:
                    continue
                if isinstance(v, (int, float)) and math.isfinite(float(v)):
                    numeric = float(v)
                    break
                try:
                    candidate = float(str(v).strip())
                except Exception:
                    continue
                if math.isfinite(candidate):
                    numeric = candidate
                    break
            if numeric is not None:
                rows.append({'date': day, 'value': numeric})
        if rows:
            uniq = {x['date']: x['value'] for x in rows}
            clean = [{'date': d, 'value': uniq[d]} for d in sorted(uniq)]
            candidates.append((len(clean), clean))
    if not candidates:
        raise SystemExit('No dated numeric WTI series found in official EIA XLS')
    rows = max(candidates, key=lambda x: x[0])[1]
    rows = [x for x in rows if x['date'] >= '2016-01-01']
    if len(rows) < 500:
        raise SystemExit(f'EIA WTI candidate too short: {len(rows)}')
    dates = [x['date'] for x in rows]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise SystemExit('EIA WTI dates are not unique/monotonic')
    if dates[0] > '2016-01-31':
        raise SystemExit(f'EIA WTI candidate starts too late: {dates[0]}')
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--as-of', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    date.fromisoformat(args.as_of)

    with tempfile.TemporaryDirectory() as td:
        xls_path = Path(td) / 'RWTCd.xls'
        subprocess.run([
            'curl', '-fL', '--compressed', '--retry', '2', '--retry-all-errors',
            '--retry-delay', '2', '--retry-max-time', '90', '--connect-timeout', '15',
            '--max-time', '45', '-A', 'Mozilla/5.0', SOURCE_URL, '-o', str(xls_path),
        ], check=True)
        observations = parse_xls(xls_path, args.as_of)

    candidate = {
        'schema': 'GMFQ_RISK_WTI_EIA_DIRECT_CANDIDATE_V1',
        'status': 'GREEN_OFFICIAL_SOURCE_CANDIDATE',
        'as_of': args.as_of,
        'source_name': 'Cushing, OK WTI Spot Price FOB (Dollars per Barrel)',
        'publisher': 'U.S. Energy Information Administration',
        'transport': 'EIA direct XLS',
        'source_url': SOURCE_URL,
        'benchmark_key': 'RWTC',
        'historical_fred_series_id': 'DCOILWTICO',
        'frequency': 'Daily',
        'observation_count': len(observations),
        'first_date': observations[0]['date'],
        'last_date': observations[-1]['date'],
        'last_value': observations[-1]['value'],
        'observations': observations,
        'publication_performed': False,
    }
    Path(args.out).write_text(json.dumps(candidate, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(json.dumps({k: v for k, v in candidate.items() if k != 'observations'}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
