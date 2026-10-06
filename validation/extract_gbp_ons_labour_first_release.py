#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

OUT = Path('/tmp/gmfq-gbp-ons-pit/labour_first_release.json')
ARCHIVE = 'https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/bulletins/uklabourmarket/previousreleases'
UA = 'global-macro-fx-quant/1.0 (+read-only PIT first-release validation)'
MONTHS = '(?:january|february|march|april|may|june|july|august|september|october|november|december)'
SLUG_RE = re.compile(rf'/({MONTHS}\d{{4}})(?:/|$|\?)', re.I)
RELEASE_DATE_RE = re.compile(r'Release date:\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})', re.I)
EMP_RE = re.compile(r'The UK employment rate[^.]{0,220}?was estimated at\s*([0-9]+(?:\.[0-9]+)?)%\s*(?:in|for)\s*([^.]+?)\.', re.I)
UNEMP_RE = re.compile(r'The UK unemployment rate[^.]{0,220}?was estimated at\s*([0-9]+(?:\.[0-9]+)?)%\s*(?:in|for)\s*([^.]+?)\.', re.I)

class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]
    def handle_starttag(self, tag, attrs):
        if tag.lower()=='a':
            href=dict(attrs).get('href')
            if href: self.links.append(href)

class Text(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]
    def handle_data(self,data):
        s=' '.join(data.split())
        if s: self.parts.append(s)
    def value(self): return ' '.join(self.parts)

def fetch(url: str, retries: int=5) -> tuple[str,str]:
    last=None
    for attempt in range(retries):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html'})
            with urllib.request.urlopen(req,timeout=45) as r:
                body=r.read().decode('utf-8','replace')
                time.sleep(1.1)
                return r.geturl(),body
        except urllib.error.HTTPError as e:
            last=e
            if e.code!=429 or attempt==retries-1: raise
            time.sleep(4*(attempt+1))
    raise last or RuntimeError('fetch failed')

def plain(html: str) -> str:
    p=Text(); p.feed(html); return unescape(p.value())

def archive_release_urls(limit: int=12) -> list[str]:
    urls=[]; seen=set()
    for page in range(1,5):
        url=ARCHIVE if page==1 else f'{ARCHIVE}?page={page}'
        final,html=fetch(url)
        p=Links(); p.feed(html)
        for href in p.links:
            full=urljoin(final,href).split('#')[0]
            path=urlparse(full).path
            if '/bulletins/uklabourmarket/' not in path: continue
            if not SLUG_RE.search(path): continue
            if full not in seen:
                seen.add(full); urls.append(full)
                if len(urls)>=limit: return urls
    return urls

def extract_release(url: str) -> dict:
    final,html=fetch(url)
    text=plain(html)
    rd=RELEASE_DATE_RE.search(text)
    emp=EMP_RE.search(text)
    unemp=UNEMP_RE.search(text)
    return {
        'url':final,
        'slug_period':SLUG_RE.search(urlparse(final).path).group(1).lower() if SLUG_RE.search(urlparse(final).path) else None,
        'release_date_text':rd.group(1) if rd else None,
        'employment_rate':float(emp.group(1)) if emp else None,
        'employment_reference_period':emp.group(2).strip() if emp else None,
        'unemployment_rate':float(unemp.group(1)) if unemp else None,
        'unemployment_reference_period':unemp.group(2).strip() if unemp else None,
        'first_release_source':'ONS dated Labour Market bulletin',
    }

def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    urls=archive_release_urls(12)
    rows=[extract_release(u) for u in urls]
    valid=[r for r in rows if r['release_date_text'] and r['employment_rate'] is not None and r['unemployment_rate'] is not None]
    unique_release_dates=len({r['release_date_text'] for r in valid})
    result={
        'schema':'GMFQ_GBP_ONS_LABOUR_FIRST_RELEASE_CONTRACT_V1',
        'status':'PASS' if len(valid)==12 and unique_release_dates==12 else 'FAIL',
        'runtime_series':{
            'UK_EMPLOYMENT_RATE_history_value':'employment_rate',
            'UK_UNEMP_RATE_history_value':'unemployment_rate',
        },
        'source':'Office for National Statistics dated Labour Market bulletins',
        'pit_policy':'value becomes available only on release_date; bulletin value is retained as first-published evidence and is not backfilled from revised time-series history',
        'release_count_requested':12,
        'release_count_parsed':len(valid),
        'unique_release_dates':unique_release_dates,
        'rows':rows,
        'guardrails':{
            'read_only':True,'live_data_modified':False,'model_rules_modified':False,
            'uses_revised_timeseries_api_for_values':False,'rules_fingerprint_expected_unchanged':'3356baf0'
        }
    }
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(result,indent=2,ensure_ascii=False))
    if result['status']!='PASS': raise SystemExit(1)

if __name__=='__main__': main()
