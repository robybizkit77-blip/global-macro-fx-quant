#!/usr/bin/env python3
from __future__ import annotations
import csv, io, json, pathlib, re, sys, urllib.request
from datetime import datetime

ROOT=pathlib.Path(__file__).resolve().parents[1]
CURRENT=ROOT/'live_data'/'sections'/'NATIVE_RATES_DATA.json'
TREASURY_URL='https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/2026/all?_format=csv&field_tdr_date_value=2026&page=&type=daily_treasury_yield_curve'
MOF_URL='https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv'

UA='GMFQ-rates-adapter/1.0 (+https://github.com/robybizkit77-blip/global-macro-fx-quant)'

def fetch(url:str)->bytes:
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/csv,text/plain,*/*'})
    with urllib.request.urlopen(req,timeout=30) as r:
        b=r.read()
    if not b: raise RuntimeError('empty response: '+url)
    return b

def decode_csv(raw:bytes)->str:
    for enc in ('utf-8-sig','cp932','shift_jis','utf-8'):
        try: return raw.decode(enc)
        except UnicodeDecodeError: pass
    raise RuntimeError('unable to decode CSV')

def norm(s:str)->str:
    return re.sub(r'[^a-z0-9]','',str(s).lower())

def parse_date(s:str):
    s=str(s).strip()
    for fmt in ('%m/%d/%Y','%Y/%m/%d','%Y-%m-%d','%Y/%-m/%-d'):
        try: return datetime.strptime(s,fmt).date()
        except Exception: pass
    m=re.fullmatch(r'(\d{4})/(\d{1,2})/(\d{1,2})',s)
    if m:
        y,mo,d=map(int,m.groups()); return datetime(y,mo,d).date()
    raise ValueError('bad date '+s)

def find_col(headers:list[str], candidates:set[str])->int:
    nh=[norm(h) for h in headers]
    for i,h in enumerate(nh):
        if h in candidates: return i
    raise RuntimeError(f'column not found candidates={sorted(candidates)} headers={headers}')

def parse_treasury(raw:bytes)->dict:
    text=decode_csv(raw)
    rows=list(csv.reader(io.StringIO(text)))
    if not rows: raise RuntimeError('Treasury CSV empty')
    headers=rows[0]
    di=find_col(headers,{'date','recorddate'})
    i2=find_col(headers,{'2yr','2year','bc2year'})
    i10=find_col(headers,{'10yr','10year','bc10year'})
    vals=[]
    for r in rows[1:]:
        if len(r)<=max(di,i2,i10): continue
        try:
            dt=parse_date(r[di]); y2=float(r[i2]); y10=float(r[i10])
        except Exception: continue
        vals.append((dt,y2,y10))
    if not vals: raise RuntimeError('Treasury: no valid rows')
    dt,y2,y10=max(vals,key=lambda x:x[0])
    return {'date':dt.isoformat(),'2Y':y2,'10Y':y10,'source_url':TREASURY_URL,'authority':'U.S. Department of the Treasury'}

def locate_jgb_header(rows:list[list[str]])->tuple[int,int,int,int]:
    for ri,r in enumerate(rows[:20]):
        nr=[norm(x) for x in r]
        date_idx=next((i for i,x in enumerate(nr) if x in {'date','recorddate'}),None)
        if date_idx is None: continue
        two=next((i for i,x in enumerate(nr) if x in {'2y','2year','2years','2yr','2yrs'}),None)
        ten=next((i for i,x in enumerate(nr) if x in {'10y','10year','10years','10yr','10yrs'}),None)
        if two is not None and ten is not None: return ri,date_idx,two,ten
    # MOF historical/current CSVs have occasionally used Japanese/compact headers; accept maturity labels containing 2/10 + year.
    for ri,r in enumerate(rows[:20]):
        nr=[norm(x) for x in r]
        date_idx=next((i for i,x in enumerate(nr) if 'date' in x),None)
        two=next((i for i,x in enumerate(nr) if ('2' in x and ('year' in x or x.endswith('y')))),None)
        ten=next((i for i,x in enumerate(nr) if ('10' in x and ('year' in x or x.endswith('y')))),None)
        if date_idx is not None and two is not None and ten is not None: return ri,date_idx,two,ten
    raise RuntimeError('MOF: unable to identify Date/2Y/10Y header')

def parse_mof(raw:bytes)->dict:
    text=decode_csv(raw)
    rows=list(csv.reader(io.StringIO(text)))
    if not rows: raise RuntimeError('MOF CSV empty')
    hi,di,i2,i10=locate_jgb_header(rows)
    vals=[]
    for r in rows[hi+1:]:
        if len(r)<=max(di,i2,i10): continue
        try:
            dt=parse_date(r[di]); y2=float(r[i2]); y10=float(r[i10])
        except Exception: continue
        vals.append((dt,y2,y10))
    if not vals: raise RuntimeError('MOF: no valid rows')
    dt,y2,y10=max(vals,key=lambda x:x[0])
    return {'date':dt.isoformat(),'2Y':y2,'10Y':y10,'source_url':MOF_URL,'authority':'Japan Ministry of Finance'}

def cmp(cur:dict, src:dict)->dict:
    cd=cur.get('date'); sd=src['date']
    if sd<cd: state='SOURCE_OLDER_THAN_CURRENT'
    elif sd==cd and abs(float(cur['2Y'])-src['2Y'])<1e-9 and abs(float(cur['10Y'])-src['10Y'])<1e-9: state='NO_CHANGE'
    elif sd==cd: state='SAME_DATE_VALUE_MISMATCH'
    else: state='ADVANCE_AVAILABLE'
    return {'current':{'date':cd,'2Y':cur.get('2Y'),'10Y':cur.get('10Y')},'source':src,'state':state}

def main()->int:
    cur=json.loads(CURRENT.read_text())
    treasury=parse_treasury(fetch(TREASURY_URL))
    mof=parse_mof(fetch(MOF_URL))
    out={'schema':'GMFQ_RATES_SOURCE_PAIR_AUDIT_V1','status':'PASS','USD':cmp(cur['USD'],treasury),'JPY':cmp(cur['JPY'],mof)}
    # Fail closed on source regressions or same-date disagreements.
    bad=[c for c in ('USD','JPY') if out[c]['state'] in {'SOURCE_OLDER_THAN_CURRENT','SAME_DATE_VALUE_MISMATCH'}]
    if bad:
        out['status']='FAIL'; out['failures']=bad
        print(json.dumps(out,indent=2)); return 2
    print(json.dumps(out,indent=2)); return 0

if __name__=='__main__': sys.exit(main())
