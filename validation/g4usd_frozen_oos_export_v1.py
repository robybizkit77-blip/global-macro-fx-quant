#!/usr/bin/env python3
"""Export frozen OOS observations from the exact PR122 implementation without changing its model."""
import argparse, importlib.util, json
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--model',required=True)
    for x in ['eur-rates','jpy-rates','cad-rates','aud-rates','usd-rates','usd-ecb','jpy-ecb','cad-ecb','aud-ecb']:
        ap.add_argument('--'+x,required=True)
    ap.add_argument('--output',required=True); a=ap.parse_args()
    spec=importlib.util.spec_from_file_location('m122',a.model); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    # Monkeypatch writer path by directly rebuilding rows through public helpers used by PR122.
    rates={c:m.load_rates(Path(getattr(a,f'{c.lower()}_rates'))) for c in ['EUR','JPY','CAD','AUD','USD']}
    fx=m.load_fx(Path(a.usd_ecb),Path(a.jpy_ecb),Path(a.cad_ecb),Path(a.aud_ecb))
    obs=[]
    for c in m.CCYS:
        rows=m.build_rows(c,rates,fx)
        feats=m.MODELS['PRIMARY_REL_2Y_REPRICE']
        labelled=[r for r in rows if r.get('target') is not None]
        for i in range(m.MIN_TRAIN,len(labelled)):
            train=labelled[:i]
            beta,mu,sd=m.fit([[r[k] for k in feats] for r in train],[r['target'] for r in train])
            r=labelled[i]; pred=m.predict(beta,mu,sd,[r[k] for k in feats])
            obs.append({'currency':c,'asof_date':r['asof'],'prediction':pred,'target_return':r['target'],
                        'strategy_return':(1 if pred>=0 else -1)*r['target'],'d_diff_2y':r['d_diff_2y']})
    out={'schema':'GMFQ_G4USD_RELATIVE_FRONT_END_PANEL_OOS_V1','frozen_from_pr':122,'baseline_panel_sharpe':0.301,'observations':obs}
    Path(a.output).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'n':len(obs),'baseline_panel_sharpe':0.301},indent=2))
if __name__=='__main__': main()
