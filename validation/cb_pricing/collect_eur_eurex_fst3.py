#!/usr/bin/env python3
"""Read-only collector for official Eurex Three-Month Euro STR Futures settlements."""
from __future__ import annotations
import argparse, datetime as dt, json, pathlib, urllib.error, urllib.request

BASE='https://www.eurex.com/api/v1/overallstatistics/3402482'
PAGE='https://www.eurex.com/ex-en/markets/int/mon/3m-euro-str-futures/estr/Three-Month-Euro-STR-Futures-3402480'
PRODUCT='FST3'; ISIN='DE000A3CNW06'
CONTRACTS={'3m':'20261216','6m':'20270317','12m':'20270915'}


def fetch(day: dt.date):
    url=f'{BASE}?busdate={day:%Y%m%d}&filtertype=overview'
    req=urllib.request.Request(url,headers={'User-Agent':'GLOBAL-MACRO-FX-QUANT validation','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            payload=json.loads(r.read().decode('utf-8'))
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise ValueError(f'no valid Eurex JSON for {day}: {exc}') from exc
    meta=payload.get('meta') or {}
    if meta.get('productCode')!=PRODUCT or meta.get('isin')!=ISIN or meta.get('productType')!='F':
        raise ValueError(f'unexpected Eurex metadata for {day}: {meta}')
    rows={str(x.get('date')):x for x in payload.get('dataRows') or []}
    out={}
    for h,expiry in CONTRACTS.items():
        row=rows.get(expiry)
        if not row or row.get('dSettle') is None:
            raise ValueError(f'missing FST3 settlement {h}/{expiry} for {day}')
        out[h]=round(100.0-float(row['dSettle']),6)
    return out,url


def find_valid_session(start: dt.date, stop_before: dt.date | None = None, max_lookback: int = 14):
    """Walk backward and accept only a real Eurex busDate that returns valid FST3 settlements."""
    for offset in range(max_lookback+1):
        day=start-dt.timedelta(days=offset)
        if stop_before is not None and day>=stop_before:
            continue
        try:
            vals,url=fetch(day)
            return day,vals,url
        except ValueError:
            continue
    raise SystemExit(f'no valid Eurex FST3 session found from {start} within {max_lookback} days')


def build(as_of: dt.date):
    current,url=fetch(as_of)
    prev_date,prev,prev_url=find_valid_session(as_of-dt.timedelta(days=1), max_lookback=10)
    weekly_cutoff=as_of-dt.timedelta(days=5)
    week_date,week,week_url=find_valid_session(weekly_cutoff, max_lookback=10)
    if not prev_date<as_of: raise SystemExit('previous session is not strictly before as-of')
    if not week_date<=weekly_cutoff: raise SystemExit('weekly reference violates cutoff')
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
      'validation':{
        'official_source':True,'direct_settlements':True,'no_interpolation':True,'homogeneous_contracts':True,
        'current_real':True,'previous_real':True,'week_real':True,
        'runtime_mutated':False,'payload_mutated':False,
        'weekly_reference_rule':'nearest valid official Eurex busDate on or before as_of minus 5 calendar days'
      },
      'provenance':{
        'current_request_url':url,'previous_request_url':prev_url,'weekly_request_url':week_url,
        'product_id':'3402482','product_code':PRODUCT,'isin':ISIN,
        'session_discovery':'backward busDate probe; accept only valid FST3 JSON with identical mapped contracts and non-null dSettle'
      }
    }


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--as-of',required=True); ap.add_argument('--output',type=pathlib.Path); a=ap.parse_args()
    out=build(dt.date.fromisoformat(a.as_of)); text=json.dumps(out,indent=2,ensure_ascii=False)+'\n'
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(text,encoding='utf-8')
    print(text,end='')
if __name__=='__main__': main()
