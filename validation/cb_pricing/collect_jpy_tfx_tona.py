#!/usr/bin/env python3
"""Read-only collector for official TFX Three-month TONA Futures settlements."""
from __future__ import annotations
import argparse, csv, datetime as dt, io, json, pathlib, re
import requests

ROOT = pathlib.Path(__file__).resolve().parents[2]
OIS = ROOT / 'live_data' / 'sections' / 'OIS_DATA.json'
PAGE = 'https://www.tfx.co.jp/en/historical/futures/'
RESULT = 'https://www.tfx.co.jp/historical/futures/result'
PRODUCT = '無担保コールオーバーナイト３ヵ月金利先物'
MONTHS = {'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Jun':6,'Jul':7,'Aug':8,'Sep':9,'Oct':10,'Nov':11,'Dec':12}


def canonical_contracts():
    live=json.loads(OIS.read_text(encoding='utf-8'))['currencies']['JPY']
    meta=live.get('source_meta',{})
    structured=meta.get('contract_mapping')
    if isinstance(structured,dict) and all(structured.get(k) for k in ('3m','6m','12m')):
        return {k:str(structured[k]) for k in ('3m','6m','12m')}
    text=meta.get('horizon_mapping','')
    m=re.search(r'([A-Z][a-z]{2})-(\d{2})\s*/\s*([A-Z][a-z]{2})-(\d{2})\s*/\s*([A-Z][a-z]{2})-(\d{2})',text)
    if not m: raise SystemExit('Cannot parse canonical JPY horizon contract mapping')
    pairs=[(m.group(1),m.group(2)),(m.group(3),m.group(4)),(m.group(5),m.group(6))]
    out={}
    for horizon,(mon,yy) in zip(('3m','6m','12m'),pairs):
        if mon not in MONTHS: raise SystemExit(f'Unknown month {mon}')
        out[horizon]=f'{yy}.{MONTHS[mon]:02d}'
    return out


def fetch_rows(end: dt.date, days: int=20):
    start=end-dt.timedelta(days=days)
    params=[
      ('HistoricalFuturesData[submit_type]','csv'),('HistoricalFuturesData[period_start_type]','date'),
      ('HistoricalFuturesData[period_start][year]',str(start.year)),('HistoricalFuturesData[period_start][month]',str(start.month)),('HistoricalFuturesData[period_start][day]',str(start.day)),
      ('HistoricalFuturesData[period_end_type]','date'),('HistoricalFuturesData[period_end][year]',str(end.year)),('HistoricalFuturesData[period_end][month]',str(end.month)),('HistoricalFuturesData[period_end][day]',str(end.day)),
      ('HistoricalFuturesData[product_type1][]',PRODUCT),('HistoricalFuturesData[product_type2]','1'),
      ('HistoricalFuturesData[get_preference][]','day_settlement_price')]
    s=requests.Session(); headers={'User-Agent':'GLOBAL-MACRO-FX-QUANT validation'}
    s.get(PAGE,timeout=30,headers=headers).raise_for_status()
    r=s.get(RESULT,params=params,timeout=30,headers=headers); r.raise_for_status()
    if 'attachment' not in (r.headers.get('content-disposition') or '').lower(): raise SystemExit('TFX did not return CSV attachment')
    text=r.content.decode('shift_jis')
    lines=text.splitlines()
    header=next((i for i,x in enumerate(lines) if x.startswith('商品名,Product,限月,取引日,清算価格')),None)
    if header is None: raise SystemExit('TFX CSV settlement header not found')
    return list(csv.DictReader(io.StringIO('\n'.join(lines[header:])))), r.url


def build(as_of: dt.date|None):
    requested=as_of or dt.date.today()
    cmap=canonical_contracts(); rows,url=fetch_rows(requested)
    by_date={}
    for row in rows:
        if row.get('Product')!='Three-month TONA Futures': continue
        c=row.get('限月'); d=row.get('取引日'); p=row.get('清算価格')
        if c not in cmap.values() or not d or not p: continue
        try: rate=round(100.0-float(p),6)
        except ValueError: continue
        by_date.setdefault(d,{})[c]=rate
    complete=[]
    for ds,vals in by_date.items():
        if all(c in vals for c in cmap.values()): complete.append((dt.date.fromisoformat(ds),{h:vals[c] for h,c in cmap.items()}))
    complete.sort(key=lambda x:x[0])
    if as_of:
        matches=[x for x in complete if x[0]==as_of]
        if not matches: raise SystemExit(f'Requested as-of {as_of} has no complete canonical TFX settlement set')
        cur=matches[-1]
    else:
        eligible=[x for x in complete if x[0]<=requested]
        if not eligible: raise SystemExit('No complete TFX observations')
        cur=eligible[-1]
    earlier=[x for x in complete if x[0]<cur[0]]
    if not earlier: raise SystemExit('No prior official TFX session')
    prev=earlier[-1]
    weekly=[x for x in earlier if x[0] <= cur[0]-dt.timedelta(days=5)]
    if not weekly: raise SystemExit('No official weekly reference at least 5 calendar days before as-of')
    week=weekly[-1]
    def pack(x): return {'date':x[0].isoformat(),**x[1]}
    current,t1,t5=pack(cur),pack(prev),pack(week)
    d1={h:round((current[h]-t1[h])*100,4) for h in cmap}; dw={h:round((current[h]-t5[h])*100,4) for h in cmap}
    return {'schema':'GMFQ_CB_PRICING_SOURCE_SNAPSHOT_V1','currency':'JPY','status':'SOURCE_SNAPSHOT_ONLY','source':'Tokyo Financial Exchange · Three-month TONA Futures','source_url':PAGE,'request_url':url,'instrument':'Three-month TONA Futures','quotation':'100 minus compounded TONA','contract_mapping':cmap,'horizon_mapping':'Canonical direct TFX quarterly buckets from current runtime metadata; no interpolation','as_of':current['date'],'observations':{'current':current,'t_minus_1':t1,'weekly_reference':t5},'change_1d_bp':d1,'change_1w_bp':dw,'validation':{'official_source':True,'direct_settlements':True,'no_interpolation':True,'homogeneous_contracts':True,'runtime_mutated':False,'payload_mutated':False,'weekly_reference_rule':'nearest complete official session on or before as_of minus 5 calendar days'}}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--as-of'); ap.add_argument('--output',type=pathlib.Path); a=ap.parse_args(); out=build(dt.date.fromisoformat(a.as_of) if a.as_of else None); text=json.dumps(out,indent=2,ensure_ascii=False)+'\n'
    if a.output: a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(text,encoding='utf-8')
    print(text,end='')
if __name__=='__main__': main()
