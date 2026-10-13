#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path

LOOKUP_URL='https://www.bankofcanada.ca/rates/interest-rates/canadian-interest-rates/'
VALET_BASE='https://www.bankofcanada.ca/valet/observations'
RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
OUT=Path('validation/liquidity-cad-settlement-diagnostic.json')
UA='GMFQ-validation/1.0'


def fetch_text(url: str) -> str:
    req=urllib.request.Request(url,headers={'User-Agent':UA})
    with urllib.request.urlopen(req,timeout=60) as r:
        return r.read().decode('utf-8','replace')


def norm_date(v):
    if isinstance(v,(datetime,date)):
        return v.strftime('%Y-%m-%d')
    s=str(v).strip()
    for fmt in ('%Y-%m-%d','%Y-%m','%d %b %Y','%d %B %Y','%d/%m/%Y'):
        try:
            d=datetime.strptime(s,fmt)
            return d.strftime('%Y-%m-%d') if '%d' in fmt else d.strftime('%Y-%m')
        except ValueError:
            pass
    return None


def last_wednesday(year:int, month:int) -> str:
    d=date(year,month,monthrange(year,month)[1])
    while d.weekday()!=2:
        d-=timedelta(days=1)
    return d.isoformat()


def runtime_series():
    rt=json.loads(RUNTIME.read_text(encoding='utf-8'))
    row=rt['CAD']['liquidity']
    dates=list(row.get('dates') or [])
    values=list(row.get('values') or [])
    if not dates or len(dates)!=len(values):
        raise SystemExit('invalid CAD.liquidity runtime arrays')
    return row, [(str(d),float(v)) for d,v in zip(dates,values)]


def candidate_series_ids(page: str):
    # Bank lookup page embeds checkbox/radio inputs for the Lynx table. Inspect a bounded
    # block around the human label instead of guessing an ID.
    text=html.unescape(page)
    low=text.lower()
    pos=low.find('lynx settlement balances')
    if pos<0:
        raise SystemExit('Lynx settlement balances label not found on official BoC lookup page')
    block=text[max(0,pos-5000):pos+15000]
    ids=[]
    for m in re.finditer(r'value=["\'](V\d+)["\']',block,re.I):
        sid=m.group(1).upper()
        if sid not in ids:
            ids.append(sid)
    # Also accept names/ids containing a V-number.
    for m in re.finditer(r'\b(V\d{4,})\b',block,re.I):
        sid=m.group(1).upper()
        if sid not in ids:
            ids.append(sid)
    return ids, block


def valet_series(series_id: str):
    url=f'{VALET_BASE}/{urllib.parse.quote(series_id)}/json?start_date=2016-01-01'
    try:
        obj=json.loads(fetch_text(url))
    except Exception as exc:
        return None, str(exc)
    obs=obj.get('observations') or []
    out={}
    for row in obs:
        d=row.get('d')
        cell=row.get(series_id) or row.get(series_id.upper()) or row.get(series_id.lower())
        if not d or not isinstance(cell,dict):
            continue
        v=cell.get('v')
        if v in (None,''):
            continue
        try:
            out[d]=float(v)
        except (TypeError,ValueError):
            pass
    return out, None


def main():
    row, runtime=runtime_series()
    page=fetch_text(LOOKUP_URL)
    ids, block=candidate_series_ids(page)
    if not ids:
        raise SystemExit('no BoC V-series IDs discovered near Lynx settlement balances label')

    tests=[]
    best=None
    for sid in ids:
        official,err=valet_series(sid)
        if err or not official:
            tests.append({'series_id':sid,'transport_error':err,'official_count':0})
            continue
        matches=0
        overlap=0
        rows=[]
        for raw_d,rv in runtime:
            nd=norm_date(raw_d)
            if not nd:
                continue
            if len(nd)==7:
                y,m=map(int,nd.split('-'))
                key=last_wednesday(y,m)
            else:
                key=nd
            if key not in official:
                continue
            overlap+=1
            ov=official[key]
            ok=abs(rv-ov)<=1e-6
            matches+=int(ok)
            rows.append({'runtime_date':raw_d,'official_date':key,'runtime':rv,'official':ov,'exact':ok})
        ratio=(matches/overlap) if overlap else 0.0
        rec={'series_id':sid,'official_count':len(official),'overlap_count':overlap,'exact_match_count':matches,'exact_match_ratio':ratio,'sample':rows[-12:]}
        tests.append(rec)
        if best is None or (ratio,overlap)>(best['exact_match_ratio'],best['overlap_count']):
            best=rec

    if not best:
        raise SystemExit('no candidate BoC series returned observations')

    proven = best['overlap_count']>=12 and best['exact_match_ratio']>=0.95
    receipt={
        'schema':'GMFQ_LIQUIDITY_CAD_SETTLEMENT_DIAGNOSTIC_V1',
        'status':'EXACT_SERIES_AND_LAST_WEDNESDAY_RULE_PROVEN' if proven else 'WITHHELD_NO_EXACT_AGGREGATION_PROOF',
        'source':{
            'publisher':'Bank of Canada',
            'lookup_url':LOOKUP_URL,
            'series_family':'Lynx settlement balances — Actual',
            'monthly_rule_documented_by_boc':'last Wednesday of each month',
        },
        'runtime':{
            'last_date':row.get('last_date'),
            'last_value':row.get('last_value'),
            'count':len(runtime),
        },
        'discovered_series_ids':ids,
        'best_candidate':best,
        'all_candidates':tests,
        'automation_ready':False,
        'publication_performed':False,
        'runtime_mutated':False,
        'bias_score_sizing_effect':'NONE',
    }
    OUT.write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2,ensure_ascii=False))
    # Diagnostic is allowed to succeed when proof is insufficient: fail-closed state is the result.

if __name__=='__main__':
    main()
