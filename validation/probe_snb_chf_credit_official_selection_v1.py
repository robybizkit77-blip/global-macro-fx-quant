#!/usr/bin/env python3
import csv
import io
import json
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

RUNTIME=Path('live_data/sections/NATIVE_LIQ_DATA.json')
D0_CODES=('AV1','AV2','AV3','AV4','AV10')
BASE='https://data.snb.ch/api/cube/bakredinausbm/data/csv/en'


def url_for(d0):
    return f'{BASE}?dimSel=D0({d0}),D1(T0,I,A),D2(T1,H,K),D3(F,B)&fromDate=2025-07&toDate=2026-07'

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'GMFQ-validation/1.0','Accept':'text/csv'})
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
    rt=runtime(); ranked=[]; requests=[]; seen=set(); last=max(rt)
    for d0 in D0_CODES:
        url=url_for(d0)
        rec={'d0':d0,'url':url}
        try:
            text=fetch(url); series=parse(text)
            rec['status']='OK' if series else 'EMPTY'; rec['series_count']=len(series)
        except Exception as e:
            series=[]; rec['status']='ERROR'; rec['series_count']=0; rec['error']=f'{type(e).__name__}: {e}'
        requests.append(rec)
        for s in series:
            key=tuple(s['dimensions'][k] for k in ('D0','D1','D2','D3'))
            if key in seen:continue
            seen.add(key)
            cmp=compare(rt,s['values'])
            ranked.append({'dimensions':s['dimensions'],**cmp,'runtime_last_date':last,'runtime_last':rt[last],'official_on_runtime_last_raw':s['values'].get(last),'official_latest_date':max(s['values']),'official_latest_raw':s['values'][max(s['values'])]})
    ranked.sort(key=lambda x:(x['rounded_1dp_exact'],x['exact'],x['overlap'],-x['mae']),reverse=True)
    if not ranked:raise SystemExit('all SNB D0 category requests returned zero usable dimensioned series')
    print(json.dumps({'schema':'GMFQ_SNB_CHF_CREDIT_OFFICIAL_SELECTION_PROBE_V3','requests':requests,'requested_d0':list(D0_CODES),'series_count':len(ranked),'ranked':ranked[:60]},indent=2,ensure_ascii=False))
if __name__=='__main__':main()
