#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path


def parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--as-of', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    as_of = parse_date(args.as_of)
    url = (
        'https://fred.stlouisfed.org/graph/fredgraph.csv'
        f'?id=DCOILWTICO&cosd=2016-01-01&coed={args.as_of}'
    )

    with tempfile.TemporaryDirectory() as td:
        csv_path = Path(td) / 'DCOILWTICO.csv'
        cmd = [
            'curl', '-fL', '--compressed', '--retry', '5', '--retry-all-errors',
            '--retry-delay', '3', '--connect-timeout', '20', '--max-time', '180',
            '-A', 'Mozilla/5.0', url, '-o', str(csv_path),
        ]
        subprocess.run(cmd, check=True)
        text = csv_path.read_text(encoding='utf-8-sig')

    rdr = csv.DictReader(io.StringIO(text))
    observations = []
    for row in rdr:
        day = (row.get('observation_date') or row.get('DATE') or '').strip()
        raw = (row.get('DCOILWTICO') or '').strip()
        if not day or raw in ('', '.', 'NA', 'N/A'):
            continue
        try:
            dt = parse_date(day)
            value = float(raw)
        except Exception:
            continue
        if dt > as_of:
            continue
        observations.append({'date': day, 'value': value})

    observations.sort(key=lambda x: x['date'])
    dates = [x['date'] for x in observations]
    if len(observations) < 500:
        raise SystemExit(f'WTI candidate too short: {len(observations)} observations')
    if dates[0] > '2016-01-31':
        raise SystemExit(f'WTI candidate starts too late: {dates[0]}')
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise SystemExit('WTI candidate dates are not unique/monotonic')

    candidate = {
        'schema': 'GMFQ_RISK_WTI_CANDIDATE_V1',
        'status': 'GREEN_OFFICIAL_SOURCE_CANDIDATE',
        'as_of': args.as_of,
        'source_name': 'Crude Oil Prices: West Texas Intermediate (WTI) - Cushing, Oklahoma',
        'publisher': 'U.S. Energy Information Administration via FRED',
        'transport': 'FRED graph CSV',
        'series_id': 'DCOILWTICO',
        'source_url': url,
        'frequency': 'Daily',
        'observation_count': len(observations),
        'first_date': observations[0]['date'],
        'last_date': observations[-1]['date'],
        'last_value': observations[-1]['value'],
        'observations': observations,
        'publication_performed': False,
    }
    Path(args.out).write_text(
        json.dumps(candidate, ensure_ascii=False, separators=(',', ':')),
        encoding='utf-8',
    )
    print(json.dumps({k: v for k, v in candidate.items() if k != 'observations'}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
