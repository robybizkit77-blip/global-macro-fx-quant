#!/usr/bin/env python3
"""Read-only collector for official Eurex Three-Month Euro STR Futures settlements."""
from __future__ import annotations
import argparse, datetime as dt, json, pathlib, urllib.request

BASE='https://www.eurex.com/api/v1/overallstatistics/3402482'
PAGE='https://www.eurex.com/ex-en/markets/int/mon/3m-euro-str-futures/estr/Three-Month-Euro-STR-Futures-3402480'
PRODUCT='FST3'; ISIN='DE000A3CNW06'
CONTRACTS={'3m':'20261216','6m':'20270317','12m':'20270915'}


def fetch(day: dt.date):
    url=f'{BASE}?busdate={day:%Y%m%d}&filtertype=overview'
    req=urllib.request.Request(url,headers={'User-Agent':'GLOBAL-MACRO-FX-QUANT validation','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as r: payload=json.loads(r.read().decode('utf-8'))
    meta=payload.get('meta') or {}
    if meta.get('productCode')!=PRODUCT or meta.get('isin')!=ISIN or meta.get('productType')!='F': raise SystemExit(f'unexpected Eurex metadata for {day}: {meta}')
    rows={str(x.get('date')):x for x in payload.get('dataRows') or []}
    out={}
    for h,expiry in CONTRACTS.items():
        row=rows.get(expiry)
        if not row or row.get('dSettle') is None: raise SystemExit(f'missing FST3 settlement {h}/{expiry} for {day}')
        out[h]=round(100.0-float(row['dSettle']),6)
    trading=[]
    for raw in (payload.get('header') or {}).get('tradingDates') or []:
        try: trading.append(dt.datetime.strptime(raw,'%d-%m-%Y').date())
        except Exception: pass
    return out, sorted(set(trading), reverse=True), url


def build(as_of: dt.date):
    current,trading,url=fetch(as_of)
    eligible=[d for d in trading if d<as_of]
    if not eligible: raise SystemExit('no previous official Eurex trading date')
    prev_date=max(eligible)
    weekly_dates=[d for d in eligible if d<=as_of-dt.timedelta(days=5)]
    if not weekly_dates: raise SystemExit('no official weekly reference at least 5 calendar days before as-of')
    week_date=max(weekly_dates)
    prev,_,prev_url=fetch(prev_date); week,_,week_url=fetch(week_date)
    def pack(day,vals): return {'date':day.isoformat(),**vals}
    cur=pack(as_of,current); t1=pack(prev_date,prev); t5=pack(week_date,week)
    d1={h:round((current[h]-prev[h])*100,4) for h in CONTRACTS}
    dw={h:round((current[h]-week[h])*100,4) for h in CONTRACTS}
    return {
      'schema':'GMFQ_CB_PRICING_SOURCE_SNAPSHOT_V1','currency':'EUR','status':'SOURCE_SNAPSHOT_ONLY',
      'source':'Eurex · Three-Month Euro STR Futures (FST3)','source_url':PAGE,'instrument':'Three-Month Euro STR Futures (FST3)',
      'quotation':'100 minus implied compounded Euro STR','contract_mapping':CONTRACTS,
      'horizon_mapping':'Dec-26 / Mar-27 / Sep-27 direct Eurex quarterly settlement buckets; no interpolation',
      'as_of':as_of.isoformat(),'observations':{'current':cur,'t_minus_1':t1,'weekly_reference':t5},
      'change_1d_bp':d1,'change_1w_bp':dw,
      'validation':{'official_source':True,'direct_settlements':True,'no_interpolation':True,'homogeneous_contracts':True,'runtime_mutated':False,'payload_mutated':False,'weekly_reference_rule':'nearest official Eurex trading session on or before as_of minus 5 calendar days'},
      'provenance':{'current_request_url':url,'previous_request_url':prev_url,'weekly_request_url':week_url,'product_id':'3402482','product_code':PRODUCT,'isin':ISIN}
    }


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--as-of',required=True); ap.add_argument('--output',type=pathlib.Path); a=ap.parse_args()
    out=build(dt.date.fromisoformat(a.as_of)); text=json.dumps(out,indent=2,ensure_ascii=False)+'\n'
    if a.output: a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(text,encoding='utf-8')
    print(text,end='')
if __name__=='__main__': main()
