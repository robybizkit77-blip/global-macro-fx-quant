#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D_PATH = ROOT / 'live_data' / 'sections' / 'D.json'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--replacement-out', required=True)
    args = ap.parse_args()

    candidate = json.loads(Path(args.candidate).read_text(encoding='utf-8'))
    if candidate.get('schema') != 'GMFQ_RISK_WTI_DIRECT_EIA_CANDIDATE_V1':
        raise SystemExit('WTI candidate schema mismatch')
    if candidate.get('status') != 'GREEN_OFFICIAL_EIA_CANDIDATE':
        raise SystemExit('WTI candidate is not GREEN')
    observations = candidate.get('observations')
    if not isinstance(observations, list) or len(observations) < 6000:
        raise SystemExit('WTI candidate observations missing/short')

    dates = [x['date'] for x in observations]
    values = [x['value'] for x in observations]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise SystemExit('WTI candidate dates not unique/monotonic')

    d = json.loads(D_PATH.read_text(encoding='utf-8'))
    risk = d.get('risk')
    if not isinstance(risk, dict) or not isinstance(risk.get('WTI'), dict):
        raise SystemExit('D.risk.WTI missing')
    before_other_risk = {k: v for k, v in risk.items() if k != 'WTI'}

    source = candidate['source']
    risk['WTI'] = {
        'dates': dates,
        'values': values,
        'source': source['publisher'],
        'source_name': source['name'],
        'source_url': source['url'],
        'series_id': source['direct_series_code'],
        'fred_mirror_series_id': source['fred_mirror_series_id'],
        'frequency': source['frequency'],
        'last_date': candidate['latest_date'],
        'last_value': candidate['latest_value'],
    }

    if {k: v for k, v in risk.items() if k != 'WTI'} != before_other_risk:
        raise SystemExit('non-WTI risk data changed unexpectedly')
    if risk['WTI']['last_date'] != risk['WTI']['dates'][-1] or risk['WTI']['last_value'] != risk['WTI']['values'][-1]:
        raise SystemExit('WTI last_date/last_value inconsistency after replacement')

    out = Path(args.replacement_out)
    out.write_text(json.dumps(d, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    receipt = {
        'schema': 'GMFQ_RISK_WTI_FULL_REPLACEMENT_RECEIPT_V1',
        'replaced_placeholder': True,
        'result_observation_count': len(dates),
        'result_first_date': dates[0],
        'result_last_date': dates[-1],
        'result_last_value': values[-1],
        'source': source,
        'other_risk_keys_preserved': True,
        'publication_performed': False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
