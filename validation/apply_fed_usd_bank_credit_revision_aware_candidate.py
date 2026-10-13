#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from datetime import datetime
from pathlib import Path
DEFAULT_RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json'); SERIES='B1001NCBA'; TOL=1e-9

def day(v):
 s=str(v or '').strip()
 for fmt in ('%Y-%m-%d','%d/%m/%Y'):
  try:return datetime.strptime(s,fmt).strftime('%Y-%m-%d')
  except ValueError:pass
 raise SystemExit(f'invalid USD.credit date {v!r}')

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--candidate',required=True); ap.add_argument('--runtime',default=str(DEFAULT_RUNTIME)); ap.add_argument('--apply',action='store_true'); a=ap.parse_args()
 c=json.loads(Path(a.candidate).read_text()); rp=Path(a.runtime); p=json.loads(rp.read_text())
 if c.get('schema')!='GMFQ_LIQUIDITY_USD_BANK_CREDIT_REVISION_AWARE_CANDIDATE_V1' or c.get('status')!='GREEN_SOURCE_CANDIDATE_ONLY': raise SystemExit('invalid USD.credit candidate')
 if (c.get('source') or {}).get('series_id')!=SERIES: raise SystemExit('unexpected USD.credit series')
 pr=c.get('proof') or {}
 if pr.get('revision_aware_append_only') is not True or pr.get('historical_runtime_values_frozen') is not True or pr.get('new_observation_transform')!='SCALE_0.001': raise SystemExit('USD.credit safety contract missing')
 lane=p['USD']['credit']; od=list(lane['dates']); ov=list(lane['values']); dates=[day(x) for x in od]; vals=[float(x) for x in ov]
 cr=c.get('runtime') or {}
 if cr.get('lane')!='USD.credit' or day(cr.get('last_date'))!=dates[-1] or abs(float(cr.get('last_value'))-vals[-1])>TOL or int(cr.get('count',-1))!=len(dates): raise SystemExit('candidate built against different USD.credit runtime')
 new=[]; prev=dates[-1]
 for row in c.get('new_observations') or []:
  dt=day(row['date']); value=float(row['value'])
  if dt<=prev: raise SystemExit(f'non-forward USD.credit observation {dt} <= {prev}')
  if (datetime.strptime(dt,'%Y-%m-%d')-datetime.strptime(prev,'%Y-%m-%d')).days not in (7,14): raise SystemExit(f'non-contiguous weekly USD.credit step {prev} -> {dt}')
  new.append((dt,value)); prev=dt
 if bool(new)!=bool(c.get('candidate_update_available')): raise SystemExit('candidate update flag mismatch')
 u=json.loads(json.dumps(p)); target=u['USD']['credit']; orig_dates=list(target['dates']); orig_vals=list(target['values'])
 for dt,value in new: target['dates'].append(dt); target['values'].append(value)
 if new: target['last_date']=new[-1][0]; target['last_value']=new[-1][1]
 if target['dates'][:len(orig_dates)]!=orig_dates or target['values'][:len(orig_vals)]!=orig_vals: raise SystemExit('USD.credit historical rewrite attempted')
 changed=u!=p
 r={'schema':'GMFQ_LIQUIDITY_USD_BANK_CREDIT_REVISION_AWARE_APPLY_RECEIPT_V1','status':'UPDATE_AVAILABLE' if changed else 'NO_CHANGE','series_id':SERIES,'before_last_date':dates[-1],'before_last_value':vals[-1],'after_last_date':target.get('last_date'),'after_last_value':target.get('last_value'),'appended_observations':len(new),'applied':bool(a.apply and changed),'runtime_history_rewritten':False,'revision_aware_append_only':True,'publication_performed':False}
 if a.apply and changed: rp.write_text(json.dumps(u,separators=(',',':'))+'\n')
 print(json.dumps(r,indent=2,sort_keys=True))
if __name__=='__main__': main()
