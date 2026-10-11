#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,math
from bisect import bisect_right
from datetime import date,datetime
from pathlib import Path
import eurusd_relative_rates_diagnostic_v1 as rr

SCHEMA='GMFQ_AUDUSD_FEATURE_RELIABILITY_GATE_V1'
RELIABILITY_WINDOW=36


def iso_date(s:str)->str:
 s=s.strip()
 for f in ('%Y-%m-%d','%d/%m/%Y','%d %B %Y','%d %b %Y'):
  try:return datetime.strptime(s,f).date().isoformat()
  except ValueError:pass
 raise ValueError(f'unrecognised release date {s!r}')

def load_inflation(path:Path):
 out=[]
 with path.open(newline='',encoding='utf-8-sig') as f:
  for r in csv.DictReader(f):out.append({'ref':r['reference_quarter'],'release':iso_date(r['release_date']),'value':float(r['cpi_yoy'])})
 if len(out)!=34:raise RuntimeError(f'unexpected AUD inflation rows {len(out)}')
 return out

def load_labour(path:Path):
 out=[]
 with path.open(newline='',encoding='utf-8-sig') as f:
  for r in csv.DictReader(f):out.append({'ref':r['reference_month'],'release':iso_date(r['release_date']),'value':float(r['unemployment_rate_sa'])})
 if len(out)!=104:raise RuntimeError(f'unexpected AUD labour rows {len(out)}')
 return out

def load_fx(path:Path):
 prices={}
 with path.open(newline='',encoding='utf-8-sig') as f:
  rd=csv.DictReader(f);fields=rd.fieldnames or []
  dk=next((k for k in ['TIME_PERIOD','TIME PERIOD','Date','DATE'] if k in fields),None);vk=next((k for k in ['OBS_VALUE','OBS VALUE','Value','VALUE'] if k in fields),None)
  if not dk or not vk:raise RuntimeError(f'ECB CSV columns not recognised: {fields}')
  for r in rd:
   ds=(r.get(dk) or '')[:10];vs=(r.get(vk) or '').strip()
   try:date.fromisoformat(ds);v=float(vs)
   except Exception:continue
   if v>0:prices[ds]=v
 return prices

def first_after(dp:str,common:list[str],px:dict[str,float]):
 i=bisect_right(common,dp)
 if i>=len(common):raise RuntimeError(f'no fixing after {dp}')
 d=common[i];return d,px[d]

def eligible_grid(inf,lab):
 out=[]
 for dp in rr.grid():
  if any(r['release']<dp for r in inf) and any(r['release']<dp for r in lab):out.append(dp)
 if out[0] != '2018-05-10':raise RuntimeError(f'unexpected first eligible AUD decision date {out[0]}')
 return out

def build_rows(inf,lab,aud,usd,aud_eur,usd_eur):
 common=sorted(set(aud_eur)&set(usd_eur));audusd={d:usd_eur[d]/aud_eur[d] for d in common};rows=[]
 for dp in eligible_grid(inf,lab):
  i=rr.latest_macro(inf,dp);l=rr.latest_macro(lab,dp);ar=rr.latest_rates(aud,dp);ur=rr.latest_rates(usd,dp);curve=(ar['y10']-ar['y2'])*100.0;fd,px=first_after(dp,common,audusd)
  rows.append({'decision_point':dp,'inflation':i['value'],'unemployment':l['value'],'aud_curve_bp':curve,'aud_y2':ar['y2'],'aud_y10':ar['y10'],'usd_y2':ur['y2'],'usd_y10':ur['y10'],'label_start_fixing_date':fd,'label_start_price':px})
 if len(rows)!=100:raise RuntimeError(f'unexpected eligible grid {len(rows)}')
 return rows

def label_rows(rows):
 out=[]
 for i in range(len(rows)-1):
  r=dict(rows[i]);r['forward_log_return']=math.log(rows[i+1]['label_start_price']/rows[i]['label_start_price']);out.append(r)
 return out

def expanding(labelled,features):
 out=[]
 for t in range(rr.MIN_TRAIN,len(labelled)):
  tr=labelled[:t];beta,mus,sds=rr.fit_ridge([[r[f] for f in features] for r in tr],[r['forward_log_return'] for r in tr]);row=labelled[t];p=rr.predict(beta,mus,sds,[row[f] for f in features]);a=row['forward_log_return'];s=1 if p>0 else(-1 if p<0 else 0)
  out.append({'decision_point':row['decision_point'],'prediction':p,'actual':a,'strategy':s*a})
 return out

def trailing_sharpe(xs):
 s=rr.stdev(xs)
 return None if s<=1e-12 else rr.mean(xs)/s*math.sqrt(12.0)

def gate(macro,curve):
 if len(macro)!=len(curve):raise RuntimeError('model prediction length mismatch')
 out=[];enabled=[]
 for j,(m,c) in enumerate(zip(macro,curve)):
  use=False;reason='FAIL_CLOSED_INSUFFICIENT_HISTORY'
  if j>=RELIABILITY_WINDOW:
   ms=[x['strategy'] for x in macro[j-RELIABILITY_WINDOW:j]];cs=[x['strategy'] for x in curve[j-RELIABILITY_WINDOW:j]]
   msh=trailing_sharpe(ms);csh=trailing_sharpe(cs);mret=math.exp(sum(ms))-1;c_ret=math.exp(sum(cs))-1
   use=(csh is not None and msh is not None and csh>msh and c_ret>mret);reason='CURVE_RELIABLE' if use else 'CURVE_NOT_RELIABLE'
  src=c if use else m
  out.append({'decision_point':src['decision_point'],'prediction':src['prediction'],'actual':src['actual'],'strategy':src['strategy'],'curve_enabled':use,'gate_reason':reason})
  if use:enabled.append(src['decision_point'])
 return out,enabled

def with_blocks(preds):
 return {'overall':rr.metrics(preds),'time_blocks':{name:rr.metrics([p for p in preds if lo<=p['decision_point']<=hi]) for name,lo,hi in rr.BLOCKS}}

def build(inf,lab,aud,usd,aud_eur,usd_eur):
 rows=build_rows(inf,lab,aud,usd,aud_eur,usd_eur);labelled=label_rows(rows)
 macro=expanding(labelled,['inflation','unemployment']);curve=expanding(labelled,['inflation','unemployment','aud_curve_bp']);gated,enabled=gate(macro,curve)
 models={'EXPANDING_MACRO_ONLY':with_blocks(macro),'EXPANDING_MACRO_PLUS_CURVE':with_blocks(curve),'PREDECLARED_CURVE_RELIABILITY_GATE_36':with_blocks(gated)}
 return {'schema':SCHEMA,'status':'UNTOUCHED_HOLDOUT_COMPLETE','scope':{'instrument':'AUDUSD','price_definition':'USD per AUD derived from ECB AUD/EUR and USD/EUR reference rates','first_eligible_decision_date':rows[0]['decision_point'],'snapshot_count':len(rows),'labelled_months':len(labelled),'oos_predictions_per_model':len(macro),'holdout_currency_not_used_to_define_gate':True,'two_early_grid_points_withheld_for_unavailable_strict_pit_cpi':True},'method':{'ridge_alpha_fixed':rr.ALPHA,'minimum_training_months':rr.MIN_TRAIN,'estimation':'expanding','reliability_window_months_fixed':RELIABILITY_WINDOW,'reliability_window_inherited_from_prior_regime_memory_work':True,'gate_defined_before_aud_results':True,'aud_parameter_tuning':False,'gate_rule':'Enable local curve model only when, over prior 36 realized OOS months, curve model has both higher annualized Sharpe and higher cumulative strategy return than Macro-only; otherwise fail closed to Macro-only.','gate_uses_current_or_future_outcome':False},'gate_telemetry':{'curve_enabled_months':len(enabled),'curve_disabled_months':len(gated)-len(enabled),'curve_enabled_fraction':len(enabled)/len(gated),'curve_enabled_dates':enabled},'models':models,'comparison':{'gate_minus_macro_sharpe':models['PREDECLARED_CURVE_RELIABILITY_GATE_36']['overall']['strategy_annualized_sharpe']-models['EXPANDING_MACRO_ONLY']['overall']['strategy_annualized_sharpe'],'gate_minus_macro_return':models['PREDECLARED_CURVE_RELIABILITY_GATE_36']['overall']['strategy_total_return']-models['EXPANDING_MACRO_ONLY']['overall']['strategy_total_return'],'gate_minus_curve_sharpe':models['PREDECLARED_CURVE_RELIABILITY_GATE_36']['overall']['strategy_annualized_sharpe']-models['EXPANDING_MACRO_PLUS_CURVE']['overall']['strategy_annualized_sharpe']},'policy':{'diagnostic_only':True,'production_signal_authorized':False,'position_sizing_authorized':False,'parameter_changes_from_aud_result_authorized':False}}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--inflation-csv',type=Path,required=True);ap.add_argument('--labour-csv',type=Path,required=True);ap.add_argument('--aud-rates',type=Path,required=True);ap.add_argument('--usd-rates',type=Path,required=True);ap.add_argument('--aud-ecb',type=Path,required=True);ap.add_argument('--usd-ecb',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 r=build(load_inflation(a.inflation_csv),load_labour(a.labour_csv),rr.load_rates(a.aud_rates),rr.load_rates(a.usd_rates),load_fx(a.aud_ecb),load_fx(a.usd_ecb));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print(json.dumps({'gate_telemetry':r['gate_telemetry'],'comparison':r['comparison'],'models':r['models']},indent=2,sort_keys=True))
if __name__=='__main__':main()
