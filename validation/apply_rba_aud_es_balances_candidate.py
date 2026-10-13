#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

DEFAULT_RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')
SERIES_ID = 'AESAT'


def norm_date(value: str) -> str:
    s = str(value).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d %b %Y', '%d %B %Y'):
        try:
            return datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except ValueError:
            pass
    raise SystemExit(f'invalid AUD ES date: {value!r}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--runtime', default=str(DEFAULT_RUNTIME))
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    candidate = json.loads(Path(args.candidate).read_text(encoding='utf-8'))
    runtime_path = Path(args.runtime)
    liq = json.loads(runtime_path.read_text(encoding='utf-8'))

    if candidate.get('schema') != 'GMFQ_LIQUIDITY_AUD_ES_BALANCES_CANDIDATE_V1':
        raise SystemExit('invalid AUD ES candidate schema')
    if candidate.get('status') != 'GREEN_SOURCE_CANDIDATE_ONLY':
        raise SystemExit('AUD ES candidate proof is not GREEN')
    source = candidate.get('source') or {}
    if source.get('series_id') != SERIES_ID or source.get('frequency') != 'DAILY':
        raise SystemExit('unexpected RBA AUD ES source contract')
    proof = candidate.get('proof') or {}
    if float(proof.get('exact_match_ratio', 0)) < 0.98:
        raise SystemExit('AUD ES historical exact-match ratio below contract')
    if proof.get('recent_20_exact') is not True or proof.get('runtime_last_matches_official') is not True:
        raise SystemExit('AUD ES runtime/source proof is not exact on recent window')

    contract = candidate.get('snapshot_contract') or {}
    if contract.get('runtime_frequency') != 'WEEKLY_SNAPSHOT' or contract.get('interpolation_allowed') is not False:
        raise SystemExit('AUD ES weekly snapshot contract missing or invalid')
    weekday = int(contract.get('weekday'))
    if weekday < 0 or weekday > 6:
        raise SystemExit('AUD ES snapshot weekday invalid')

    runtime = liq['AUD']['liquidity']
    dates = list(runtime.get('dates') or [])
    values = list(runtime.get('values') or [])
    if not dates or len(dates) != len(values):
        raise SystemExit('invalid AUD.liquidity runtime arrays')
    normalized_dates = [norm_date(x) for x in dates]
    runtime_last = normalized_dates[-1]
    if norm_date(runtime.get('last_date')) != runtime_last:
        raise SystemExit('AUD.liquidity last_date inconsistent with dates array')
    if abs(float(values[-1]) - float(runtime.get('last_value'))) > 1e-9:
        raise SystemExit('AUD.liquidity last_value inconsistent with values array')

    cand_runtime = candidate.get('runtime') or {}
    if norm_date(cand_runtime.get('last_date')) != runtime_last:
        raise SystemExit('candidate built against different AUD.liquidity runtime date')
    if abs(float(cand_runtime.get('last_value')) - float(runtime.get('last_value'))) > 1e-9:
        raise SystemExit('candidate built against different AUD.liquidity runtime value')

    new = []
    prev = datetime.strptime(runtime_last, '%Y-%m-%d').date()
    for row in candidate.get('new_observations') or []:
        d = norm_date(row.get('date'))
        dd = datetime.strptime(d, '%Y-%m-%d').date()
        v = float(row.get('value'))
        gap = (dd - prev).days
        if dd.weekday() != weekday:
            raise SystemExit(f'AUD ES snapshot weekday drift on {d}')
        if gap < 7 or gap % 7 != 0:
            raise SystemExit(f'AUD ES weekly snapshot cadence break: previous={prev}, current={d}, gap={gap}')
        if v < 0:
            raise SystemExit(f'invalid AUD ES balance on {d}: {v}')
        new.append((d, v))
        prev = dd

    if bool(new) != bool(candidate.get('candidate_update_available')):
        raise SystemExit('candidate_update_available disagrees with new_observations')
    if new and new[-1][0] != norm_date(candidate.get('latest_eligible_snapshot_date')):
        raise SystemExit('latest eligible AUD ES snapshot disagrees with new_observations')

    updated = json.loads(json.dumps(liq))
    target = updated['AUD']['liquidity']
    n = len(target['dates'])
    old_dates = list(target['dates'])
    old_values = list(target['values'])
    for d, v in new:
        target['dates'].append(d)
        target['values'].append(v)
    if new:
        target['last_date'] = new[-1][0]
        target['last_value'] = new[-1][1]
    if target['dates'][:n] != old_dates or target['values'][:n] != old_values:
        raise SystemExit('AUD ES controlled apply attempted to rewrite history')

    changed = updated != liq
    receipt = {
        'schema': 'GMFQ_LIQUIDITY_AUD_ES_BALANCES_APPLY_RECEIPT_V1',
        'status': 'UPDATE_AVAILABLE' if changed else 'NO_CHANGE',
        'series_id': SERIES_ID,
        'snapshot_weekday': weekday,
        'before_last_date': runtime.get('last_date'),
        'before_last_value': runtime.get('last_value'),
        'after_last_date': target.get('last_date'),
        'after_last_value': target.get('last_value'),
        'appended_observations': len(new),
        'applied': bool(args.apply and changed),
        'publication_performed': False,
    }
    if args.apply and changed:
        runtime_path.write_text(json.dumps(updated, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
