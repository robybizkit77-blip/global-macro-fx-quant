#!/usr/bin/env python3
from __future__ import annotations

import json, math, pathlib, statistics
from collections import defaultdict
from datetime import date

import run_cot_extreme_reversal_one_shot_v1 as base

ROBUST_PATH = pathlib.Path('validation/COT_EXTREME_REVERSAL_ROBUSTNESS_CONTRACT_V1_2026-10-12.json')
EDGE_PATH = pathlib.Path('validation/COT_EXTREME_REVERSAL_EDGE_CONTRACT_V1_2026-10-12.json')
PIT_PATH = pathlib.Path('validation/COT_ULTRACONSERVATIVE_PIT_POLICY_V1_2026-10-11.json')
PRICE_PATH = pathlib.Path('validation/COT_FLOW_FX_PRICE_SOURCE_CONTRACT_V1_2026-10-11.json')
OUTDIR = pathlib.Path('/tmp/cot-extreme-reversal-robustness-v1')


def weekly_panel(rows):
    wk = defaultdict(list)
    for r in rows:
        iso = r['entry_date'].isocalendar()
        wk[(iso.year, iso.week)].append(r['observation_return'])
    keys = sorted(wk)
    vals = [sum(wk[k]) / len(wk[k]) for k in keys]
    return keys, vals


def newey_west_tstat(xs, lag=4):
    n = len(xs)
    if n < lag + 3:
        return None
    mu = statistics.mean(xs)
    u = [x - mu for x in xs]
    gamma0 = sum(v*v for v in u) / n
    long_var = gamma0
    for L in range(1, lag + 1):
        cov = sum(u[t] * u[t-L] for t in range(L, n)) / n
        w = 1.0 - L / (lag + 1.0)
        long_var += 2.0 * w * cov
    if long_var <= 0:
        return None
    se_mean = math.sqrt(long_var / n)
    return mu / se_mean if se_mean > 0 else None


def build_frozen_oos():
    edge = json.loads(EDGE_PATH.read_text())
    policy = json.loads(PIT_PATH.read_text())
    price_contract = json.loads(PRICE_PATH.read_text())
    assert edge['status'] == 'PREDECLARED_NO_RESULTS_OBSERVED'
    assert policy['status'] == 'PREDECLARED_NO_EDGE_RESULTS_OBSERVED'
    assert price_contract['status'] == 'PREDECLARED_NO_COT_EDGE_RESULTS_OBSERVED'
    currencies = edge['universe']['currencies']
    positions = base.load_cot_positions(currencies)
    pit_map = base.build_pit_map([r['report_date'] for r in positions[currencies[0]]])
    prices = base.load_fx_prices(price_contract)
    observations = {c: [] for c in currencies}
    for ccy in currencies:
        rows = positions[ccy]
        for i in range(103, len(rows)):
            cur = rows[i]
            pcur = pit_map[cur['report_date']]
            if not pcur['research_pit_eligible']:
                continue
            lookback = rows[i-103:i+1]
            if any(not pit_map[r['report_date']]['research_pit_eligible'] for r in lookback):
                continue
            pct = base.percentile_midrank([r['net_oi'] for r in lookback], cur['net_oi'])
            if pct >= 80:
                signal = -1
            elif pct <= 20:
                signal = 1
            else:
                continue
            available = date.fromisoformat(pcur['research_available_from'])
            px = prices[ccy]
            idx = base.first_index_on_or_after(px, available)
            if idx is None or idx + 5 >= len(px):
                continue
            entry_d, entry_p = px[idx]
            exit_d, exit_p = px[idx+5]
            raw = math.log(exit_p / entry_p)
            observations[ccy].append({
                'currency': ccy,
                'report_date': cur['report_date'],
                'entry_date': entry_d,
                'exit_date': exit_d,
                'percentile': pct,
                'signal': signal,
                'observation_return': signal * raw,
            })
    oos = {}
    for ccy in currencies:
        rows = sorted(observations[ccy], key=lambda r: (r['entry_date'], r['report_date']))
        cut = math.floor(0.60 * len(rows))
        oos[ccy] = rows[cut:]
    return currencies, oos


def main():
    contract = json.loads(ROBUST_PATH.read_text())
    assert contract['status'] == 'PREDECLARED_BEFORE_ROBUSTNESS_RESULTS'
    currencies, oos = build_frozen_oos()
    pooled = [r for c in currencies for r in oos[c]]
    keys, vals = weekly_panel(pooled)
    full_sharpe = base.sample_sharpe(vals)

    loo = {}
    for omit in currencies:
        rows = [r for c in currencies if c != omit for r in oos[c]]
        _, xs = weekly_panel(rows)
        loo[omit] = {'weekly_n': len(xs), 'panel_sharpe': base.sample_sharpe(xs)}
    min_loo = min(v['panel_sharpe'] for v in loo.values() if v['panel_sharpe'] is not None)

    mid = len(vals) // 2
    first = vals[:mid]
    second = vals[mid:]
    halves = {
        'first': {'weekly_n': len(first), 'panel_sharpe': base.sample_sharpe(first)},
        'second': {'weekly_n': len(second), 'panel_sharpe': base.sample_sharpe(second)},
    }
    nw_t = newey_west_tstat(vals, lag=4)

    gates = {
        'leave_one_currency_out_min_sharpe_ge_0_50': min_loo >= 0.50,
        'both_chronological_half_sharpes_positive': halves['first']['panel_sharpe'] > 0 and halves['second']['panel_sharpe'] > 0,
        'newey_west_lag4_tstat_ge_1_96': nw_t is not None and nw_t >= 1.96,
    }
    result = {
        'schema': 'GMFQ_COT_EXTREME_REVERSAL_ROBUSTNESS_RESULT_V1',
        'verdict': 'PASS_PREDECLARED_ROBUSTNESS_GATE' if all(gates.values()) else 'FAIL_PREDECLARED_ROBUSTNESS_GATE',
        'frozen_oos': {'pooled_n': len(pooled), 'weekly_n': len(vals), 'panel_sharpe': full_sharpe},
        'leave_one_currency_out': loo,
        'min_leave_one_out_sharpe': min_loo,
        'chronological_halves': halves,
        'newey_west_lag4_tstat': nw_t,
        'gates': gates,
        'governance': {
            'candidate_rule_changed': False,
            'forward_shadow_changed': False,
            'production_signal_authorized': False,
            'sizing_authorized': False,
        },
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / 'result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
