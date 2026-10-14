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
    if candidate.get('schema') != 'GMFQ_RISK_VIX_CANDIDATE_V2' or candidate.get('status') != 'GREEN_OFFICIAL_SOURCE_CANDIDATE':
        raise SystemExit('candidate schema/status mismatch')
    observations = candidate.get('observations')
    if not isinstance(observations, list) or not observations:
        raise SystemExit('candidate observations missing')

    raw = D_PATH.read_text(encoding='utf-8')
    d = json.loads(raw)
    risk = d.get('risk')
    if not isinstance(risk, dict) or not isinstance(risk.get('VIX'), dict):
        raise SystemExit('D.risk.VIX missing')
    vix = risk['VIX']
    dates = vix.get('dates')
    values = vix.get('values')
    if not isinstance(dates, list) or not isinstance(values, list) or len(dates) != len(values) or not dates:
        raise SystemExit('invalid runtime VIX dates/values arrays')
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise SystemExit('runtime VIX dates are not strictly unique/monotonic')
    if vix.get('last_date') != dates[-1] or not math.isclose(float(vix.get('last_value')), float(values[-1]), rel_tol=0, abs_tol=1e-12):
        raise SystemExit('runtime VIX last_date/last_value drift')

    source = {x['date']: float(x['value']) for x in observations}
    if len(source) != len(observations):
        raise SystemExit('candidate has duplicate dates')
    anchor = dates[-1]
    if anchor not in source:
        raise SystemExit(f'current runtime anchor {anchor} missing from Cboe candidate')
    if not math.isclose(float(values[-1]), source[anchor], rel_tol=0, abs_tol=1e-9):
        raise SystemExit(f'anchor mismatch runtime={values[-1]} Cboe={source[anchor]} on {anchor}')

    missing = [(day, source[day]) for day in sorted(source) if day > anchor]
    new_dates = dates + [x[0] for x in missing]
    new_values = values + [x[1] for x in missing]
    if new_dates != sorted(new_dates) or len(new_dates) != len(set(new_dates)):
        raise SystemExit('resulting VIX dates are not strictly unique/monotonic')

    before_other_risk = {k: v for k, v in risk.items() if k != 'VIX'}
    vix['dates'] = new_dates
    vix['values'] = new_values
    vix['last_date'] = new_dates[-1]
    vix['last_value'] = new_values[-1]
    if {k: v for k, v in risk.items() if k != 'VIX'} != before_other_risk:
        raise SystemExit('non-VIX risk data changed unexpectedly')

    out = Path(args.replacement_out)
    out.write_text(json.dumps(d, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    receipt = {
        'schema': 'GMFQ_RISK_VIX_CONTROLLED_APPLY_RECEIPT_V1',
        'candidate_as_of': candidate['as_of'],
        'runtime_anchor_date': anchor,
        'runtime_anchor_value': values[-1],
        'appended_observation_count': len(missing),
        'first_appended_date': missing[0][0] if missing else None,
        'last_appended_date': missing[-1][0] if missing else None,
        'result_last_date': new_dates[-1],
        'result_last_value': new_values[-1],
        'result_observation_count': len(new_dates),
        'other_risk_keys_preserved': True,
        'publication_performed': False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
