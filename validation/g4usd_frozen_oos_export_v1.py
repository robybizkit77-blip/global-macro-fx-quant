#!/usr/bin/env python3
"""Export frozen PR #122 OOS observations without changing or refitting its specification."""
import argparse, importlib.util, json
from pathlib import Path


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--model',required=True)
    for x in ['eur-rates','jpy-rates','cad-rates','aud-rates','usd-rates','usd-ecb','jpy-ecb','cad-ecb','aud-ecb']:
        ap.add_argument('--'+x,required=True)
    ap.add_argument('--output',required=True); a=ap.parse_args()

    spec=importlib.util.spec_from_file_location('m122',a.model)
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

    rates={c:m.load_rates(Path(getattr(a,f'{c.lower()}_rates'))) for c in ['EUR','JPY','CAD','AUD','USD']}
    usd_fx=m.load_ecb(Path(a.usd_ecb))
    local_fx={
        'EUR':None,
        'JPY':m.load_ecb(Path(a.jpy_ecb)),
        'CAD':m.load_ecb(Path(a.cad_ecb)),
        'AUD':m.load_ecb(Path(a.aud_ecb)),
    }

    obs=[]
    currency_results={}
    for c in m.CCYS:
        result=m.build_currency(c,rates[c],rates['USD'],usd_fx,local_fx[c])
        currency_results[c]=result
        preds=result['models']['PRIMARY_REL_2Y_REPRICE']['predictions']

        # Reconstruct the same labelled feature rows solely to attach the contemporaneous
        # frozen d_diff_2y to each already-generated OOS prediction. No model refit here.
        raw=[]
        for dp in m.month_grid():
            lr=m.select_rate(rates[c],dp); ur=m.select_rate(rates['USD'],dp)
            if c=='EUR':
                fd=m.first_common_after(dp,usd_fx); px=usd_fx[fd]
            else:
                fd=m.first_common_after(dp,usd_fx,local_fx[c]); px=usd_fx[fd]/local_fx[c][fd]
            raw.append({'dp':dp,'price':px,'diff_2y':lr['y2']-ur['y2']})
        repriced=[]
        for i in range(1,len(raw)):
            r=dict(raw[i]); r['d_diff_2y']=r['diff_2y']-raw[i-1]['diff_2y']; repriced.append(r)
        labelled=[]
        for i in range(len(repriced)-1):
            r=dict(repriced[i]); labelled.append(r)
        by_dp={r['dp']:r for r in labelled}

        assert len(preds)==64
        for p in preds:
            dp=p['decision_point']; r=by_dp[dp]
            obs.append({
                'currency':c,
                'asof_date':dp,
                'prediction':p['prediction'],
                'target_return':p['actual'],
                'strategy_return':p['strategy'],
                'd_diff_2y':r['d_diff_2y'],
            })

    panel=m.panel_metrics(currency_results,'PRIMARY_REL_2Y_REPRICE')
    baseline=panel['equal_weight_monthly_annualized_sharpe']
    assert len(obs)==256
    assert abs(baseline-0.301)<0.002
    out={
        'schema':'GMFQ_G4USD_RELATIVE_FRONT_END_PANEL_OOS_V1',
        'frozen_from_pr':122,
        'frozen_head_sha':'0d9e2128680bddcb917767389cad97937b7c48f5',
        'baseline_panel_sharpe':baseline,
        'observations':obs,
    }
    Path(a.output).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'n':len(obs),'baseline_panel_sharpe':baseline},indent=2))

if __name__=='__main__': main()
