#!/usr/bin/env python3
from __future__ import annotations
import argparse,datetime as dt,json,pathlib,re,requests
from bs4 import BeautifulSoup
ROOT=pathlib.Path(__file__).resolve().parents[2]; OIS=ROOT/'live_data'/'sections'/'OIS_DATA.json'; BASE='https://www.m-x.ca/en/trading/data/market-review'
DATE_RE=re.compile(r'([A-Z][a-z]+) (\d{1,2}), (20\d{2})')
def cmap():
 l=json.loads(OIS.read_text())['currencies']['CAD']; s=l.get('source_meta',{}).get('contract_mapping')
 if isinstance(s,dict) and all(s.get(k) for k in ('3m','6m','12m')): return {k:str(s[k]) for k in ('3m','6m','12m')}
 if 'Dec-26 / Mar-27 / Sep-27' not in l.get('source_meta',{}).get('horizon_mapping',''): raise SystemExit('bad CAD mapping')
 return {'3m':'DE 26','6m':'MR 27','12m':'SE 27'}
def parse(html):
 soup=BeautifulSoup(html,'html.parser')
 d=None
 for tag in soup.find_all(['h1','h2','h3','h4']):
  m=DATE_RE.fullmatch(tag.get_text(' ',strip=True))
  if m:
   d=dt.datetime.strptime(' '.join(m.groups()),'%B %d %Y').date(); break
 if d is None: raise SystemExit('Market Review heading date missing')
 lines=[x.strip() for x in soup.stripped_strings]
 try:start=next(i for i,x in enumerate(lines) if 'Three-Month CORRA Futures' in x)
 except StopIteration:raise SystemExit('CRA heading missing')
 end=len(lines)
 for i in range(start+1,len(lines)):
  if any(k in lines[i] for k in ('Two-Year Government of Canada Bond Futures','Five-Year Government of Canada Bond Futures')):
   end=i; break
 section=' '.join(lines[start:end])
 pat=re.compile(r'\b(MR|JN|SE|DE)\s+(\d{2})\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+([-0-9.]+)\s+([0-9,]+)\s+([0-9,]+)')
 out={}
 for m in pat.finditer(section):
  code=f'{m.group(1)} {m.group(2)}'; out[code]={'settlement':float(m.group(6)),'change':float(m.group(7)),'volume':int(m.group(8).replace(',','')),'open_interest':int(m.group(9).replace(',',''))}
 if not out: raise SystemExit('CRA rows missing')
 return d,out
def get(rid=None):
 r=requests.get(BASE,params={'id':rid} if rid is not None else None,headers={'User-Agent':'Mozilla/5.0 GMFQ validation'},timeout=30); r.raise_for_status(); d,c=parse(r.text); return d,c,r.url
def latest_id():
 target=get()[0]
 for rid in range(6192,6312):
  try:d,_,_=get(rid)
  except:continue
  if d==target:return rid
  if d>target:break
 raise SystemExit(f'latest review id not found for {target}')
def build(asof=None):
 cm=cmap(); lid=latest_id(); obs=[]; seen=set()
 for rid in range(lid,max(1,lid-40),-1):
  try:d,cs,url=get(rid)
  except:continue
  if d in seen or (asof and d>asof):continue
  seen.add(d)
  if not all(x in cs for x in cm.values()):continue
  rates={h:round(100-cs[x]['settlement'],6) for h,x in cm.items()}; obs.append((d,rates,rid,{h:cs[x] for h,x in cm.items()}))
 obs.sort(key=lambda x:x[0])
 if not obs: raise SystemExit('no complete CRA observations')
 matches=[x for x in obs if x[0]==asof] if asof else obs
 if not matches: raise SystemExit(f'no observation for {asof}')
 cur=matches[-1]; earlier=[x for x in obs if x[0]<cur[0]]
 if not earlier: raise SystemExit('no prior CRA session')
 prev=earlier[-1]; weekly=[x for x in earlier if x[0]<=cur[0]-dt.timedelta(days=5)]
 if not weekly: raise SystemExit('no weekly CRA reference')
 week=weekly[-1]
 def p(x):
  d,r,i,raw=x; return {'date':d.isoformat(),'market_review_id':i,**r,'raw':raw}
 a,b,w=p(cur),p(prev),p(week); d1={h:round((a[h]-b[h])*100,4) for h in cm}; dw={h:round((a[h]-w[h])*100,4) for h in cm}
 return {'schema':'GMFQ_CB_PRICING_SOURCE_SNAPSHOT_V1','currency':'CAD','status':'SOURCE_SNAPSHOT_ONLY','source':'Montréal Exchange public Market Review · Three-Month CORRA Futures (CRA)','source_url':BASE,'instrument':'Three-Month CORRA Futures (CRA)','quotation':'100 minus compounded CORRA','contract_mapping':cm,'as_of':a['date'],'observations':{'current':a,'t_minus_1':b,'weekly_reference':w},'change_1d_bp':d1,'change_1w_bp':dw,'validation':{'official_source':True,'direct_settlements':True,'no_interpolation':True,'homogeneous_contracts':True,'runtime_mutated':False,'payload_mutated':False,'weekly_reference_rule':'nearest complete official session on or before as_of minus 5 calendar days'}}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--as-of'); ap.add_argument('--output',type=pathlib.Path); a=ap.parse_args(); o=build(dt.date.fromisoformat(a.as_of) if a.as_of else None); t=json.dumps(o,indent=2,ensure_ascii=False)+'\n'
 if a.output:a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(t)
 print(t,end='')
if __name__=='__main__':main()
