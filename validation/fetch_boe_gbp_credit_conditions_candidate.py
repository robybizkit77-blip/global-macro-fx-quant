#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from diagnose_boe_gbp_credit_conditions_v1 import fetch_bytes, parse_xlsx, norm, build_quarters, TARGET, URL

RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')


def next_quarter(q):
    y, n = q.split('-Q')
    y, n = int(y), int(n)
    return f'{y+1}-Q1' if n == 4 else f'{y}-Q{n+1}'


def collect():
    runtime = json.loads(RUNTIME.read_text(encoding='utf-8'))['GBP']['conditions']
    book = parse_xlsx(fetch_bytes())
    hits = []
    for sheet, rows in book.items():
        for idx, vals in rows:
            joined = ' | '.join(str(v) for _, v in sorted(vals.items()))
            if TARGET in norm(joined) and 'past three months' in norm(joined):
                q_by_col, header_rows = build_quarters(rows, idx)
                obs = []
                for col, val in sorted(vals.items()):
                    if col not in q_by_col:
                        continue
                    try:
                        num = float(val)
                    except (TypeError, ValueError):
                        continue
                    obs.append({'date': q_by_col[col], 'value': num})
                hits.append({'sheet': sheet, 'row': idx, 'header_rows': header_rows, 'observations': obs})

    if len(hits) != 1:
        raise SystemExit(f'expected exactly one BoE corporate availability row, found {len(hits)}')
    source = hits[0]
    observations = source['observations']
    rmap = {d: float(v) for d, v in zip(runtime['dates'], runtime['values'])}
    smap = {x['date']: float(x['value']) for x in observations}
    overlap = sorted(set(rmap) & set(smap))
    exact = sum(abs(rmap[d] - smap[d]) < 1e-9 for d in overlap)
    if len(overlap) != len(runtime['dates']) or exact != len(runtime['dates']):
        raise SystemExit(f'current BoE vintage does not reproduce full runtime: overlap={len(overlap)} exact={exact} runtime={len(runtime["dates"])}')

    last = runtime['dates'][-1]
    new = [x for x in observations if x['date'] > last]
    expected = next_quarter(last)
    for row in new:
        if row['date'] != expected:
            raise SystemExit(f'non-contiguous new quarter: expected {expected}, got {row["date"]}')
        expected = next_quarter(expected)

    return {
        'schema': 'GMFQ_LIQUIDITY_GBP_CCS_CONDITIONS_CANDIDATE_V1',
        'source': {
            'publisher': 'Bank of England',
            'release': '2026 Q3',
            'url': URL,
            'sheet': source['sheet'],
            'row': source['row'],
            'target_question': 'How has the availability of credit provided to the corporate sector overall changed?',
            'response_horizon': 'Past three months',
            'frequency': 'QUARTERLY',
        },
        'runtime': {
            'lane': 'GBP.conditions',
            'count': len(runtime['dates']),
            'last_date': last,
            'last_value': runtime['values'][-1],
        },
        'proof': {
            'candidate_row_count': 1,
            'source_observation_count': len(observations),
            'overlap_count': len(overlap),
            'exact_match_count': exact,
            'exact_match_ratio': exact / len(overlap),
            'runtime_history_unchanged_by_current_vintage': True,
            'identity_transform': True,
        },
        'latest_date': observations[-1]['date'],
        'latest_value': observations[-1]['value'],
        'new_observations': new,
        'candidate_update_available': bool(new),
        'automation_candidate_ready': True,
        'runtime_mutated': False,
        'publication_performed': False,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out')
    args = ap.parse_args()
    data = collect()
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text + '\n', encoding='utf-8')
    else:
        print(text)


if __name__ == '__main__':
    main()
