#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, date
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

PAGE='https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/datasets/summaryoflabourmarketstatistics/current'
UA='global-macro-fx-quant/1.0 (+read-only PIT vintage build)'
EXPECTED_CODES={'unemployment':'MGSX','employment':'LF24'}
EXPECTED_COLS={'unemployment':8,'employment':16}


def parse_dt(s):
    s=' '.join(str(s).split())
    for fmt in ('%d %B %Y %H:%M','%d %B %Y'):
        try:return datetime.strptime(s,fmt)
        except ValueError:pass
    return None


def get(url, *, timeout=90, retries=5, sleep=0.35):
    last=None
    for n in range(retries):
        try:
            r=requests.get(url,headers={'User-Agent':UA},timeout=timeout)
            if r.status_code==429:
                time.sleep(2.5*(n+1));continue
            r.raise_for_status();time.sleep(sleep);return r
        except requests.RequestException as e:
            last=e
            if n==retries-1:raise
            time.sleep(1.5*(n+1))
    raise last or RuntimeError('request failed')


def discover_versions():
    r=get(PAGE,timeout=60)
    soup=BeautifulSoup(r.text,'html.parser')
    rows=[]
    for tr in soup.find_all('tr'):
        a=tr.find('a',href=True)
        if not a:continue
        cells=[' '.join(td.get_text(' ',strip=True).split()) for td in tr.find_all(['td','th'])]
        dt=None
        for c in reversed(cells):
            dt=parse_dt(c)
            if dt:break
        href=urljoin(PAGE,a['href'])
        if not dt or not re.search(r'\.xlsx?(?:\?|$)',href,re.I):continue
        rows.append({'superseded_at':dt.isoformat(),'url':href,'archive_cells':cells})
    # Current workbook: unlike archived rows, it has no superseded timestamp yet.
    current=None
    for a in soup.find_all('a',href=True):
        href=urljoin(PAGE,a['href'])
        txt=' '.join(a.get_text(' ',strip=True).split()).lower()
        if re.search(r'\.xlsx?(?:\?|$)',href,re.I) and ('xlsx' in txt or 'xls' in txt or 'download' in txt):
            if '/current/' in href or '/current?' in href:
                current={'superseded_at':None,'url':href,'archive_cells':['CURRENT']};break
    # De-duplicate exact URLs.
    seen=set();out=[]
    for x in sorted(rows,key=lambda z:z['superseded_at']):
        if x['url'] not in seen:seen.add(x['url']);out.append(x)
    if current and current['url'] not in seen:out.append(current)
    return out


def parse_period(v):
    if pd.isna(v):return None
    if isinstance(v,(datetime,pd.Timestamp)):return v.date().isoformat()
    s=' '.join(str(v).split())
    if re.match(r'^[A-Z][a-z]{2}-[A-Z][a-z]{2}\s+\d{4}$',s):return s
    if re.match(r'^[A-Z][a-z]{2}\s+\d{4}$',s):return s
    return None


def parse_book(meta,tmpdir):
    r=get(meta['url'],timeout=120,sleep=0.20)
    ext='.xlsx' if '.xlsx' in meta['url'].lower() else '.xls'
    path=tmpdir/f"a01_{abs(hash(meta['url']))}{ext}"
    path.write_bytes(r.content)
    df=pd.read_excel(path,sheet_name='1',header=None,dtype=object)
    # Header contract is semantic + code based, not fixed-row only.
    code_row=None
    for i in range(min(15,len(df))):
        vals=[str(x).strip() if pd.notna(x) else '' for x in df.iloc[i].tolist()]
        if 'Dataset identifier code' in vals:
            code_row=i;break
    if code_row is None:raise ValueError('dataset identifier row not found')
    codes=[str(x).strip() if pd.notna(x) else '' for x in df.iloc[code_row].tolist()]
    for k,code in EXPECTED_CODES.items():
        col=EXPECTED_COLS[k]
        if col>=len(codes) or codes[col]!=code:
            raise ValueError(f'{k} code mismatch at col {col}: {codes[col] if col<len(codes) else None!r}')
    # Publication date is explicit inside each vintage workbook.
    pub=None
    for i in range(min(8,len(df))):
        vals=df.iloc[i].tolist()
        for j,v in enumerate(vals[:-1]):
            if str(v).strip()=='Date of publication:':
                raw=vals[j+1]
                if isinstance(raw,(datetime,pd.Timestamp)):pub=raw.date()
                else:
                    z=pd.to_datetime(raw,errors='coerce')
                    if not pd.isna(z):pub=z.date()
    if pub is None:raise ValueError('publication date not found')
    # Last valid period row with numeric canonical headline rates.
    latest=None
    for i in range(code_row+1,len(df)):
        period=parse_period(df.iat[i,0] if df.shape[1] else None)
        if not period:continue
        try:u=float(df.iat[i,EXPECTED_COLS['unemployment']]);e=float(df.iat[i,EXPECTED_COLS['employment']])
        except (TypeError,ValueError):continue
        if not (0<=u<=30 and 30<=e<=100):continue
        latest={'row':int(i),'reference_period':period,'unemployment_rate':u,'employment_rate':e}
    if latest is None:raise ValueError('latest canonical rate row not found')
    return {
        'publication_date':pub.isoformat(),
        'superseded_at':meta['superseded_at'],
        'vintage_url':meta['url'],
        'reference_period':latest['reference_period'],
        'unemployment_rate':latest['unemployment_rate'],
        'employment_rate':latest['employment_rate'],
        'source_row':latest['row'],
        'series_codes':{'unemployment':'MGSX','employment':'LF24'},
        'source_sheet':'1'
    }


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--start',default='2018-01-01');ap.add_argument('--end',default='2026-09-30');ap.add_argument('--output',required=True);args=ap.parse_args()
    start=date.fromisoformat(args.start);end=date.fromisoformat(args.end)
    tmp=Path('/tmp/gmfq-gbp-ons-pit/a01books');tmp.mkdir(parents=True,exist_ok=True)
    versions=discover_versions();vintages=[];errors=[]
    for n,meta in enumerate(versions,1):
        try:
            x=parse_book(meta,tmp)
            d=date.fromisoformat(x['publication_date'])
            if start<=d<=end:
                vintages.append(x);print(f"{len(vintages):03d} {x['publication_date']} {x['reference_period']} emp={x['employment_rate']:.4f} unemp={x['unemployment_rate']:.4f}",flush=True)
        except Exception as e:
            # Current page may expose non-workbook links matching our broad discovery; archived official files must parse.
            errors.append({'url':meta['url'],'superseded_at':meta['superseded_at'],'error':repr(e)})
    # One publication per date. Duplicate/correction workbooks on same publication date: earliest archive version wins as first-published evidence.
    vintages.sort(key=lambda x:(x['publication_date'],x['superseded_at'] or '9999'))
    first_by_date={}
    for x in vintages:first_by_date.setdefault(x['publication_date'],x)
    vintages=list(first_by_date.values())
    release_dates=[x['publication_date'] for x in vintages]
    # Monthly history should be nearly continuous. We do not fabricate missing months.
    year_counts={str(y):sum(1 for d in release_dates if d.startswith(str(y))) for y in range(start.year,end.year+1)}
    anchor={x['publication_date']:x for x in vintages if x['publication_date'] in {'2021-05-18','2024-02-13','2026-02-17','2026-09-15'}}
    status='PASS' if len(vintages)>=100 and len(set(release_dates))==len(vintages) and len(anchor)>=3 else 'FAIL'
    out={
        'schema':'GMFQ_GBP_ONS_A01_LABOUR_PIT_VINTAGES_V1','status':status,'currency':'GBP','block':'Labour',
        'coverage_requested':{'start':args.start,'end':args.end},'vintage_count':len(vintages),'year_counts':year_counts,
        'method':'Official ONS A01 archived workbooks. Each workbook is read as published on its internal Date of publication. Headline unemployment uses MGSX; headline employment rate age 16-64 uses LF24; the last valid period row is retained from that vintage.',
        'pit_semantics':'No current revised history is substituted. If ONS has multiple later supersessions/corrections, one row per workbook publication date is retained; for duplicate publication dates, the earliest archived vintage is used as first-published evidence.',
        'anchors':anchor,'vintages':vintages,'parse_errors':errors,
        'guardrails':{'read_only_source_build':True,'uses_current_revised_timeseries_for_values':False,'live_data_modified':False,'model_rules_modified':False,'rules_fingerprint_expected_unchanged':'3356baf0'}
    }
    Path(args.output).write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'status':status,'vintage_count':len(vintages),'year_counts':year_counts,'anchors':anchor,'error_count':len(errors)},indent=2),flush=True)
    if status!='PASS':raise SystemExit(1)

if __name__=='__main__':main()
