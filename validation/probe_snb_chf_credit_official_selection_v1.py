#!/usr/bin/env python3
import csv
import io
import json
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
URL='https://data.snb.ch/api/cube/bakredinausbm/data/csv/en?dimSel=D0(AV1),D1(T0,I,A),D2(T1,H),D3(F)&fromDate=2025-07&toDate=2026-07'


def fetch():
    req=urllib.request.Request(URL,headers={'User-Agent':'GMFQ-validation/1.0','Accept':'text/csv'})
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
    try:dialect=csv.Sniffer().sniff(text[:8192],delimiters=';,\t')
    except csv.Error:
        dialect=csv.excel; dialect.delimiter=';'
    rows=list(csv.reader(io.StringIO(text),dialect=dialect))
    width=max(len(r) for r in rows); rows=[r+['']*(width-len(r)) for r in rows]
    header_idx=next((i for i,r in enumerate(rows) if [str(x).strip() for x in r[:6]]==['Date','D0','D1','D2','D3','Value']),None)
    if header_idx is None:raise SystemExit(f'expected SNB long-table header not found preview={rows[:20]!r}')
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
    if not grouped:raise SystemExit('SNB official selection returned no dimensioned series')
    series=[]
    for dims,vals in grouped.items():
        series.append({'dimensions':{'D0':dims[0],'D1':dims[1],'D2':dims[2],'D3':dims[3]},'values':vals})
    return rows[:header_idx+1],series

def compare(rt,vals):
    common=sorted(set(rt)&set(vals)); best=None
    for scale in (1,1e-3,1e3,1e-6,1e6):
        exact=sum(abs(rt[m]-vals[m]*scale)<=1e-9 for m in common)
        r1=sum(abs(rt[m]-round(vals[m]*scale,1))<=1e-9 for m in common)
        mae=sum(abs(rt[m]-vals[m]*scale) for m in common)/(len(common) or 1)
        row={'scale':scale,'overlap':len(common),'exact':exact,'rounded_1dp_exact':r1,'mae':mae}
        score=(r1,exact,-mae)
        if best is None or score>best[0]:best=(score,row)
    return best[1]

def main():
    text=fetch(); header,series=parse(text); rt=runtime(); ranked=[]
    last=max(rt)
    for s in series:
        cmp=compare(rt,s['values'])
        ranked.append({'dimensions':s['dimensions'],**cmp,'runtime_last_date':last,'runtime_last':rt[last],'official_on_runtime_last_raw':s['values'].get(last),'official_latest_date':max(s['values']),'official_latest_raw':s['values'][max(s['values'])]})
    ranked.sort(key=lambda x:(x['rounded_1dp_exact'],x['exact'],x['overlap'],-x['mae']),reverse=True)
    print(json.dumps({'schema':'GMFQ_SNB_CHF_CREDIT_OFFICIAL_SELECTION_PROBE_V1','url':URL,'series_count':len(series),'header_preview':header,'ranked':ranked},indent=2,ensure_ascii=False))
if __name__=='__main__':main()
