#!/usr/bin/env python3
"""Read-only collector for official Montréal Exchange Three-Month CORRA Futures Market Review settlements."""
from __future__ import annotations
import argparse, datetime as dt, json, pathlib, re
import requests
from bs4 import BeautifulSoup

ROOT=pathlib.Path(__file__).resolve().parents[2]
OIS=ROOT/'live_data'/'sections'/'OIS_DATA.json'
BASE='https://www.m-x.ca/en/trading/data/market-review'

def canonical_contracts():
    live=json.loads(OIS.read_text(encoding='utf-8'))['currencies']['CAD']
    sm=live.get('source_meta',{})
    structured=sm.get('contract_mapping')
    if isinstance(structured,dict) and all(structured.get(k) for k in ('3m','6m','12m')):
        return {k:str(structured[k]) for k in ('3m','6m','12m')}
    text=sm.get('horizon_mapping','')
    if not re.search(r'Dec-26\s*/\s*Mar-27\s*/\s*Sep-27',text,re.I): raise SystemExit('Cannot parse canonical CAD contract mapping')
    return {'3m':'DE 26','6m':'MR 27','12m':'SE 27'}

def parse_page(html:str):
    soup=BeautifulSoup(html,'html.parser')
    full='\n'.join(soup.stripped_strings)
    dm=re.search(r'([A-Z][a-z]+)\s+(\d{1,2}),\s+(20\d{2})',full)
    if not dm: raise SystemExit('Market Review date not found')
    date=dt.datetime.strptime(' '.join(dm.groups()),'%B %d %Y').date()
    out={}
    for tr in soup.find_all('tr'):
        cells=[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'])]
        if not cells or not re.fullmatch(r'(MR|JN|SE|DE)\s+\d{2}',cells[0]): continue
        nums=[]
        for x in cells[1:]:
            try: nums.append(float(x.replace(',','')))
            except: pass
        if len(nums)>=4:
            out[cells[0]]={'settlement':nums[3],'change':nums[4] if len(nums)>4 else None,'volume':int(nums[5]) if len(nums)>5 else None,'open_interest':int(nums[6]) if len(nums)>6 else None}
    if not out:
        lines=[x.strip() for x in soup.stripped_strings]
        for i,x in enumerate(lines):
            if not re.fullmatch(r'(MR|JN|SE|DE)\s+\d{2}',x): continue
            vals=lines[i+1:i+8]; nums=[]
            for v in vals:
                try: nums.append(float(v.replace(',','')))
                except: pass
            if len(nums)>=4: out[x]={'settlement':nums[3],'change':nums[4] if len(nums)>4 else None,'volume':int(nums[5]) if len(nums)>5 else None,'open_interest':int(nums[6]) if len(nums)>6 else None}
    return date,out

def fetch_review(review_id:int|None=None):
    headers={'User-Agent':'Mozilla/5.0 GLOBAL-MACRO-FX-QUANT validation'}
    r=requests.get(BASE,params={'id':review_id} if review_id is not None else None,headers=headers,timeout=30)
    r.raise_for_status(); date,contracts=parse_page(r.text)
    return {'id':review_id,'date':date,'contracts':contracts,'url':r.url}

def discover_latest_id():
    target=fetch_review(None)['date']; seed=6192
    for rid in range(seed,seed+120):
        try: x=fetch_review(rid)
        except Exception: continue
        if x['date']==target: return rid
        if x['date']>target: break
    raise SystemExit(f'Could not map latest MX Market Review date {target} to id')

def build(as_of:dt.date|None):
    cmap=canonical_contracts(); latest_id=discover_latest_id(); obs=[]; seen=set()
    for rid in range(latest_id,max(1,latest_id-40),-1):
        try: x=fetch_review(rid)
        except Exception: continue
        d=x['date']
        if d in seen: continue
        seen.add(d)
        if as_of and d>as_of: continue
        cs=x['contracts']
        if not all(c in cs and cs[c].get('settlement') is not None for c in cmap.values()): continue
        rates={h:round(100.0-float(cs[c]['settlement']),6) for h,c in cmap.items()}
        obs.append((d,rates,rid,{h:cs[c] for h,c in cmap.items()}))
    obs.sort(key=lambda x:x[0])
    if not obs: raise SystemExit('No complete official MX CRA observations')
    if as_of:
        matches=[x for x in obs if x[0]==as_of]
        if not matches: raise SystemExit(f'Requested as-of {as_of} not found')
        cur=matches[-1]
    else: cur=obs[-1]
    earlier=[x for x in obs if x[0]<cur[0]]
    if not earlier: raise SystemExit('No prior official MX CRA session')
    prev=earlier[-1]; weekly=[x for x in earlier if x[0]<=cur[0]-dt.timedelta(days=5)]
    if not weekly: raise SystemExit('No official weekly reference')
    week=weekly[-1]
    def pack(x):
        d,r,rid,raw=x; return {'date':d.isoformat(),'market_review_id':rid,**r,'raw':raw}
    current,t1,t5=pack(cur),pack(prev),pack(week)
    d1={h:round((current[h]-t1[h])*100,4) for h in cmap}; dw={h:round((current[h]-t5[h])*100,4) for h in cmap}
    return {'schema':'GMFQ_CB_PRICING_SOURCE_SNAPSHOT_V1','currency':'CAD','status':'SOURCE_SNAPSHOT_ONLY','source':'Montréal Exchange public Market Review · Three-Month CORRA Futures (CRA)','source_url':BASE,'instrument':'Three-Month CORRA Futures (CRA)','quotation':'100 minus compounded CORRA','contract_mapping':cmap,'horizon_mapping':'Canonical direct MX quarterly settlement buckets; no interpolation','as_of':current['date'],'observations':{'current':current,'t_minus_1':t1,'weekly_reference':t5},'change_1d_bp':d1,'change_1w_bp':dw,'validation':{'official_source':True,'direct_settlements':True,'no_interpolation':True,'homogeneous_contracts':True,'runtime_mutated':False,'payload_mutated':False,'weekly_reference_rule':'nearest complete official session on or before as_of minus 5 calendar days'}}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--as-of'); ap.add_argument('--output',type=pathlib.Path); a=ap.parse_args(); out=build(dt.date.fromisoformat(a.as_of) if a.as_of else None); text=json.dumps(out,indent=2,ensure_ascii=False)+'\n'
    if a.output: a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(text,encoding='utf-8')
    print(text,end='')
if __name__=='__main__': main()
