#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path

DEFAULT_RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')

CONTRACTS = {
    'GBP.liquidity': {'runtime_key': 'liquidity', 'series_id': 'RPWB56A', 'frequency': 'Weekly'},
    'GBP.credit': {'runtime_key': 'credit', 'series_id': 'LPMVTYI', 'frequency': 'Monthly'},
}


def parse_date(value: str) -> date:
    raw = str(value or '').strip()
    if not raw:
        raise SystemExit(f'invalid date: {value}')
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise SystemExit(f'invalid ISO date: {value}') from exc


def normalized_date(value: str) -> str:
    return parse_date(value).isoformat()


def month_key(value: str) -> tuple[int, int]:
    d = parse_date(value)
    return d.year, d.month


def next_month_key(value: str) -> tuple[int, int]:
    y, m = month_key(value)
    return (y + 1, 1) if m == 12 else (y, m + 1)


def validate_sequence(policy_key: str, runtime_last_date: str, rows: list[dict]) -> list[tuple[str, float]]:
    spec = CONTRACTS[policy_key]
    normalized = []
    prev = parse_date(runtime_last_date)
    expected_month = next_month_key(runtime_last_date) if spec['frequency'] == 'Monthly' else None

    for row in rows:
        raw_date = str(row.get('date') or '')
        d = parse_date(raw_date)
        value = float(row.get('value'))
        if d <= prev:
            raise SystemExit(f'{policy_key}: non-increasing candidate date {raw_date}')
        if spec['frequency'] == 'Weekly':
            gap = (d - prev).days
            if not 4 <= gap <= 10:
                raise SystemExit(f'{policy_key}: implausible weekly gap {gap} days ({prev} -> {d})')
        else:
            if (d.year, d.month) != expected_month:
                raise SystemExit(f'{policy_key}: non-contiguous monthly sequence at {raw_date}; expected {expected_month}')
            expected_month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
        normalized.append((d.isoformat(), value))
        prev = d
    return normalized


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--runtime', default=str(DEFAULT_RUNTIME))
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    candidate = json.loads(Path(args.candidate).read_text(encoding='utf-8'))
    runtime_path = Path(args.runtime)
    liq = json.loads(runtime_path.read_text(encoding='utf-8'))

    if candidate.get('schema') != 'GMFQ_LIQUIDITY_GBP_BOE_CANDIDATES_V1':
        raise SystemExit('invalid GBP BoE candidate schema')
    if candidate.get('status') != 'GREEN_SOURCE_CANDIDATE_ONLY':
        raise SystemExit('GBP BoE candidate proof is not GREEN')
    if candidate.get('series_count') != 2:
        raise SystemExit('expected exactly two GBP BoE candidate series')

    updated = json.loads(json.dumps(liq))
    receipts = {}

    for policy_key, spec in CONTRACTS.items():
        row = (candidate.get('results') or {}).get(policy_key) or {}
        source = row.get('source') or {}
        if source.get('series_id') != spec['series_id']:
            raise SystemExit(f'{policy_key}: unexpected series id')
        if row.get('runtime_match_confirmed') is not True or row.get('status') != 'GREEN_SOURCE_CANDIDATE_ONLY':
            raise SystemExit(f'{policy_key}: candidate source/runtime proof is not GREEN')

        runtime = liq['GBP'][spec['runtime_key']]
        target = updated['GBP'][spec['runtime_key']]
        dates = list(runtime.get('dates') or [])
        values = list(runtime.get('values') or [])
        if len(dates) != len(values) or not dates:
            raise SystemExit(f'{policy_key}: invalid runtime arrays')
        if normalized_date(dates[-1]) != normalized_date(runtime.get('last_date')):
            raise SystemExit(f'{policy_key}: runtime last_date inconsistency')
        if abs(float(values[-1]) - float(runtime.get('last_value'))) > 1e-9:
            raise SystemExit(f'{policy_key}: runtime last_value inconsistency')

        cand_runtime = row.get('runtime') or {}
        if normalized_date(cand_runtime.get('last_date')) != normalized_date(runtime.get('last_date')):
            raise SystemExit(f'{policy_key}: candidate built against different runtime last_date')
        if abs(float(cand_runtime.get('last_value')) - float(runtime.get('last_value'))) > 1e-9:
            raise SystemExit(f'{policy_key}: candidate built against different runtime last_value')

        normalized = validate_sequence(policy_key, str(runtime['last_date']), row.get('new_observations') or [])
        if bool(normalized) != bool(row.get('candidate_update_available')):
            raise SystemExit(f'{policy_key}: candidate_update_available disagrees with observations')

        original_dates = list(target['dates'])
        original_values = list(target['values'])
        for d, value in normalized:
            target['dates'].append(d)
            target['values'].append(value)
        if normalized:
            target['last_date'] = normalized[-1][0]
            target['last_value'] = normalized[-1][1]
        if target['dates'][:len(original_dates)] != original_dates or target['values'][:len(original_values)] != original_values:
            raise SystemExit(f'{policy_key}: controlled apply attempted to rewrite history')

        receipts[policy_key] = {
            'series_id': spec['series_id'],
            'before_last_date': runtime['last_date'],
            'before_last_value': runtime['last_value'],
            'after_last_date': target['last_date'],
            'after_last_value': target['last_value'],
            'appended_observations': len(normalized),
        }

    changed = updated != liq
    receipt = {
        'schema': 'GMFQ_LIQUIDITY_GBP_BOE_APPLY_RECEIPT_V1',
        'status': 'UPDATE_AVAILABLE' if changed else 'NO_CHANGE',
        'results': receipts,
        'applied': bool(args.apply and changed),
        'publication_performed': False,
    }
    if args.apply and changed:
        runtime_path.write_text(json.dumps(updated, separators=(',', ':')) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
