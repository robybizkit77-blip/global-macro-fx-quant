#!/usr/bin/env python3
import json, urllib.request
from pathlib import Path

URL='https://www.bankofcanada.ca/valet/observations/group/bond_yields_benchmark/json'
SERIES_2Y='BD.CDN.2YR.DQ.YLD'
SERIES_10Y='BD.CDN.10YR.DQ.YLD'

def get_json(url):
    req=urllib.request.Request(url,headers={'User-Agent':'GMFQ-Rates-Audit/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=60) as r:
        return json.load(r)

def main():
    raw=get_json(URL)
    detail=raw.get('seriesDetail',{})
    if SERIES_2Y not in detail or SERIES_10Y not in detail:
        raise SystemExit('Expected Bank of Canada benchmark series are missing')
    obs=[]
    for row in raw.get('observations',[]):
        d=row.get('d')
        try:
            y2=float(row[SERIES_2Y]['v']); y10=float(row[SERIES_10Y]['v'])
        except Exception:
            continue
        obs.append((d,y2,y10))
    if not obs: raise SystemExit('No same-day CAD 2Y/10Y observations')
    d,y2,y10=max(obs,key=lambda x:x[0])
    rates=json.loads(Path('live_data/sections/NATIVE_RATES_DATA.json').read_text())
    cur=rates['CAD']
    out={'CAD':{
        'official_date':d,'2Y':y2,'10Y':y10,
        'current_date':cur['date'],'current_2Y':cur['2Y'],'current_10Y':cur['10Y'],
        'series_2Y':SERIES_2Y,'series_10Y':SERIES_10Y,
        'source':'Bank of Canada Valet API · selected benchmark Government of Canada bond yields'
    }}
    print(json.dumps(out,indent=2,ensure_ascii=False))
    Path('validation/rates_cad_audit_output.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')

if __name__=='__main__': main()
