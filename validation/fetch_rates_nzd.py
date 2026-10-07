#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime
from html.parser import HTMLParser
from urllib.request import Request, urlopen

URL='https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates/wholesale-interest-rates'
AUTHORITY='Reserve Bank of New Zealand'

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows=[]; self.row=None; self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='tr': self.row=[]
        elif tag in {'td','th'} and self.row is not None: self.cell=[]
    def handle_data(self,data):
        if self.cell is not None: self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in {'td','th'} and self.cell is not None and self.row is not None:
            self.row.append(' '.join(''.join(self.cell).split()))
            self.cell=None
        elif tag=='tr' and self.row is not None:
            if self.row: self.rows.append(self.row)
            self.row=None

def fetch(url:str=URL)->str:
    req=Request(url,headers={'User-Agent':'Mozilla/5.0 GMFQ-rates-audit/1.0'})
    with urlopen(req,timeout=45) as r:
        raw=r.read()
    return raw.decode('utf-8','replace')

def parse_date(s:str):
    s=' '.join(str(s).replace('\xa0',' ').split())
    for fmt in ('%d %b %Y','%d %B %Y'):
        try: return datetime.strptime(s,fmt).date()
        except ValueError: pass
    return None

def parse(html:str)->dict:
    p=TableParser(); p.feed(html)
    obs=[]
    # Official summary table columns:
    # Date, OCR, ODR, ORRF, interbank, 30d, 60d, 90d, 1Y, 2Y, 5Y, 10Y, 2-10s.
    for row in p.rows:
        if len(row) < 12: continue
        d=parse_date(row[0])
        if d is None: continue
        try:
            y2=float(row[9]); y10=float(row[11])
        except (ValueError,TypeError,IndexError):
            continue
        obs.append((d.isoformat(),y2,y10))
    if not obs:
        raise RuntimeError('RBNZ B2: no dated same-row 2Y/10Y observations parsed')
    d,y2,y10=max(obs,key=lambda x:x[0])
    return {'date':d,'2Y':y2,'10Y':y10,'authority':AUTHORITY,'source':'RBNZ B2 wholesale interest rates'}

def main()->int:
    import json
    print(json.dumps(parse(fetch()),indent=2))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
