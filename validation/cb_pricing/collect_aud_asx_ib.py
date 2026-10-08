#!/usr/bin/env python3
from __future__ import annotations
import argparse,datetime as dt,json,pathlib,re,requests
from bs4 import BeautifulSoup
ROOT=pathlib.Path(__file__).resolve().parents[2]
OIS=ROOT/'live_data'/'sections'/'OIS_DATA.json'
BASE='https://www.asx.com.au/data/futures/reports/EODWebMarketSummary{date}SFN.htm'
MAP={'3m':'Dec 2026','6m':'Mar 2027','12m':'Sep 2027'}
DATE_RE=re.compile(r'close of trade date\s+(\d{2}/\d{2}/\d{2})',re.I)
def parse(html):
 soup=BeautifulSoup(html,'html.parser')
 txt=soup.get_text(' ',strip=True)
 m=DATE_RE.search(txt)
 if not m: raise SystemExit('ASX trade date missing')
 d=dt.datetime.strptime(m.group(1),'%d/%m/%y').date()
 table=None
 for t in soup.find_all('table'):
  z=t.get_text(' ',strip=True)
  if 'IB - 30 Day Interbank Cash Rate' in z:
   table=t; break
 if table is None: raise SystemExit('ASX IB table missing')
 out={}
 for tr in table.find_all('tr'):
  cells=[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'])]
  if len(cells)<6: continue
  expiry=cells[0]
  if expiry not in MAP.values(): continue
  try: sett=float(cells[5].replace(',',''))
  except ValueError: continue
  out[expiry]={'settlement':sett,'settlement_change':cells[6] if len(cells)>6 else None,'raw_cells':cells}
 if not all(x in out for x in MAP.values()): raise SystemExit(f'ASX IB target rows missing: {out.keys()}')
 return d,out
def get(day):
 url=BASE.format(date=day.strftime('%y%m%d'))
 r=requests.get(url,headers={'User-Agent':'Mozilla/5.0 GMFQ validation'},timeout=30)
 r.raise_for_status(); d,rows=parse(r.text)
 if d!=day: raise SystemExit(f'ASX date mismatch requested={day} parsed={d}')
 return d,rows,url
def latest():
 today=dt.datetime.now(dt.timezone.utc).date()
 for i in range(0,14):
  day=today-dt.timedelta(days=i)
  if day.weekday()>=5: continue
  try:return get(day)
  except Exception: continue
 raise SystemExit('no recent ASX SFN report found')
def build(asof=None):
 cur=get(asof) if asof else latest()
 obs=[]
 for i in range(1,12):
  day=cur[0]-dt.timedelta(days=i)
  if day.weekday()>=5: continue
  try: obs.append(get(day))
  except Exception: continue
 prev=obs[0] if obs else None
 if prev is None: raise SystemExit('no prior ASX session')
 target=cur[0]-dt.timedelta(days=7)
 week=min(obs,key=lambda x:(abs((x[0]-target).days),0 if x[0]<=target else 1,-x[0].toordinal()))
 def pack(x):
  d,rows,url=x
  rates={h:round(100-rows[e]['settlement'],6) for h,e in MAP.items()}
  return {'date':d.isoformat(),'url':url,**rates,'raw':{h:rows[e] for h,e in MAP.items()}}
 a,b,w=pack(cur),pack(prev),pack(week)
 d1={h:round((a[h]-b[h])*100,4) for h in MAP}; dw={h:round((a[h]-w[h])*100,4) for h in MAP}
 return {'schema':'GMFQ_CB_PRICING_SOURCE_SNAPSHOT_V1','currency':'AUD','status':'SOURCE_SNAPSHOT_ONLY','source':'ASX Futures End of Day Data · 30 Day Interbank Cash Rate futures (IB)','source_url':cur[2],'instrument':'ASX 30 Day Interbank Cash Rate futures (IB)','quotation':'100 minus implied average monthly interbank overnight cash rate','contract_mapping':MAP,'as_of':a['date'],'observations':{'current':a,'t_minus_1':b,'weekly_reference':w},'change_1d_bp':d1,'change_1w_bp':dw,'validation':{'official_source':True,'direct_settlements':True,'no_interpolation':True,'homogeneous_contracts':True,'runtime_mutated':False,'payload_mutated':False,'weekly_reference_rule':'complete official ASX SFN session nearest to as_of minus 7 calendar days; ties prefer on/before target'}}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--as-of'); ap.add_argument('--output',type=pathlib.Path); a=ap.parse_args()
 o=build(dt.date.fromisoformat(a.as_of) if a.as_of else None); t=json.dumps(o,indent=2,ensure_ascii=False)+'\n'
 if a.output: a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(t)
 print(t,end='')
if __name__=='__main__': main()
