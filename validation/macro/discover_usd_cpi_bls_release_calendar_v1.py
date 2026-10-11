#!/usr/bin/env python3
"""Read-only discovery of official BLS CPI release availability, 2018-2026.

Purpose: establish an exact release-date/time timeline for strict USD inflation
PIT reconstruction. This does not materialize CPI values and does not certify
USD.inflation by itself.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import pathlib
import re
import time
import urllib.request
from datetime import datetime
from html.parser import HTMLParser

YEARS=range(2018,2027)
BASE='https://www.bls.gov/schedule/{year}/home.htm'
UA='GLOBAL-MACRO-FX-QUANT USD CPI BLS release-calendar discovery v1'
TARGET_START='2018-01'
TARGET_END='2026-08'
EXPECTED_MONTHS=104

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.in_tr=False; self.in_td=False; self.cell=[]; self.row=[]; self.rows=[]
    def handle_starttag(self, tag, attrs):
        if tag=='tr': self.in_tr=True; self.row=[]
        elif tag in ('td','th') and self.in_tr: self.in_td=True; self.cell=[]
    def handle_data(self, data):
        if self.in_td: self.cell.append(data)
    def handle_endtag(self, tag):
        if tag in ('td','th') and self.in_td:
            self.row.append(' '.join(''.join(self.cell).split())); self.in_td=False
        elif tag=='tr' and self.in_tr:
            if self.row: self.rows.append(self.row)
            self.in_tr=False


def fetch(url:str)->tuple[bytes,str]:
    last=None
    for attempt in range(1,5):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*;q=0.8','Connection':'close'})
            with urllib.request.urlopen(req,timeout=60) as r:
                raw=r.read(); final=r.geturl()
            return raw,final
        except Exception as exc:
            last=exc
            if attempt<4: time.sleep((3,8,15)[attempt-1])
    raise RuntimeError(f'BLS fetch failed after 4 attempts: {url}: {last!r}')


def month_key(label:str)->str:
    dt=datetime.strptime(label.strip(),'%B %Y')
    return dt.strftime('%Y-%m')


def parse_release_date(text:str)->str:
    # BLS annual calendar cells use e.g. "Friday, January 12, 2018".
    clean=' '.join(text.replace('\xa0',' ').split())
    for fmt in ('%A, %B %d, %Y','%B %d, %Y'):
        try: return datetime.strptime(clean,fmt).date().isoformat()
        except ValueError: pass
    raise ValueError(f'unparsed BLS release date: {text!r}')


def extract_year(year:int)->tuple[list[dict],dict]:
    url=BASE.format(year=year)
    raw,final=fetch(url)
    text=raw.decode('utf-8','replace')
    parser=TableParser(); parser.feed(text)
    found=[]
    # Be tolerant to extra cells, but identify row content semantically.
    for row in parser.rows:
        joined=' | '.join(row)
        m=re.search(r'Consumer Price Index(?:\s*\([^)]*\))?\s+for\s+([A-Za-z]+\s+\d{4})',joined,re.I)
        if not m: continue
        ref=month_key(m.group(1))
        time_cell=next((c for c in row if re.fullmatch(r'0?8:30\s*AM',c,re.I)),None)
        if time_cell is None:
            raise ValueError(f'non-08:30 CPI release row in {year}: {row!r}')
        date_cell=next((c for c in row if re.search(r'[A-Za-z]+,\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}',c)),None)
        if date_cell is None:
            raise ValueError(f'missing release date in {year}: {row!r}')
        found.append({
            'reference_month':ref,
            'release_date':parse_release_date(date_cell),
            'release_time':'08:30',
            'release_timezone':'America/New_York',
            'availability_rule':'AT_OR_AFTER_OFFICIAL_BLS_RELEASE_TIMESTAMP',
            'calendar_year_page':year,
            'source_url':final,
        })
    return found,{
        'year':year,'source_url':final,'http_sha256':hashlib.sha256(raw).hexdigest(),'cpi_rows_found':len(found)
    }


def expected_keys()->list[str]:
    out=[]; y,m=2018,1
    while True:
        key=f'{y:04d}-{m:02d}'; out.append(key)
        if key==TARGET_END: return out
        m+=1
        if m==13: y+=1; m=1


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=pathlib.Path); a=ap.parse_args()
    rows=[]; sources=[]; errors=[]
    try:
        for year in YEARS:
            yr,src=extract_year(year); rows.extend(yr); sources.append(src)
    except Exception as exc:
        errors.append(repr(exc))

    by_ref={}
    duplicates=[]
    for row in rows:
        ref=row['reference_month']
        if ref in by_ref: duplicates.append(ref)
        by_ref[ref]=row
    expected=expected_keys()
    selected=[by_ref[k] for k in expected if k in by_ref]
    missing=[k for k in expected if k not in by_ref]
    status='DISCOVERY_PASS' if not errors and not duplicates and not missing and len(selected)==EXPECTED_MONTHS else 'DISCOVERY_FAIL'
    out={
        'schema':'GMFQ_USD_CPI_BLS_RELEASE_CALENDAR_DISCOVERY_V1',
        'status':status,
        'authority':'U.S. Bureau of Labor Statistics',
        'target':'USD.inflation',
        'calendar_source':'BLS Schedule of Selected Releases annual archives',
        'coverage':{'start':TARGET_START,'end':TARGET_END,'months':len(selected),'expected_months':EXPECTED_MONTHS},
        'release_rows':selected,
        'missing_reference_months':missing,
        'duplicate_reference_months':sorted(set(duplicates)),
        'errors':errors,
        'sources':sources,
        'invariants':{
            'official_release_time_required':'08:30 America/New_York',
            'release_timestamp_is_information_availability_floor':True,
            'same_day_pre_release_access_forbidden':True,
            'no_cpi_values_materialized':True,
            'production_write':False,
            'changes_live_data':False,
            'changes_engine_rules':False,
        },
    }
    semantic={**out,'sources':[{k:v for k,v in s.items() if k!='http_sha256'} for s in sources]}
    out['semantic_sha256']=hashlib.sha256(json.dumps(semantic,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'status':status,'coverage':out['coverage'],'missing':missing,'duplicates':duplicates,'errors':errors,'semantic_sha256':out['semantic_sha256']},indent=2))
    if status!='DISCOVERY_PASS': raise SystemExit(2)

if __name__=='__main__': main()
