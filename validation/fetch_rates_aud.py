#!/usr/bin/env python3
from __future__ import annotations
import csv
import io
import urllib.request
from datetime import datetime

URL='https://www.rba.gov.au/statistics/tables/csv/f2-data.csv'
SERIES_2Y='FCMYGBAG2D'
SERIES_10Y='FCMYGBAG10D'
AUTHORITY='Reserve Bank of Australia'


def fetch(url:str=URL)->str:
    req=urllib.request.Request(url,headers={'User-Agent':'GLOBAL-MACRO-FX-QUANT rates audit'})
    with urllib.request.urlopen(req,timeout=60) as r:
        return r.read().decode('utf-8-sig')


def parse(text:str)->dict:
    rows=list(csv.reader(io.StringIO(text)))
    if len(rows)<12:
        raise RuntimeError('RBA F2: unexpectedly short CSV')
    title=rows[1]
    series=rows[10]
    if not series or series[0].strip()!='Series ID':
        raise RuntimeError(f'RBA F2: Series ID row not found at canonical position: {series[:3]}')
    try:
        i2=series.index(SERIES_2Y)
        i10=series.index(SERIES_10Y)
    except ValueError as exc:
        raise RuntimeError(f'RBA F2: required official series IDs missing: {SERIES_2Y}/{SERIES_10Y}') from exc
    if '2 year' not in title[i2].lower() or '10 year' not in title[i10].lower():
        raise RuntimeError('RBA F2: series ID/title semantic mismatch')
    obs=[]
    for row in rows[11:]:
        if len(row)<=max(i2,i10):
            continue
        ds=row[0].strip()
        v2=row[i2].strip(); v10=row[i10].strip()
        if not ds or not v2 or not v10:
            continue
        try:
            d=datetime.strptime(ds,'%d-%b-%Y').date().isoformat()
            y2=float(v2); y10=float(v10)
        except ValueError:
            continue
        obs.append((d,y2,y10))
    if not obs:
        raise RuntimeError('RBA F2: no complete same-day 2Y/10Y observations')
    d,y2,y10=max(obs,key=lambda x:x[0])
    return {
        'date':d,'2Y':y2,'10Y':y10,
        'authority':AUTHORITY,'source':'F2 Capital Market Yields – Government Bonds – Daily',
        'series_2Y':SERIES_2Y,'series_10Y':SERIES_10Y,
        'source_url':URL,
        'publication_cadence':'RBA F2 file is published weekly; observations inside the file are daily government bond yields'
    }


def latest()->dict:
    return parse(fetch())


if __name__=='__main__':
    import json
    print(json.dumps(latest(),indent=2,ensure_ascii=False))
