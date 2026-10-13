#!/usr/bin/env python3
import csv
import io
import json
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

RUNTIME = Path('live_data/sections/NATIVE_LIQ_DATA.json')
BASE = 'https://data.snb.ch/api/warehouse/cube/BSTA.SNB.MONA_U.BIL.AKT.FMI.GGU/data/csv/en'
CREDIT_DIMS = 'https://data.snb.ch/api/cube/bakredinausbm/dimensions/en'
VARIANTS = {
    'U_T_T_A40': 'KONSOLIDIERUNGSSTUFE(U),INLANDAUSLAND(T),WAEHRUNG(T),BANKENGRUPPE(A40)',
    'U_T_CHF_A40': 'KONSOLIDIERUNGSSTUFE(U),INLANDAUSLAND(T),WAEHRUNG(CHF),BANKENGRUPPE(A40)',
    'U_I_T_A40': 'KONSOLIDIERUNGSSTUFE(U),INLANDAUSLAND(I),WAEHRUNG(T),BANKENGRUPPE(A40)',
    'U_I_CHF_A40': 'KONSOLIDIERUNGSSTUFE(U),INLANDAUSLAND(I),WAEHRUNG(CHF),BANKENGRUPPE(A40)',
}


def fetch(url, accept='text/csv'):
    req = urllib.request.Request(url, headers={'User-Agent':'GMFQ-validation/1.0','Accept':accept})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode('utf-8-sig')


def norm_month(v):
    s=str(v or '').strip()
    for fmt in ('%Y-%m','%Y-%m-%d','%d.%m.%Y','%d/%m/%Y'):
        try: return datetime.strptime(s,fmt).strftime('%Y-%m')
        except ValueError: pass
    return None


def runtime():
    d=json.loads(RUNTIME.read_text(encoding='utf-8'))['CHF']['liquidity']
    return {norm_month(x):float(v) for x,v in zip(d['dates'],d['values'])}


def parse_single(text):
    try: dialect=csv.Sniffer().sniff(text[:4096],delimiters=';,\t')
    except csv.Error:
        dialect=csv.excel; dialect.delimiter=';'
    rows=list(csv.reader(io.StringIO(text),dialect=dialect))
    width=max(len(r) for r in rows)
    rows=[r+['']*(width-len(r)) for r in rows]
    data_start=next(i for i,r in enumerate(rows) if norm_month(r[0]))
    numeric_cols=[]
    for c in range(1,width):
        count=0
        for r in rows[data_start:]:
            if not norm_month(r[0]): continue
            try: float(str(r[c]).replace("'",'').replace(' ','')); count+=1
            except ValueError: pass
        if count: numeric_cols.append((count,c))
    if not numeric_cols: raise SystemExit('no numeric data column in SNB response')
    col=max(numeric_cols)[1]
    out={}
    for r in rows[data_start:]:
        m=norm_month(r[0])
        if not m: continue
        try: out[m]=float(str(r[col]).replace("'",'').replace(' ',''))
        except ValueError: pass
    return out


def compare(rt, raw):
    common=sorted(set(rt)&set(raw))
    best=None
    for scale in (1,1e-3,1e3,1e-6,1e6):
        exact=sum(abs(rt[m]-raw[m]*scale)<=1e-9 for m in common)
        mae=sum(abs(rt[m]-raw[m]*scale) for m in common)/len(common) if common else None
        row={'scale':scale,'overlap':len(common),'exact':exact,'mae':mae}
        score=(exact,-(mae if mae is not None else 1e99))
        if best is None or score>best[0]: best=(score,row)
    row=best[1]
    last=max(rt)
    row.update({'runtime_last_date':last,'runtime_last_value':rt[last],'official_raw_on_runtime_last':raw.get(last),'official_scaled_on_runtime_last':raw.get(last)*row['scale'] if raw.get(last) is not None else None,'official_latest_date':max(raw),'official_latest_raw':raw[max(raw)]})
    return row


def summarize_dims(obj):
    # Keep the exact API payload shape but trim large descriptive fields recursively.
    if isinstance(obj,dict):
        out={}
        for k,v in obj.items():
            kl=k.lower()
            if kl in {'description','comment','note','notes','footnote','footnotes'}: continue
            out[k]=summarize_dims(v)
        return out
    if isinstance(obj,list): return [summarize_dims(x) for x in obj[:200]]
    return obj


def main():
    rt=runtime()
    variants={}
    for name,dimsel in VARIANTS.items():
        url=BASE+'?'+urllib.parse.urlencode({'dimSel':dimsel,'fromDate':'2025-07','toDate':'2026-07'},safe='(),')
        raw=parse_single(fetch(url))
        variants[name]={'url':url,**compare(rt,raw)}
    dims=json.loads(fetch(CREDIT_DIMS,'application/json'))
    out={'schema':'GMFQ_SNB_CHF_EXACT_VARIANT_PROBE_V1','sight_variants':variants,'credit_dimensions':summarize_dims(dims)}
    print(json.dumps(out,indent=2,ensure_ascii=False))

if __name__=='__main__': main()
