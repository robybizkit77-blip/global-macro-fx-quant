#!/usr/bin/env python3
import csv
import io
import json
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')
WAREHOUSE_CUBE = 'BSTA.SNB.MONA_U.BIL.AKT.FMI.GGU'
WAREHOUSE_DIMS = f'https://data.snb.ch/api/warehouse/cube/{WAREHOUSE_CUBE}/dimensions/en'
CREDIT_DIMS = 'https://data.snb.ch/api/cube/bakredinausbm/dimensions/en'
CREDIT_DATA = 'https://data.snb.ch/api/cube/bakredinausbm/data/csv/en'


def fetch(url, accept='application/json'):
    req=urllib.request.Request(url,headers={'User-Agent':'GMFQ-validation/1.0','Accept':accept})
    with urllib.request.urlopen(req,timeout=90) as r:
        return r.read().decode('utf-8-sig')


def norm_month(v):
    s=str(v or '').strip()
    for fmt in ('%Y-%m','%Y-%m-%d','%d.%m.%Y','%d/%m/%Y'):
        try:return datetime.strptime(s,fmt).strftime('%Y-%m')
        except ValueError:pass
    return None


def runtime_credit():
    d=json.loads(RUNTIME.read_text(encoding='utf-8'))['CHF']['credit']
    return {norm_month(x):float(v) for x,v in zip(d['dates'],d['values'])}


def flatten_ids(items):
    out=[]
    for x in items or []:
        xid=x.get('id')
        if xid: out.append(str(xid))
        out.extend(flatten_ids(x.get('dimensionItems')))
    return out


def build_dimsel(dims):
    parts=[]
    for d in dims:
        ids=flatten_ids(d.get('dimensionItems'))
        if ids:
            parts.append(f"{d['id']}({','.join(ids)})")
    return ','.join(parts)


def sniff_dict_rows(text):
    try:dialect=csv.Sniffer().sniff(text[:8192],delimiters=';,\t')
    except csv.Error:
        dialect=csv.excel; dialect.delimiter=';'
    rows=list(csv.DictReader(io.StringIO(text),dialect=dialect))
    if not rows: raise SystemExit('empty credit CSV')
    return rows,list(rows[0].keys())


def parse_credit_long(text):
    rows,fields=sniff_dict_rows(text)
    low={str(f).lower().strip():f for f in fields}
    date_col=next((f for f in fields if str(f).lower().strip() in {'date','datum','period'}),None)
    value_col=next((f for f in fields if str(f).lower().strip() in {'value','wert','val'}),None)
    if not date_col or not value_col:
        raise SystemExit(f'credit CSV missing date/value columns: {fields}')
    dim_cols=[f for f in fields if f not in {date_col,value_col}]
    grouped=defaultdict(dict)
    meta={}
    for row in rows:
        m=norm_month(row.get(date_col))
        raw=str(row.get(value_col) or '').strip().replace("'",'').replace(' ','')
        if not m or not raw: continue
        if raw.count(',')==1 and '.' not in raw:raw=raw.replace(',','.')
        try:value=float(raw)
        except ValueError:continue
        dims=tuple(str(row.get(c) or '').strip() for c in dim_cols)
        key='|'.join(f'{c}={v}' for c,v in zip(dim_cols,dims))
        grouped[key][m]=value
        meta[key]={c:v for c,v in zip(dim_cols,dims)}
    return grouped,meta,fields


def compare(rt,official):
    common=sorted(set(rt)&set(official))
    best=None
    for scale in (1,1e-3,1e3,1e-6,1e6):
        exact=sum(abs(rt[m]-official[m]*scale)<=1e-9 for m in common)
        round1=sum(abs(rt[m]-round(official[m]*scale,1))<=1e-9 for m in common)
        mae=sum(abs(rt[m]-official[m]*scale) for m in common)/len(common) if common else 1e99
        row={'scale':scale,'overlap':len(common),'exact':exact,'rounded_1dp_exact':round1,'mae':mae}
        score=(round1,exact,-mae)
        if best is None or score>best[0]:best=(score,row)
    return best[1]


def main():
    warehouse_dims=json.loads(fetch(WAREHOUSE_DIMS))
    credit_dims=json.loads(fetch(CREDIT_DIMS))
    dims=credit_dims.get('dimensions') or []
    dimsel=build_dimsel(dims)
    url=CREDIT_DATA+'?'+urllib.parse.urlencode({'dimSel':dimsel,'fromDate':'2025-07','toDate':'2026-07'},safe='(),')
    text=fetch(url,'text/csv')
    series,meta,fields=parse_credit_long(text)
    rt=runtime_credit()
    ranked=[]
    for key,vals in series.items():
        cmp=compare(rt,vals)
        if not cmp['overlap']:continue
        last=max(rt)
        ranked.append({'series_key':key,'metadata':meta[key],**cmp,'runtime_last':rt[last],'official_raw_on_runtime_last':vals.get(last),'official_latest_date':max(vals),'official_latest_raw':vals[max(vals)]})
    ranked.sort(key=lambda x:(x['rounded_1dp_exact'],x['exact'],x['overlap'],-x['mae']),reverse=True)
    out={'schema':'GMFQ_SNB_CHF_DIMENSIONS_CREDIT_GRID_PROBE_V1','warehouse_dimensions':warehouse_dims,'credit_dimsel':dimsel,'credit_fields':fields,'credit_series_count':len(series),'credit_ranked':ranked[:30]}
    print(json.dumps(out,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
