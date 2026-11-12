#!/usr/bin/env python3
from __future__ import annotations
import csv
import io
import urllib.request
import urllib.error
import math
from datetime import datetime, date, timezone

URL='https://www.rba.gov.au/statistics/tables/csv/f2-data.csv'
XLSX_URL='https://www.rba.gov.au/statistics/tables/xls/f02d.xlsx'
USER_AGENT='GlobalMacroFXQuant/1.0 (official RBA statistical tables; https://github.com/robybizkit77-blip/global-macro-fx-quant)'
SERIES_2Y='FCMYGBAG2D'
SERIES_10Y='FCMYGBAG10D'
AUTHORITY='Reserve Bank of Australia'


def fetch(url:str=URL)->str:
    req=urllib.request.Request(url,headers={'User-Agent':USER_AGENT,'Accept':'text/csv,*/*'})
    with urllib.request.urlopen(req,timeout=60) as r:
        return r.read().decode('utf-8-sig')


def parse(text:str)->dict:
    rows=list(csv.reader(io.StringIO(text)))
    if len(rows)<12:
        raise RuntimeError('RBA F2: unexpectedly short CSV')
    title=rows[1]
    frequency=rows[3]
    source=rows[8]
    publication=rows[9]
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
    if frequency[i2].strip()!='Daily' or frequency[i10].strip()!='Daily':
        raise RuntimeError('RBA F2: required series are no longer marked Daily')
    if source[i2].strip()!='RBA' or source[i10].strip()!='RBA':
        raise RuntimeError('RBA F2: required series source is no longer RBA')
    try:
        p2=datetime.strptime(publication[i2].strip(),'%d-%b-%Y').date().isoformat()
        p10=datetime.strptime(publication[i10].strip(),'%d-%b-%Y').date().isoformat()
    except ValueError as exc:
        raise RuntimeError('RBA F2: invalid publication date') from exc
    if p2!=p10:
        raise RuntimeError(f'RBA F2: 2Y/10Y publication-date mismatch {p2} vs {p10}')
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
        'publication_date':p2,
        'authority':AUTHORITY,'source':'F2 Capital Market Yields – Government Bonds – Daily',
        'series_2Y':SERIES_2Y,'series_10Y':SERIES_10Y,
        'source_url':URL,'source_format':'RBA_F2_OFFICIAL_CSV',
        'publication_cadence':'RBA F2 file is published weekly; observations inside the file are daily government bond yields'
    }



def _xlsx_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for fmt in ('%d-%b-%Y','%d/%m/%Y','%Y-%m-%d'):
            try:
                return datetime.strptime(value.strip(),fmt).date()
            except ValueError:
                pass
    raise ValueError('invalid RBA F2 workbook date')


def fetch_xlsx(url:str=XLSX_URL)->bytes:
    """Second *official* RBA F2 representation, never a secondary quote."""
    req=urllib.request.Request(url,headers={
        'User-Agent':USER_AGENT,
        'Accept':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/octet-stream'
    })
    with urllib.request.urlopen(req,timeout=45) as response:
        raw=response.read(12_000_001)
    if not raw.startswith(b'PK\x03\x04') or len(raw)>12_000_000:
        raise RuntimeError('RBA F2: invalid or oversized official XLSX')
    return raw


def parse_xlsx(raw:bytes, *, asof:date|None=None)->dict:
    """Fail closed if F2 series IDs, tenor, units, publisher or dates differ."""
    from openpyxl import load_workbook
    asof=asof or datetime.now(timezone.utc).date()
    workbook=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
    candidates=[]
    try:
        for sheet in workbook.worksheets:
            rows=list(sheet.iter_rows(values_only=True))
            series_rows=[(i,r) for i,r in enumerate(rows[:30])
                         if r and str(r[0] or '').strip().lower()=='series id']
            for row_i, ids in series_rows:
                if SERIES_2Y not in ids or SERIES_10Y not in ids:
                    continue
                i2=ids.index(SERIES_2Y)
                i10=ids.index(SERIES_10Y)
                if i2==i10:
                    raise RuntimeError('RBA F2 XLSX: duplicated tenor column')
                meta={}
                for row in rows[:row_i]:
                    label=str((row or [None])[0] or '').strip().lower()
                    if label in ('title','frequency','source','units','publication date'):
                        if label in meta:
                            raise RuntimeError('RBA F2 XLSX: duplicate metadata label '+label)
                        meta[label]=row
                required=('title','frequency','source','units','publication date')
                if not all(key in meta and len(meta[key])>max(i2,i10) for key in required):
                    raise RuntimeError('RBA F2 XLSX: required issuer metadata unavailable')
                def entry(key,col):
                    return str(meta[key][col] or '').strip()
                if ('2 year' not in entry('title',i2).lower()
                        or '10 year' not in entry('title',i10).lower()):
                    raise RuntimeError('RBA F2 XLSX: title/series mismatch')
                for col in (i2,i10):
                    if entry('frequency',col).lower()!='daily' or entry('source',col)!='RBA':
                        raise RuntimeError('RBA F2 XLSX: official source/frequency mismatch')
                    if not any(x in entry('units',col).lower() for x in ('per cent','percent','%')):
                        raise RuntimeError('RBA F2 XLSX: yield unit not verified')
                pub2=_xlsx_date(meta['publication date'][i2])
                pub10=_xlsx_date(meta['publication date'][i10])
                if pub2!=pub10 or pub2>asof:
                    raise RuntimeError('RBA F2 XLSX: publication mismatch or future release')
                observations=[]
                seen=set()
                for row in rows[row_i+1:]:
                    if not row or len(row)<=max(i2,i10):
                        continue
                    if row[i2] is None or row[i10] is None:
                        continue
                    try:
                        d=_xlsx_date(row[0])
                        y2=float(row[i2]); y10=float(row[i10])
                    except (TypeError,ValueError):
                        continue
                    if d in seen:
                        raise RuntimeError('RBA F2 XLSX: duplicate observation date')
                    if d>pub2 or d>asof or not all(math.isfinite(x) and -5<x<25 for x in (y2,y10)):
                        raise RuntimeError('RBA F2 XLSX: future/invalid official yield')
                    seen.add(d)
                    observations.append((d,y2,y10))
                if not observations:
                    raise RuntimeError('RBA F2 XLSX: no comparable same-date 2Y/10Y')
                d,y2,y10=max(observations,key=lambda p:p[0])
                candidates.append({
                    'date':d.isoformat(),'2Y':y2,'10Y':y10,
                    'publication_date':pub2.isoformat(),
                    'authority':AUTHORITY,
                    'source':'F2 Capital Market Yields – Government Bonds – Daily',
                    'series_2Y':SERIES_2Y,'series_10Y':SERIES_10Y,
                    'source_url':XLSX_URL,'source_format':'RBA_F2_OFFICIAL_XLSX',
                    'publication_cadence':'RBA F2 file is published weekly; observations inside the file are daily government bond yields'
                })
        if len(candidates)!=1:
            raise RuntimeError('RBA F2 XLSX: unique official daily table not found')
        return candidates[0]
    finally:
        workbook.close()


def latest()->dict:
    try:
        return parse(fetch())
    except urllib.error.HTTPError as exc:
        # An inaccessible CSV is not data. Try only RBA's *same table* XLSX.
        # Bad/removed CSV URLs (e.g. 404) remain hard errors.
        if exc.code not in (403,429,500,502,503,504):
            raise
    except urllib.error.URLError:
        # Transient transport error only, never a CSV parser/identity mismatch.
        pass
    return parse_xlsx(fetch_xlsx())



if __name__=='__main__':
    import json
    print(json.dumps(latest(),indent=2,ensure_ascii=False))
