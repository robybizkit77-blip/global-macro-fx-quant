#!/usr/bin/env python3
import csv
import io
import json
import urllib.parse
import urllib.request
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
        if not ids: continue
        parts.append(f"{d['id']}({','.join(ids)})")
    return ','.join(parts)


def parse_wide(text):
    try:dialect=csv.Sniffer().sniff(text[:8192],delimiters=';,\t')
    except csv.Error:
        dialect=csv.excel; dialect.delimiter=';'
    rows=list(csv.reader(io.StringIO(text),dialect=dialect))
    if not rows: raise SystemExit('empty credit CSV')
    width=max(len(r) for r in rows)
    rows=[r+['']*(width-len(r)) for r in rows]
    data_start=next((i for i,r in enumerate(rows) if norm_month(r[0])),None)
    if data_start is None: raise SystemExit(f'no dated rows. preview={rows[:12]!r}')
    headers=[]
    for col in range(1,width):
        desc=[]
        for r in range(data_start):
            label=str(rows[r][0]).strip()
            val=str(rows[r][col]).strip()
            if val: desc.append((label,val))
        key=next((v for _,v in desc if '@SNB.' in v or ('{' in v and '}' in v)),None)
        headers.append((col,key or f'column_{col}',desc))
    series={}
    meta={}
    for col,key,desc in headers:
        vals={}
        for r in rows[data_start:]:
            m=norm_month(r[0])
            if not m: continue
            raw=str(r[col]).strip().replace("'",'').replace(' ','')
            if not raw: continue
            if raw.count(',')==1 and '.' not in raw: raw=raw.replace(',','.')
            try: vals[m]=float(raw)
            except ValueError: continue
        if vals:
            series[key]=vals
            meta[key]=desc
    return series,meta


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
    series,meta=parse_wide(text)
    rt=runtime_credit()
    ranked=[]
    for key,vals in series.items():
        cmp=compare(rt,vals)
        if not cmp['overlap']:continue
        last=max(rt)
        ranked.append({'series_key':key,'metadata':meta[key],**cmp,'runtime_last':rt[last],'official_raw_on_runtime_last':vals.get(last),'official_latest_date':max(vals),'official_latest_raw':vals[max(vals)]})
    ranked.sort(key=lambda x:(x['rounded_1dp_exact'],x['exact'],x['overlap'],-x['mae']),reverse=True)
    out={'schema':'GMFQ_SNB_CHF_DIMENSIONS_CREDIT_GRID_PROBE_V1','warehouse_dimensions':warehouse_dims,'credit_dimsel':dimsel,'credit_series_count':len(series),'credit_ranked':ranked[:30]}
    print(json.dumps(out,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
