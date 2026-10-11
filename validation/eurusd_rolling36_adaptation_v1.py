#!/usr/bin/env python3
"""Exploratory EURUSD adaptation test: expanding vs fixed rolling-36 ridge.

The 36-month window is not tuned: it equals the pre-existing minimum training
history used throughout the diagnostic stack. This test is nevertheless post-hoc
because it is motivated by the observed 2025 curve regime break, so any positive
result remains a candidate requiring independent validation.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
import eurusd_relative_rates_diagnostic_v1 as rr

SCHEMA='GMFQ_EURUSD_ROLLING36_ADAPTATION_DIAGNOSTIC_V1'
WINDOW=36
MODELS={
 'EXPANDING_MACRO_ONLY':(['inflation','unemployment'],'expanding'),
 'ROLLING36_MACRO_ONLY':(['inflation','unemployment'],'rolling36'),
 'EXPANDING_MACRO_PLUS_CURVE':(['inflation','unemployment','eur_curve_bp'],'expanding'),
 'ROLLING36_MACRO_PLUS_CURVE':(['inflation','unemployment','eur_curve_bp'],'rolling36'),
}

def run(labelled:list[dict[str,Any]], features:list[str], mode:str):
 out=[]
 for t in range(rr.MIN_TRAIN,len(labelled)):
  train=labelled[:t] if mode=='expanding' else labelled[t-WINDOW:t]
  xtr=[[r[f] for f in features] for r in train]; ytr=[r['forward_log_return'] for r in train]
  beta,mus,sds=rr.fit_ridge(xtr,ytr)
  row=labelled[t]; p=rr.predict(beta,mus,sds,[row[f] for f in features]); a=row['forward_log_return']; s=1 if p>0 else (-1 if p<0 else 0)
  out.append({'decision_point':row['decision_point'],'prediction':p,'actual':a,'signal':s,'strategy':s*a,'curve_beta':beta[-1] if 'eur_curve_bp' in features else None})
 return out

def build(inf,lab,eur,usd,dates,prices):
 rows=rr.build_rows(inf,lab,eur,usd,dates,prices); labelled=rr.label_rows(rows); models={}
 for name,(features,mode) in MODELS.items():
  preds=run(labelled,features,mode); blocks={}
  for label,lo,hi in rr.BLOCKS: blocks[label]=rr.metrics([p for p in preds if lo<=p['decision_point']<=hi])
  betas=[p['curve_beta'] for p in preds if p['curve_beta'] is not None]
  models[name]={'features':features,'estimation':mode,'overall':rr.metrics(preds),'time_blocks':blocks,'curve_beta_path':betas if betas else None}
 key='2025_to_2026-07'; e=models['EXPANDING_MACRO_PLUS_CURVE']['time_blocks'][key]; r=models['ROLLING36_MACRO_PLUS_CURVE']['time_blocks'][key]
 return {
  'schema':SCHEMA,'status':'DIAGNOSTIC_COMPLETE',
  'scope':{'instrument':'EURUSD','snapshot_count':len(rows),'labelled_months':len(labelled),'oos_predictions_per_model':models['EXPANDING_MACRO_ONLY']['overall']['observations'],'usd_macro_leg_present':False},
  'method':{'rolling_window_months_fixed':WINDOW,'rolling_window_reason':'equals pre-existing minimum training history; not optimized','ridge_alpha_fixed':rr.ALPHA,'minimum_training_months':rr.MIN_TRAIN,'hyperparameter_tuning':False,'window_search':False,'post_hoc_architecture_test':True,'independent_validation_required':True},
  'models':models,
  'comparison_2025_to_2026_07':{'rolling_curve_minus_expanding_curve_sharpe':r['strategy_annualized_sharpe']-e['strategy_annualized_sharpe'],'rolling_curve_minus_expanding_curve_total_return':r['strategy_total_return']-e['strategy_total_return'],'rolling_curve_minus_expanding_curve_hit_rate':r['directional_accuracy']-e['directional_accuracy']},
  'policy':{'diagnostic_only':True,'production_backtest_authorized':False,'production_signal_authorized':False,'position_sizing_authorized':False,'parameter_changes_from_results_authorized':False}
 }

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--inflation',type=Path,required=True); ap.add_argument('--labour',type=Path,required=True); ap.add_argument('--eur-rates',type=Path,required=True); ap.add_argument('--usd-rates',type=Path,required=True); ap.add_argument('--ecb',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args()
 inf=rr.load_macro(a.inflation,'headline_hicp_yoy_pct'); lab=rr.load_macro(a.labour,'unemployment_rate_pct'); eur=rr.load_rates(a.eur_rates); usd=rr.load_rates(a.usd_rates); dates,prices=rr.load_prices(a.ecb)
 res=build(inf,lab,eur,usd,dates,prices); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(res,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps({'comparison':res['comparison_2025_to_2026_07'],'models':res['models']},indent=2,sort_keys=True)); return 0
if __name__=='__main__': raise SystemExit(main())
