#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from datetime import datetime
from pathlib import Path
DEFAULT_RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json'); SERIES='ACTUAL'; TOL=1e-9

def month(v):
 s=str(v or '').strip()
 for fmt in ('%Y-%m','%Y-%m-%d'):
  try:return datetime.strptime(s,fmt).strftime('%Y-%m')
  except ValueError:pass
 raise SystemExit(f'invalid CAD.liquidity date {v!r}')

def next_month(m):
 d=datetime.strptime(m,'%Y-%m'); y=d.year+(1 if d.month==12 else 0); mm=1 if d.month==12 else d.month+1; return f'{y:04d}-{mm:02d}'

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--candidate',required=True); ap.add_argument('--runtime',default=str(DEFAULT_RUNTIME)); ap.add_argument('--apply',action='store_true'); a=ap.parse_args()
 c=json.loads(Path(a.candidate).read_text()); rp=Path(a.runtime); p=json.loads(rp.read_text())
 if c.get('schema')!='GMFQ_LIQUIDITY_CAD_SETTLEMENT_REVISION_AWARE_CANDIDATE_V1' or c.get('status')!='GREEN_SOURCE_CANDIDATE_ONLY': raise SystemExit('invalid CAD settlement candidate')
 if (c.get('source') or {}).get('series_id')!=SERIES: raise SystemExit('unexpected CAD settlement series')
 nrm=c.get('normalization') or {}; pr=c.get('proof') or {}
 if nrm.get('rule')!='LAST_AVAILABLE_OFFICIAL_OBSERVATION_IN_COMPLETED_CALENDAR_MONTH' or nrm.get('historical_runtime_values_frozen') is not True or nrm.get('revision_aware_append_only') is not True or pr.get('recent_guard_pass') is not True or pr.get('recent_guard_exact_matches')!=12: raise SystemExit('CAD settlement safety contract missing')
 lane=p['CAD']['liquidity']; od=list(lane['dates']); ov=list(lane['values']); months=[month(x) for x in od]; vals=[float(x) for x in ov]
 cr=c.get('runtime') or {}
 if cr.get('lane')!='CAD.liquidity' or month(cr.get('last_month'))!=months[-1] or abs(float(cr.get('last_value'))-vals[-1])>TOL or int(cr.get('count',-1))!=len(months): raise SystemExit('candidate built against different CAD.liquidity runtime')
 new=[]; prev=months[-1]
 for row in c.get('new_observations') or []:
  m=month(row['month']); v=float(row['value']); sd=str(row['source_observation_date'])
  if m!=next_month(prev): raise SystemExit(f'non-contiguous CAD settlement month {prev} -> {m}')
  if not sd.startswith(m+'-'): raise SystemExit(f'source observation date outside target month {sd} vs {m}')
  new.append((m,v)); prev=m
 if bool(new)!=bool(c.get('candidate_update_available')): raise SystemExit('candidate update flag mismatch')
 u=json.loads(json.dumps(p)); target=u['CAD']['liquidity']; orig_dates=list(target['dates']); orig_vals=list(target['values'])
 for m,v in new: target['dates'].append(m); target['values'].append(v)
 if new: target['last_date']=new[-1][0]; target['last_value']=new[-1][1]
 if target['dates'][:len(orig_dates)]!=orig_dates or target['values'][:len(orig_vals)]!=orig_vals: raise SystemExit('CAD settlement historical rewrite attempted')
 changed=u!=p
 r={'schema':'GMFQ_LIQUIDITY_CAD_SETTLEMENT_REVISION_AWARE_APPLY_RECEIPT_V1','status':'UPDATE_AVAILABLE' if changed else 'NO_CHANGE','series_id':SERIES,'before_last_month':months[-1],'before_last_value':vals[-1],'after_last_month':target.get('last_date'),'after_last_value':target.get('last_value'),'appended_observations':len(new),'applied':bool(a.apply and changed),'runtime_history_rewritten':False,'revision_aware_append_only':True,'publication_performed':False}
 if a.apply and changed: rp.write_text(json.dumps(u,separators=(',',':'))+'\n')
 print(json.dumps(r,indent=2,sort_keys=True))
if __name__=='__main__':main()
