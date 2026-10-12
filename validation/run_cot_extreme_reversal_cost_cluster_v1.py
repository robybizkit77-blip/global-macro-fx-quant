#!/usr/bin/env python3
from __future__ import annotations

import json, pathlib
from collections import defaultdict

import run_cot_extreme_reversal_one_shot_v1 as base
import run_cot_extreme_reversal_robustness_v1 as robust

CONTRACT = pathlib.Path('validation/COT_EXTREME_REVERSAL_COST_CLUSTER_CONTRACT_V1_2026-10-12.json')
OUTDIR = pathlib.Path('/tmp/cot-extreme-reversal-cost-cluster-v1')


def weekly_panel(rows, return_field='observation_return'):
    wk = defaultdict(list)
    for r in rows:
        iso = r['entry_date'].isocalendar()
        wk[(iso.year, iso.week)].append(r[return_field])
    vals = [sum(wk[k]) / len(wk[k]) for k in sorted(wk)]
    return vals


def collapse_episodes(rows):
    out=[]
    by_ccy=defaultdict(list)
    for r in rows:
        by_ccy[r['currency']].append(r)
    for ccy, xs in by_ccy.items():
        xs=sorted(xs,key=lambda r:(r['report_date'],r['entry_date']))
        prev=None
        for r in xs:
            keep=False
            if prev is None:
                keep=True
            else:
                same_direction=(r['signal']==prev['signal'])
                gap=(r['report_date']-prev['report_date']).days
                if (not same_direction) or gap>14:
                    keep=True
            if keep:
                out.append(r)
            prev=r
    return sorted(out,key=lambda r:(r['entry_date'],r['currency']))


def main():
    contract=json.loads(CONTRACT.read_text())
    assert contract['status']=='PREDECLARED_BEFORE_COST_CLUSTER_RESULTS'
    currencies,oos=robust.build_frozen_oos()
    pooled=[r for c in currencies for r in oos[c]]
    raw=weekly_panel(pooled)
    raw_sharpe=base.sample_sharpe(raw)

    cost_results={}
    for bps in contract['stress_tests']['transaction_costs']['round_trip_bps']:
        cost=bps/10000.0
        net=[]
        for r in pooled:
            x=dict(r)
            x['net_return']=r['observation_return']-cost
            net.append(x)
        vals=weekly_panel(net,'net_return')
        cost_results[str(bps)]={
            'weekly_n':len(vals),
            'panel_sharpe':base.sample_sharpe(vals),
            'panel_total_log_return':sum(vals)
        }

    episodes=collapse_episodes(pooled)
    ep_vals=weekly_panel(episodes)
    ep_sharpe=base.sample_sharpe(ep_vals)

    gates={
        'net_5bps_panel_sharpe_ge_0_50': cost_results['5']['panel_sharpe'] is not None and cost_results['5']['panel_sharpe']>=0.50,
        'net_10bps_panel_sharpe_gt_0': cost_results['10']['panel_sharpe'] is not None and cost_results['10']['panel_sharpe']>0.0,
        'episode_panel_sharpe_ge_0_50': ep_sharpe is not None and ep_sharpe>=0.50,
        'minimum_episode_observations_ge_100': len(episodes)>=100,
    }
    result={
        'schema':'GMFQ_COT_EXTREME_REVERSAL_COST_CLUSTER_RESULT_V1',
        'verdict':'PASS_PREDECLARED_COST_CLUSTER_GATE' if all(gates.values()) else 'FAIL_PREDECLARED_COST_CLUSTER_GATE',
        'replication':{'pooled_n':len(pooled),'weekly_n':len(raw),'panel_sharpe':raw_sharpe},
        'transaction_costs':cost_results,
        'episodes':{'observations':len(episodes),'weekly_n':len(ep_vals),'panel_sharpe':ep_sharpe,'panel_total_log_return':sum(ep_vals)},
        'gates':gates,
        'governance':{'candidate_rule_changed':False,'forward_shadow_changed':False,'production_signal_authorized':False,'sizing_authorized':False}
    }
    OUTDIR.mkdir(parents=True,exist_ok=True)
    (OUTDIR/'result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
