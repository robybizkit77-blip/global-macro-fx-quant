#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, date
from pathlib import Path

import xlrd


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


def load_eia_xls(path: Path, as_of: str) -> list[dict]:
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
                    day = parsed
                    day_idx = c
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
                text = str(v).strip()
                try:
                    candidate = float(text)
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
        raise SystemExit('No dated numeric EIA series found in XLS')
    rows = max(candidates, key=lambda x: x[0])[1]
    rows = [x for x in rows if x['date'] >= '2016-01-01']
    if len(rows) < 500:
        raise SystemExit(f'EIA direct candidate too short after 2016 filter: {len(rows)}')
    return rows


def load_fred_snapshot(path: Path) -> list[dict]:
    with path.open(newline='', encoding='utf-8-sig') as f:
        rdr = csv.DictReader(f)
        rows = []
        for row in rdr:
            day = (row.get('observation_date') or row.get('DATE') or '').strip()
            raw = (row.get('DCOILWTICO') or '').strip()
            if not day or raw in ('', '.', 'NA', 'N/A'):
                continue
            try:
                value = float(raw)
                date.fromisoformat(day)
            except Exception:
                continue
            if day >= '2016-01-01':
                rows.append({'date': day, 'value': value})
    rows.sort(key=lambda x: x['date'])
    if len(rows) < 500:
        raise SystemExit(f'Historical FRED snapshot too short: {len(rows)}')
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--eia-xls', required=True)
    ap.add_argument('--fred-snapshot-csv', required=True)
    ap.add_argument('--as-of', required=True)
    ap.add_argument('--candidate-out', required=True)
    args = ap.parse_args()

    eia = load_eia_xls(Path(args.eia_xls), args.as_of)
    fred = load_fred_snapshot(Path(args.fred_snapshot_csv))
    eia_map = {x['date']: x['value'] for x in eia}
    fred_map = {x['date']: x['value'] for x in fred}
    overlap_dates = sorted(set(eia_map) & set(fred_map))
    mismatches = [
        {'date': d, 'eia': eia_map[d], 'fred': fred_map[d]}
        for d in overlap_dates
        if not math.isclose(eia_map[d], fred_map[d], rel_tol=0, abs_tol=1e-9)
    ]
    if len(overlap_dates) < 500:
        raise SystemExit(f'Insufficient EIA/FRED overlap: {len(overlap_dates)}')
    if mismatches:
        raise SystemExit('EIA_DIRECT_EQUIVALENCE_FAILED ' + json.dumps(mismatches[:10]))

    candidate = {
        'schema': 'GMFQ_RISK_WTI_EIA_DIRECT_CANDIDATE_V1',
        'status': 'GREEN_OFFICIAL_SOURCE_CANDIDATE',
        'as_of': args.as_of,
        'source_name': 'Cushing, OK WTI Spot Price FOB (Dollars per Barrel)',
        'publisher': 'U.S. Energy Information Administration',
        'transport': 'EIA direct XLS',
        'source_url': 'https://www.eia.gov/dnav/pet/hist_xls/RWTCd.xls',
        'benchmark_key': 'RWTC',
        'frequency': 'Daily',
        'observation_count': len(eia),
        'first_date': eia[0]['date'],
        'last_date': eia[-1]['date'],
        'last_value': eia[-1]['value'],
        'historical_fred_series_id': 'DCOILWTICO',
        'equivalence_overlap_count': len(overlap_dates),
        'equivalence_mismatch_count': len(mismatches),
        'equivalence_first_date': overlap_dates[0],
        'equivalence_last_date': overlap_dates[-1],
        'observations': eia,
        'publication_performed': False,
    }
    Path(args.candidate_out).write_text(
        json.dumps(candidate, ensure_ascii=False, separators=(',', ':')),
        encoding='utf-8',
    )
    print(json.dumps({k: v for k, v in candidate.items() if k != 'observations'}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
