#!/usr/bin/env python3
from __future__ import annotations
from datetime import date, datetime
from io import BytesIO
from urllib.request import Request, urlopen
import openpyxl

URL='https://rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily-close.xlsx'
AUTHORITY='Reserve Bank of New Zealand'


def fetch(url:str=URL)->bytes:
    req=Request(url,headers={
        'User-Agent':'Mozilla/5.0 GMFQ-rates-audit/1.0',
        'Accept':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*',
        'Referer':'https://www.rbnz.govt.nz/statistics/series/data-file-index-page'
    })
    with urlopen(req,timeout=60) as r:
        return r.read()


def norm(x)->str:
    return ' '.join(str(x or '').replace('\xa0',' ').split()).lower()


def as_date(x):
    if isinstance(x,datetime): return x.date()
    if isinstance(x,date): return x
    s=' '.join(str(x or '').split())
    for fmt in ('%d %b %Y','%d %B %Y','%Y-%m-%d','%d/%m/%Y'):
        try: return datetime.strptime(s,fmt).date()
        except ValueError: pass
    return None


def parse(raw:bytes)->dict:
    wb=openpyxl.load_workbook(BytesIO(raw),read_only=True,data_only=True)
    best=None
    for ws in wb.worksheets:
        rows=list(ws.iter_rows(values_only=True))
        first_data=None
        for i,row in enumerate(rows[:80]):
            if row and as_date(row[0]) is not None:
                first_data=i; break
        if first_data is None or first_data < 1:
            continue
        width=max(len(r) for r in rows[:first_data+1])
        ctx=[]
        for c in range(width):
            bits=[]
            for r in rows[:first_data]:
                if c < len(r) and r[c] not in (None,''):
                    bits.append(norm(r[c]))
            ctx.append(' | '.join(bits))
        def pick(term):
            strong=[i for i,s in enumerate(ctx) if term in s and 'government' in s and ('close' in s or 'closing' in s)]
            if len(strong)==1: return strong[0]
            govt=[i for i,s in enumerate(ctx) if term in s and 'government' in s]
            if len(govt)==1: return govt[0]
            return None
        c2=pick('2 year'); c10=pick('10 year')
        if c2 is None or c10 is None:
            continue
        obs=[]
        for row in rows[first_data:]:
            if not row: continue
            d=as_date(row[0])
            if d is None: continue
            try:
                y2=float(row[c2]); y10=float(row[c10])
            except (ValueError,TypeError,IndexError):
                continue
            obs.append((d.isoformat(),y2,y10))
        if obs:
            candidate=max(obs,key=lambda x:x[0])
            if best is None or candidate[0] > best[0]: best=candidate
    if best is None:
        raise RuntimeError('RBNZ B2 XLSX: no same-row government 2Y/10Y observations parsed')
    d,y2,y10=best
    return {'date':d,'2Y':y2,'10Y':y10,'authority':AUTHORITY,'source':'RBNZ B2 daily close XLSX'}


def main()->int:
    import json
    print(json.dumps(parse(fetch()),indent=2))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
