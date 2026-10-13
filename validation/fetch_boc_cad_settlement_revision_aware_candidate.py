#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,urllib.request
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
DEFAULT_RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
URL='https://www.bankofcanada.ca/valet/observations/ACTUAL/json?start_date=2016-01-01'
SERIES='ACTUAL'

def month(v):
 s=str(v or '').strip()
 for fmt in ('%Y-%m','%Y-%m-%d','%d/%m/%Y'):
  try:return datetime.strptime(s,fmt).strftime('%Y-%m')
  except ValueError:pass
 raise SystemExit(f'invalid CAD.liquidity date {v!r}')

def fetch():
 req=urllib.request.Request(URL,headers={'User-Agent':'GMFQ-validation/1.0','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=90) as r: obj=json.load(r)
 rows=[]
 for x in obj.get('observations') or []:
  d=x.get('d'); cell=x.get(SERIES)
  if d and isinstance(cell,dict) and cell.get('v') not in (None,''):
   rows.append((d,float(cell['v'])))
 if not rows: raise SystemExit('BoC ACTUAL returned no observations')
 return sorted(rows)

def derive_completed_months(rows,asof_ym):
 by=defaultdict(list)
 for d,v in rows: by[d[:7]].append((d,v))
 out={}
 for m,vals in by.items():
  if m<asof_ym: out[m]=sorted(vals)[-1]
 return out

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--runtime',default=str(DEFAULT_RUNTIME)); ap.add_argument('--out',required=True); ap.add_argument('--as-of-month'); ap.add_argument('--recent-guard-months',type=int,default=12); a=ap.parse_args()
 if not 6 <= a.recent_guard_months <= 24: raise SystemExit('recent guard must be between 6 and 24 months')
 rp=Path(a.runtime); p=json.loads(rp.read_text()); lane=p['CAD']['liquidity']; dates=list(lane['dates']); vals=[float(x) for x in lane['values']]
 if not dates or len(dates)!=len(vals): raise SystemExit('invalid CAD.liquidity runtime')
 rt={month(d):v for d,v in zip(dates,vals)}; last=max(rt)
 asof=a.as_of_month or datetime.now(timezone.utc).strftime('%Y-%m')
 official=derive_completed_months(fetch(),asof)
 overlap=sorted(set(rt)&set(official)); recent=overlap[-a.recent_guard_months:]
 if len(recent)!=a.recent_guard_months: raise SystemExit(f'insufficient recent overlap: {len(recent)}')
 recent_exact=sum(abs(rt[m]-official[m][1])<=1e-9 for m in recent)
 if recent_exact!=a.recent_guard_months: raise SystemExit(f'CAD settlement recent guard failed: {recent_exact}/{a.recent_guard_months} exact')
 full_exact=sum(abs(rt[m]-official[m][1])<=1e-9 for m in overlap)
 new=[]
 for m in sorted(official):
  if m>last:
   d,v=official[m]; new.append({'month':m,'source_observation_date':d,'value':v})
 out={'schema':'GMFQ_LIQUIDITY_CAD_SETTLEMENT_REVISION_AWARE_CANDIDATE_V1','status':'GREEN_SOURCE_CANDIDATE_ONLY','source':{'publisher':'Bank of Canada','api':'Valet','series_id':SERIES,'series_label':'Lynx settlement balances - actual','url':URL,'frequency':'source observations; normalized monthly'},'normalization':{'rule':'LAST_AVAILABLE_OFFICIAL_OBSERVATION_IN_COMPLETED_CALENDAR_MONTH','as_of_month_excluded':asof,'historical_runtime_values_frozen':True,'revision_aware_append_only':True},'runtime':{'lane':'CAD.liquidity','count':len(dates),'last_month':last,'last_value':rt[last]},'proof':{'overlap_months':len(overlap),'full_history_exact_matches':full_exact,'full_history_mismatches':len(overlap)-full_exact,'recent_guard_months':a.recent_guard_months,'recent_guard_exact_matches':recent_exact,'recent_guard_pass':True},'candidate_update_available':bool(new),'new_observations':new,'official_latest_completed_month':max(official),'official_latest_completed_value':official[max(official)][1],'official_latest_completed_source_date':official[max(official)][0],'runtime_mutated':False,'publication_performed':False}
 Path(a.out).write_text(json.dumps(out,indent=2)+'\n'); print(json.dumps(out,indent=2))
if __name__=='__main__':main()
