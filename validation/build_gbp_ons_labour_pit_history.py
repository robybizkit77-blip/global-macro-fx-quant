#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

ARCHIVE='https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/bulletins/uklabourmarket/previousreleases'
UA='global-macro-fx-quant/1.0 (+read-only PIT history validation)'
MONTHS='(?:january|february|march|april|may|june|july|august|september|october|november|december)'
SLUG_RE=re.compile(rf'/({MONTHS}\d{{4}})(?:/|$|\?)',re.I)
RELEASE_DATE_RE=re.compile(r'Release date:\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})',re.I)
CURRENT_EMP_RE=re.compile(r'The UK employment rate[^.]{0,240}?was estimated at\s*([0-9]+(?:\.[0-9]+)?)%\s*(?:in|for)\s*([^.]+?)\.',re.I)
CURRENT_UNEMP_RE=re.compile(r'The UK unemployment rate[^.]{0,240}?was estimated at\s*([0-9]+(?:\.[0-9]+)?)%\s*(?:in|for)\s*([^.]+?)\.',re.I)
OLD_EMP_RE=re.compile(r'the estimated employment rate for all people was\s*([0-9]+(?:\.[0-9]+)?)%',re.I)
OLD_UNEMP_RE=re.compile(r'the estimated UK unemployment rate for all people was\s*([0-9]+(?:\.[0-9]+)?)%',re.I)
PERIOD_BEFORE_RE=re.compile(r'For\s+([A-Za-z]+(?:\s+to\s+[A-Za-z]+)?\s+\d{4}|[A-Za-z]+\s+\d{4}\s+to\s+[A-Za-z]+\s+\d{4}):',re.I)

class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag.lower()=='a':
            href=dict(attrs).get('href')
            if href:self.links.append(href)
class Text(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]
    def handle_data(self,data):
        s=' '.join(data.split())
        if s:self.parts.append(s)
    def value(self):return ' '.join(self.parts)

def fetch(url,retries=6):
    last=None
    for attempt in range(retries):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html'})
            with urllib.request.urlopen(req,timeout=45) as r:
                body=r.read().decode('utf-8','replace')
                time.sleep(0.8)
                return r.geturl(),body
        except urllib.error.HTTPError as e:
            last=e
            if e.code!=429 or attempt==retries-1:raise
            time.sleep(3*(attempt+1))
    raise last or RuntimeError('fetch failed')

def plain(html):
    p=Text();p.feed(html);return unescape(p.value())

def slug_dt(slug):
    return datetime.strptime(slug,'%B%Y')

def release_urls(start_slug,end_slug):
    start_dt=slug_dt(start_slug.title());end_dt=slug_dt(end_slug.title())
    rows=[];seen=set();empty_pages=0
    for page in range(1,20):
        url=ARCHIVE if page==1 else f'{ARCHIVE}?page={page}'
        final,html=fetch(url);p=Links();p.feed(html);found=0
        for href in p.links:
            full=urljoin(final,href).split('#')[0];path=urlparse(full).path;m=SLUG_RE.search(path)
            if not m or '/bulletins/uklabourmarket/' not in path:continue
            slug=m.group(1).lower();dt=slug_dt(slug.title())
            if end_dt<=dt<=start_dt and full not in seen:
                seen.add(full);rows.append((dt,slug,full));found+=1
        if found==0:empty_pages+=1
        else:empty_pages=0
        if rows and min(x[0] for x in rows)<=end_dt and empty_pages>=1:break
        if empty_pages>=3:break
    rows.sort(reverse=True)
    return [{'slug_period':slug,'url':url} for _,slug,url in rows]

def nearest_period(text,pos):
    window=text[max(0,pos-500):pos]
    matches=list(PERIOD_BEFORE_RE.finditer(window))
    return matches[-1].group(1).strip() if matches else None

def extract(url,slug):
    final,html=fetch(url);text=plain(html)
    rd=RELEASE_DATE_RE.search(text)
    emp=CURRENT_EMP_RE.search(text);unemp=CURRENT_UNEMP_RE.search(text)
    method='headline_current'
    if not emp:
        e=OLD_EMP_RE.search(text)
        if e:
            emp_value=float(e.group(1));emp_period=nearest_period(text,e.start());method='legacy_all_people'
        else:emp_value=emp_period=None
    else:emp_value=float(emp.group(1));emp_period=emp.group(2).strip()
    if not unemp:
        u=OLD_UNEMP_RE.search(text)
        if u:
            unemp_value=float(u.group(1));unemp_period=nearest_period(text,u.start());method=method+'+legacy_unemp'
        else:unemp_value=unemp_period=None
    else:unemp_value=float(unemp.group(1));unemp_period=unemp.group(2).strip()
    release_date=rd.group(1) if rd else None
    release_iso=datetime.strptime(release_date,'%d %B %Y').date().isoformat() if release_date else None
    return {'url':final,'slug_period':slug,'release_date':release_iso,'release_date_text':release_date,
            'employment_rate':emp_value,'employment_reference_period':emp_period,
            'unemployment_rate':unemp_value,'unemployment_reference_period':unemp_period,
            'parse_method':method}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--start',default='september2026');ap.add_argument('--end',default='august2020');ap.add_argument('--output',required=True);args=ap.parse_args()
    urls=release_urls(args.start,args.end);rows=[]
    for i,r in enumerate(urls,1):
        x=extract(r['url'],r['slug_period']);rows.append(x);print(f"{i}/{len(urls)} {x['slug_period']} {x['release_date']} emp={x['employment_rate']} unemp={x['unemployment_rate']}",flush=True)
    valid=[r for r in rows if r['release_date'] and r['employment_rate'] is not None and r['unemployment_rate'] is not None and r['employment_reference_period'] and r['unemployment_reference_period']]
    release_dates=[r['release_date'] for r in valid]
    result={'schema':'GMFQ_GBP_ONS_LABOUR_PIT_HISTORY_V1','status':'PASS' if len(valid)==len(rows) and len(rows)>=70 and len(set(release_dates))==len(rows) else 'FAIL',
            'currency':'GBP','block':'Labour','source':'Office for National Statistics dated UK Labour Market bulletins',
            'coverage_requested':{'start':args.start,'end':args.end},'release_count':len(rows),'valid_release_count':len(valid),
            'runtime_series':{'UK_EMPLOYMENT_RATE_history_value':'employment_rate','UK_UNEMP_RATE_history_value':'unemployment_rate'},
            'pit_policy':'Each value is available only from its bulletin release_date. Values are first-published bulletin evidence; no revised ONS time-series values are substituted.',
            'rows':rows,'guardrails':{'read_only_source_build':True,'uses_revised_timeseries_api_for_values':False,'live_data_modified':False,'model_rules_modified':False,'rules_fingerprint_expected_unchanged':'3356baf0'}}
    Path(args.output).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'status':result['status'],'release_count':len(rows),'valid':len(valid),'first':rows[0] if rows else None,'last':rows[-1] if rows else None},indent=2),flush=True)
    if result['status']!='PASS':raise SystemExit(1)
if __name__=='__main__':main()
