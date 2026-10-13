#!/usr/bin/env python3
import csv
import io
import json
import urllib.parse
import urllib.request
from pathlib import Path

LIQ = Path('live_data/sections/NATIVE_LIQ_DATA.json')
BASE = 'https://data-api.ecb.europa.eu/service/data/BSI'

CANDIDATES = {
    'Y_U_A20': 'M.U2.Y.U.A20.A.1.U2.2240.Z01.E',
    'N_U_A20': 'M.U2.N.U.A20.A.1.U2.2240.Z01.E',
    'N_A_A20': 'M.U2.N.A.A20.A.1.U2.2240.Z01.E',
    'N_A_A20T': 'M.U2.N.A.A20T.A.1.U2.2240.Z01.E',
}


def fetch(key):
    qs = urllib.parse.urlencode({'format':'csvdata','startPeriod':'2025-01'})
    url=f'{BASE}/{key}?{qs}'
    req=urllib.request.Request(url,headers={
        'User-Agent':'global-macro-fx-quant/1.0',
        'Accept':'text/csv,application/vnd.sdmx.data+csv;version=2.0.0',
    })
    with urllib.request.urlopen(req,timeout=45) as r:
        text=r.read().decode('utf-8-sig')
    out={}
    for row in csv.DictReader(io.StringIO(text)):
        date=(row.get('TIME_PERIOD') or '')[:7]
        raw=row.get('OBS_VALUE')
        if date and raw not in (None,''):
            out[date]=float(raw)
    if not out:
        raise SystemExit(f'no observations for {key}')
    return url,out


def main():
    liq=json.loads(LIQ.read_text(encoding='utf-8'))
    rt=liq['EUR']['credit']
    runtime={str(d)[:7]:float(v) for d,v in zip(rt['dates'],rt['values']) if str(d)[:4] in {'2025','2026'}}
    result={'schema':'GMFQ_EUR_NFC_LOANS_VARIANT_DIAGNOSTIC_V1','runtime_last_date':str(rt['last_date'])[:7],'candidates':{}}
    for name,key in CANDIDATES.items():
        url,src=fetch(key)
        overlap=sorted(set(runtime)&set(src))
        if not overlap:
            stats={'overlap_count':0}
        else:
            diffs=[runtime[d]-src[d] for d in overlap]
            absdiff=[abs(x) for x in diffs]
            stats={
                'overlap_count':len(overlap),
                'first_overlap':overlap[0],
                'last_overlap':overlap[-1],
                'mean_abs_diff':sum(absdiff)/len(absdiff),
                'max_abs_diff':max(absdiff),
                'last_runtime':runtime[overlap[-1]],
                'last_source':src[overlap[-1]],
                'last_diff':diffs[-1],
                'exact_matches_1e6':sum(1 for x in absdiff if x <= 1e-6),
            }
        result['candidates'][name]={'series_id':'BSI.'+key,'url':url,**stats}
    ranked=sorted(result['candidates'].items(),key=lambda kv: kv[1].get('mean_abs_diff',float('inf')))
    result['ranking_by_mean_abs_diff']=[name for name,_ in ranked]
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__':
    main()
