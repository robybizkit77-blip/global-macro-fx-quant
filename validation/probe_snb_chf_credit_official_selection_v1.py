#!/usr/bin/env python3
import csv
import io
import json
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
BASE='https://data.snb.ch/api/cube/bakredinausbm/data/csv/en'
DIMENSIONS='https://data.snb.ch/api/cube/bakredinausbm/dimensions/en'


def fetch(url,accept='text/csv'):
    req=urllib.request.Request(url,headers={'User-Agent':'GMFQ-validation/1.0','Accept':accept})
    with urllib.request.urlopen(req,timeout=90) as r:return r.read().decode('utf-8-sig')

def month(v):
    s=str(v or '').strip()
    for fmt in ('%Y-%m','%Y-%m-%d','%d.%m.%Y'):
        try:return datetime.strptime(s,fmt).strftime('%Y-%m')
        except ValueError:pass
    return None

def runtime():
    d=json.loads(RUNTIME.read_text(encoding='utf-8'))['CHF']['credit']
    return {month(x):float(v) for x,v in zip(d['dates'],d['values'])}

def parse(text):
    if not text.strip():return []
    try:dialect=csv.Sniffer().sniff(text[:8192],delimiters=';,\t')
    except csv.Error:
        dialect=csv.excel; dialect.delimiter=';'
    rows=list(csv.reader(io.StringIO(text),dialect=dialect))
    if not rows:return []
    width=max(len(r) for r in rows); rows=[r+['']*(width-len(r)) for r in rows]
    header_idx=next((i for i,r in enumerate(rows) if [str(x).strip() for x in r[:6]]==['Date','D0','D1','D2','D3','Value']),None)
    if header_idx is None:return []
    grouped=defaultdict(dict)
    for r in rows[header_idx+1:]:
        m=month(r[0])
        if not m:continue
        dims=tuple(str(x).strip() for x in r[1:5])
        raw=str(r[5]).strip().replace("'",'').replace(' ','')
        if not raw:continue
        if raw.count(',')==1 and '.' not in raw:raw=raw.replace(',','.')
        try:v=float(raw)
        except ValueError:continue
        grouped[dims][m]=v
    return [{'dimensions':{'D0':d[0],'D1':d[1],'D2':d[2],'D3':d[3]},'values':vals} for d,vals in grouped.items()]

def d0_items(dimensions):
    for d in dimensions.get('dimensions',[]):
        if d.get('id')=='D0':return [(x['id'],x.get('name')) for x in d.get('dimensionItems',[])]
    raise SystemExit('SNB dimensions metadata missing D0')

def main():
    rt=runtime(); last=max(rt); dimensions=json.loads(fetch(DIMENSIONS,'application/json'))
    url=f'{BASE}?fromDate={last}&toDate={last}'
    series=parse(fetch(url))
    rows=[]
    for s in series:
        raw=s['values'].get(last)
        if raw is None:continue
        rows.append({'dimensions':s['dimensions'],'official_raw':raw,'abs_diff_vs_runtime_scale1':abs(raw-rt[last]),'abs_diff_vs_runtime_scale_1e3':abs(raw*1e-3-rt[last])})
    rows.sort(key=lambda x:min(x['abs_diff_vs_runtime_scale1'],x['abs_diff_vs_runtime_scale_1e3']))
    print(json.dumps({'schema':'GMFQ_SNB_CHF_CREDIT_UNFILTERED_MONTH_PROBE_V1','url':url,'runtime_last_date':last,'runtime_last':rt[last],'bank_categories_metadata':d0_items(dimensions),'series_count':len(rows),'distinct_d0':sorted({r['dimensions']['D0'] for r in rows}),'closest':rows[:30]},indent=2,ensure_ascii=False))
if __name__=='__main__':main()
