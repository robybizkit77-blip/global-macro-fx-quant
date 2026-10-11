#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,math
from bisect import bisect_right
from datetime import date
from pathlib import Path
import eurusd_relative_rates_diagnostic_v1 as rr

SCHEMA='GMFQ_CADUSD_ROLLING36_INDEPENDENT_VALIDATION_V1'
WINDOW=36
MODELS={
 'EXPANDING_MACRO_ONLY':(['inflation','unemployment'],'expanding'),
 'ROLLING36_MACRO_ONLY':(['inflation','unemployment'],'rolling36'),
 'EXPANDING_MACRO_PLUS_CURVE':(['inflation','unemployment','cad_curve_bp'],'expanding'),
 'ROLLING36_MACRO_PLUS_CURVE':(['inflation','unemployment','cad_curve_bp'],'rolling36'),
}

def load_inflation_csv(path:Path):
 out=[]
 with path.open(newline='',encoding='utf-8-sig') as f:
  for r in csv.DictReader(f): out.append({'ref':r['reference_month'],'release':r['release_date'],'value':float(r['cpi_yoy_full_precision'])})
 if len(out)!=104: raise RuntimeError(f'unexpected inflation rows {len(out)}')
 return out

def load_labour_csv(path:Path):
 out=[]
 with path.open(newline='',encoding='utf-8-sig') as f:
  for r in csv.DictReader(f): out.append({'ref':r['reference_month'],'release':r['release_date'],'value':float(r['unemployment_rate_sa'])})
 if len(out)!=104: raise RuntimeError(f'unexpected labour rows {len(out)}')
 return out

def load_fx(path:Path):
 prices={}
 with path.open(newline='',encoding='utf-8-sig') as f:
  rd=csv.DictReader(f); fields=rd.fieldnames or []
  dk=next((k for k in ['TIME_PERIOD','TIME PERIOD','Date','DATE'] if k in fields),None); vk=next((k for k in ['OBS_VALUE','OBS VALUE','Value','VALUE'] if k in fields),None)
  if not dk or not vk: raise RuntimeError(f'ECB CSV columns not recognised: {fields}')
  for r in rd:
   ds=(r.get(dk) or '')[:10]; vs=(r.get(vk) or '').strip()
   try: date.fromisoformat(ds); v=float(vs)
   except Exception: continue
   if v>0: prices[ds]=v
 return prices

def first_after(dp:str, common:list[str], px:dict[str,float]):
 i=bisect_right(common,dp)
 if i>=len(common): raise RuntimeError(f'no fixing after {dp}')
 d=common[i]; return d,px[d]

def build_rows(inf,lab,cad,usd,cad_eur,usd_eur):
 common=sorted(set(cad_eur)&set(usd_eur)); cadusd={d:usd_eur[d]/cad_eur[d] for d in common}
 rows=[]
 for dp in rr.grid():
  i=rr.latest_macro(inf,dp); l=rr.latest_macro(lab,dp); cr=rr.latest_rates(cad,dp); ur=rr.latest_rates(usd,dp)
  curve=(cr['y10']-cr['y2'])*100.0; fd,px=first_after(dp,common,cadusd)
  rows.append({'decision_point':dp,'inflation':i['value'],'unemployment':l['value'],'cad_y2':cr['y2'],'cad_y10':cr['y10'],'cad_curve_bp':curve,'usd_y2':ur['y2'],'usd_y10':ur['y10'],'label_start_fixing_date':fd,'label_start_price':px})
 if len(rows)!=102: raise RuntimeError(f'unexpected grid size {len(rows)}')
 return rows

def label_rows(rows):
 out=[]
 for i in range(len(rows)-1):
  r=dict(rows[i]); r['forward_log_return']=math.log(rows[i+1]['label_start_price']/rows[i]['label_start_price']); out.append(r)
 return out

def run(labelled,features,mode):
 out=[]
 for t in range(rr.MIN_TRAIN,len(labelled)):
  train=labelled[:t] if mode=='expanding' else labelled[t-WINDOW:t]
  xtr=[[r[f] for f in features] for r in train]; ytr=[r['forward_log_return'] for r in train]
  beta,mus,sds=rr.fit_ridge(xtr,ytr); row=labelled[t]; p=rr.predict(beta,mus,sds,[row[f] for f in features]); a=row['forward_log_return']; s=1 if p>0 else (-1 if p<0 else 0)
  out.append({'decision_point':row['decision_point'],'prediction':p,'actual':a,'strategy':s*a,'curve_beta':beta[-1] if 'cad_curve_bp' in features else None})
 return out

def build(inf,lab,cad,usd,cad_eur,usd_eur):
 rows=build_rows(inf,lab,cad,usd,cad_eur,usd_eur); labelled=label_rows(rows); models={}
 for name,(features,mode) in MODELS.items():
  preds=run(labelled,features,mode); blocks={}
  for label,lo,hi in rr.BLOCKS: blocks[label]=rr.metrics([p for p in preds if lo<=p['decision_point']<=hi])
  betas=[p['curve_beta'] for p in preds if p['curve_beta'] is not None]
  models[name]={'features':features,'estimation':mode,'overall':rr.metrics(preds),'time_blocks':blocks,'curve_beta_path':betas if betas else None}
 return {'schema':SCHEMA,'status':'INDEPENDENT_VALIDATION_COMPLETE','scope':{'instrument':'CADUSD','price_definition':'USD per CAD derived from ECB CAD/EUR and USD/EUR reference rates','snapshot_count':len(rows),'labelled_months':len(labelled),'oos_predictions_per_model':models['EXPANDING_MACRO_ONLY']['overall']['observations'],'independent_currency_from_discovery_sample':True},'method':{'rolling_window_months_fixed':36,'window_inherited_from_eurusd_discovery':True,'window_search_on_cad':False,'ridge_alpha_fixed':rr.ALPHA,'minimum_training_months':rr.MIN_TRAIN,'hyperparameter_tuning_on_cad':False,'same_architecture_as_eurusd_and_jpyusd_tests':True},'models':models,'comparison':{'rolling_curve_minus_expanding_curve_overall_sharpe':models['ROLLING36_MACRO_PLUS_CURVE']['overall']['strategy_annualized_sharpe']-models['EXPANDING_MACRO_PLUS_CURVE']['overall']['strategy_annualized_sharpe'],'rolling_curve_minus_expanding_curve_overall_return':models['ROLLING36_MACRO_PLUS_CURVE']['overall']['strategy_total_return']-models['EXPANDING_MACRO_PLUS_CURVE']['overall']['strategy_total_return']},'policy':{'diagnostic_only':True,'production_signal_authorized':False,'position_sizing_authorized':False,'parameter_changes_from_cad_result_authorized':False}}

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--inflation-csv',type=Path,required=True); ap.add_argument('--labour-csv',type=Path,required=True); ap.add_argument('--cad-rates',type=Path,required=True); ap.add_argument('--usd-rates',type=Path,required=True); ap.add_argument('--cad-ecb',type=Path,required=True); ap.add_argument('--usd-ecb',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args()
 res=build(load_inflation_csv(a.inflation_csv),load_labour_csv(a.labour_csv),rr.load_rates(a.cad_rates),rr.load_rates(a.usd_rates),load_fx(a.cad_ecb),load_fx(a.usd_ecb)); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(res,indent=2,sort_keys=True)+'\n'); print(json.dumps({'comparison':res['comparison'],'models':res['models']},indent=2,sort_keys=True)); return 0
if __name__=='__main__': raise SystemExit(main())
