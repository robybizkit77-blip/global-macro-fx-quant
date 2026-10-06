from __future__ import annotations

import csv
import io
import json
from datetime import datetime, date
from pathlib import Path
from urllib.request import Request, urlopen

OUT=Path('history/pit_v1/USD_TREASURY_PAR_2Y_DAILY_2016_2026.csv')
EVID=Path('validation/USD_TREASURY_2Y_MATERIALIZATION_2026-10-06.json')
YEARS=range(2016,2027)
END=date(2026,10,6)
UA='Mozilla/5.0 GMFQ-PIT-Audit/1.0 (research; contact via repository)'

def url_for(year:int)->str:
    return f'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve&field_tdr_date_value={year}&page=&_format=csv'

def get(url:str)->str:
    req=Request(url,headers={'User-Agent':UA,'Accept':'text/csv,text/plain,*/*'})
    with urlopen(req,timeout=60) as r:
        return r.read().decode('utf-8-sig')

def parse_date(s:str)->date:
    return datetime.strptime(s.strip(),'%m/%d/%Y').date()

def main():
    rows=[]; audits=[]
    for y in YEARS:
        url=url_for(y); text=get(url); rdr=csv.DictReader(io.StringIO(text))
        if not rdr.fieldnames or 'Date' not in rdr.fieldnames or '2 Yr' not in rdr.fieldnames:
            raise SystemExit(f'Unexpected Treasury schema for {y}: {rdr.fieldnames}')
        n=0
        for r in rdr:
            if not r.get('Date') or not r.get('2 Yr'): continue
            d=parse_date(r['Date'])
            if d>END: continue
            v=float(r['2 Yr'])
            if not (0.0 <= v <= 20.0): raise SystemExit(f'Implausible 2Y value {d} {v}')
            rows.append({'date':d.isoformat(),'usd_treasury_par_2y_pct':v,'source_year':y,'source_url':url})
            n+=1
        audits.append({'year':y,'rows':n,'source_url':url})
    rows.sort(key=lambda r:r['date'])
    dates=[r['date'] for r in rows]
    if len(dates)!=len(set(dates)): raise SystemExit('Duplicate Treasury dates')
    if not rows or rows[0]['date']>'2016-01-05' or rows[-1]['date']<'2026-10-02':
        raise SystemExit(f'Unexpected coverage {rows[0]["date"] if rows else None} to {rows[-1]["date"] if rows else None}')
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    ev={
      'schema':'GMFQ_USD_TREASURY_2Y_HISTORY_V1','status':'PASS',
      'source':'U.S. Department of the Treasury Daily Treasury Par Yield Curve Rates',
      'instrument':'2-year Treasury par yield','role':'observed front-end repricing proxy; NOT OIS/Fed funds expectation',
      'coverage':{'start':rows[0]['date'],'end':rows[-1]['date'],'daily_observations':len(rows)},
      'annual_source_audit':audits,'output':str(OUT),
      'guardrails':['single official instrument family across all years','no interpolation','no synthetic OIS','no engine/live-data changes']
    }
    EVID.write_text(json.dumps(ev,indent=2),encoding='utf-8'); print(json.dumps(ev,indent=2))
if __name__=='__main__': main()
