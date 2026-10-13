#!/usr/bin/env python3
import json
from pathlib import Path

from fetch_fed_usd_bank_credit_candidate import fetch_official, SERIES

RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')
SCALE = 0.001  # Fed H.8 is USD millions; runtime is USD billions.
TOL = 1e-4


def main():
    d = json.loads(RUNTIME.read_text(encoding='utf-8'))
    lane = d['USD']['credit']
    rt = {str(date)[:10]: float(value) for date, value in zip(lane['dates'], lane['values'])}
    official, transport, url, content_type, attempts = fetch_official()
    off = {date: value * SCALE for date, value in official}
    common = sorted(set(rt) & set(off))
    if not common:
        raise SystemExit('no overlap between runtime and official Fed H8 observations')

    diffs = []
    exact = 0
    for date in common:
        diff = rt[date] - off[date]
        if abs(diff) <= TOL:
            exact += 1
        diffs.append({
            'date': date,
            'runtime': rt[date],
            'official_scaled': off[date],
            'diff': diff,
            'abs_diff': abs(diff),
        })

    recent = diffs[-20:]
    max_abs = max(x['abs_diff'] for x in diffs)
    mae = sum(x['abs_diff'] for x in diffs) / len(diffs)
    recent_mae = sum(x['abs_diff'] for x in recent) / len(recent)
    runtime_last = str(lane['last_date'])[:10]
    result = {
        'schema': 'GMFQ_LIQUIDITY_USD_BANK_CREDIT_REVISION_DIAGNOSTIC_V1',
        'source': {
            'publisher': 'Board of Governors of the Federal Reserve System',
            'series_id': SERIES,
            'transport': transport,
            'url': url,
            'content_type': content_type,
            'native_unit': 'USD millions',
            'runtime_unit': 'USD billions',
            'scale_to_runtime': SCALE,
            'transport_attempts': attempts,
        },
        'runtime': {
            'count': len(rt),
            'last_date': runtime_last,
            'last_value': float(lane['last_value']),
        },
        'proof': {
            'overlap_count': len(common),
            'exact_match_count': exact,
            'exact_match_ratio': exact / len(common),
            'mae_usd_billions': mae,
            'recent_20_mae_usd_billions': recent_mae,
            'max_abs_diff_usd_billions': max_abs,
            'runtime_last_official_scaled': off.get(runtime_last),
            'runtime_last_diff': (float(lane['last_value']) - off[runtime_last]) if runtime_last in off else None,
            'first_overlap': diffs[0],
            'last_overlap': diffs[-1],
            'recent_20': recent,
        },
        'interpretation': 'CURRENT_VINTAGE_REVISIONS_PRESENT' if exact != len(common) else 'EXACT_RUNTIME_MATCH',
        'automation_ready': False,
        'promotion_performed': False,
        'runtime_mutated': False,
        'publication_performed': False,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
