#!/usr/bin/env python3
"""Probe period-specific CFTC Legacy Futures Only pages for publication metadata.

Read-only discovery. The goal is to determine whether historical report pages
encode actual release date/time in the source HTML. No PIT certification is
implied by a successful fetch.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import pathlib
import re
import urllib.request

UA='global-macro-fx-quant/cot-viewable-release-metadata-discovery-v1'
PROBES=[
    ('2019-02-05','https://www.cftc.gov/files/dea/cotarchives/2019/futures/deacmelf020519.htm'),
    ('2023-02-07','https://www.cftc.gov/files/dea/cotarchives/2023/futures/deacmelf020723.htm'),
    ('2025-01-07','https://www.cftc.gov/files/dea/cotarchives/2025/futures/deacmelf010725.htm'),
    ('2026-09-29','https://www.cftc.gov/files/dea/cotarchives/2026/futures/deacmelf092926.htm'),
]


def fetch(url:str)->bytes:
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*;q=0.8'})
    with urllib.request.urlopen(req,timeout=60) as r:
        raw=r.read()
        if r.status!=200: raise RuntimeError(f'HTTP {r.status}: {url}')
        return raw


def visible(raw:bytes)->str:
    text=raw.decode('latin-1',errors='replace')
    text=re.sub(r'<script\b.*?</script>',' ',text,flags=re.I|re.S)
    text=re.sub(r'<style\b.*?</style>',' ',text,flags=re.I|re.S)
    text=html.unescape(re.sub(r'<[^>]+>',' ',text))
    return re.sub(r'\s+',' ',text).strip()


def probe(report_date:str,url:str)->dict:
    raw=fetch(url); text=visible(raw)
    patterns=[
        r'(.{0,140}Release.{0,220})',
        r'(.{0,140}3:30\s*p\.?m\.?\s*Eastern.{0,220})',
        r'(.{0,140}published.{0,220})',
    ]
    snippets=[]
    for pattern in patterns:
        for m in re.finditer(pattern,text,flags=re.I):
            snippet=re.sub(r'\s+',' ',m.group(1)).strip()
            if snippet not in snippets: snippets.append(snippet)
    return {
        'report_date':report_date,'url':url,'bytes':len(raw),
        'sha256':hashlib.sha256(raw).hexdigest(),
        'title_identity_ok': report_date[-4:] in text or report_date[:4] in text,
        'release_metadata_snippets':snippets[:12],
        'contains_330_eastern':bool(re.search(r'3:30\s*p\.?m\.?\s*Eastern',text,re.I)),
        'contains_release_word':bool(re.search(r'\brelease\b',text,re.I)),
    }


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=pathlib.Path); args=ap.parse_args()
    rows=[]; errors=[]
    for d,u in PROBES:
        try: rows.append(probe(d,u))
        except Exception as exc: errors.append({'report_date':d,'url':u,'error':repr(exc)})
    out={
        'schema':'GMFQ_COT_VIEWABLE_RELEASE_METADATA_DISCOVERY_V1',
        'status':'DISCOVERY_PASS' if not errors else 'DISCOVERY_PARTIAL',
        'probes':rows,'errors':errors,
        'invariants':{'official_cftc_only':True,'read_only':True,'historical_pit_certified':False}
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(out,indent=2,sort_keys=True))
    return 0 if not errors else 2

if __name__=='__main__': raise SystemExit(main())
