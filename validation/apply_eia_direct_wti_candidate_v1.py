#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D_PATH = ROOT / 'live_data' / 'sections' / 'D.json'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--replacement-out', required=True)
    args = ap.parse_args()

    candidate = json.loads(Path(args.candidate).read_text(encoding='utf-8'))
    if candidate.get('schema') != 'GMFQ_RISK_WTI_EIA_DIRECT_CANDIDATE_V1':
        raise SystemExit('candidate schema mismatch')
    if candidate.get('status') != 'GREEN_OFFICIAL_SOURCE_CANDIDATE':
        raise SystemExit('candidate status mismatch')
    if candidate.get('publisher') != 'U.S. Energy Information Administration':
        raise SystemExit('candidate publisher mismatch')
    if candidate.get('benchmark_key') != 'RWTC':
        raise SystemExit('candidate benchmark mismatch')
    observations = candidate.get('observations')
    if not isinstance(observations, list) or len(observations) < 500:
        raise SystemExit('candidate observations missing/too short')

    source_dates = [x['date'] for x in observations]
    source_values = [float(x['value']) for x in observations]
    if source_dates != sorted(source_dates) or len(source_dates) != len(set(source_dates)):
        raise SystemExit('candidate dates are not unique/monotonic')
    if source_dates[0] > '2016-01-31':
        raise SystemExit('candidate does not cover canonical history start')

    d = json.loads(D_PATH.read_text(encoding='utf-8'))
    risk = d.get('risk')
    if not isinstance(risk, dict) or not isinstance(risk.get('WTI'), dict):
        raise SystemExit('D.risk.WTI missing')

    current = risk['WTI']
    current_dates = current.get('dates') if isinstance(current.get('dates'), list) else []
    current_values = current.get('values') if isinstance(current.get('values'), list) else []
    if len(current_dates) != len(current_values):
        raise SystemExit('current WTI dates/values length mismatch')

    source_map = {x['date']: float(x['value']) for x in observations}
    overlap = 0
    overlap_mismatches = []
    for day, raw_value in zip(current_dates, current_values):
        if day not in source_map:
            continue
        overlap += 1
        try:
            value = float(raw_value)
        except Exception:
            overlap_mismatches.append({'date': day, 'runtime': raw_value, 'source': source_map[day]})
            continue
        if not math.isclose(value, source_map[day], rel_tol=0, abs_tol=1e-9):
            overlap_mismatches.append({'date': day, 'runtime': value, 'source': source_map[day]})

    before_other_risk = {k: v for k, v in risk.items() if k != 'WTI'}
    before_outside = dict(d)
    before_outside['risk'] = before_other_risk

    replacement_wti = {
        'dates': source_dates,
        'values': source_values,
        'source': 'U.S. Energy Information Administration',
        'benchmark_key': 'RWTC',
        'historical_fred_series_id': 'DCOILWTICO',
        'frequency': 'Daily',
        'last_date': source_dates[-1],
        'last_value': source_values[-1],
    }
    risk['WTI'] = replacement_wti

    after_other_risk = {k: v for k, v in risk.items() if k != 'WTI'}
    after_outside = dict(d)
    after_outside['risk'] = after_other_risk
    if after_other_risk != before_other_risk:
        raise SystemExit('non-WTI risk data changed unexpectedly')
    if after_outside != before_outside:
        raise SystemExit('data outside D.risk.WTI changed unexpectedly')

    Path(args.replacement_out).write_text(
        json.dumps(d, ensure_ascii=False, separators=(',', ':')), encoding='utf-8'
    )

    receipt = {
        'schema': 'GMFQ_RISK_WTI_CONTROLLED_REBUILD_RECEIPT_V1',
        'candidate_as_of': candidate['as_of'],
        'source_publisher': candidate['publisher'],
        'source_benchmark_key': candidate['benchmark_key'],
        'historical_fred_series_id': candidate.get('historical_fred_series_id'),
        'runtime_before_observation_count': len(current_dates),
        'runtime_before_last_date': current_dates[-1] if current_dates else current.get('last_date'),
        'runtime_before_last_value': current_values[-1] if current_values else current.get('last_value'),
        'overlap_observation_count': overlap,
        'overlap_mismatch_count': len(overlap_mismatches),
        'overlap_mismatch_sample': overlap_mismatches[:10],
        'result_observation_count': len(source_dates),
        'result_first_date': source_dates[0],
        'result_last_date': source_dates[-1],
        'result_last_value': source_values[-1],
        'full_rebuild_from_canonical_source': True,
        'other_risk_keys_preserved': True,
        'publication_performed': False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
