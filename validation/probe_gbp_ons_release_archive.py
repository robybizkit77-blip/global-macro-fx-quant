#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

OUT = Path('/tmp/gmfq-gbp-ons-pit/archive_probe.json')
UA = 'global-macro-fx-quant/1.0'

FAMILIES = {
    'production': {
        'runtime_ids': ['UK_PRODUCTION_history_value'],
        'latest': 'https://www.ons.gov.uk/economy/economicoutputandproductivity/output/bulletins/indexofproduction/latest',
    },
    'retail': {
        'runtime_ids': ['UK_RETAIL_VOL_history_value'],
        'latest': 'https://www.ons.gov.uk/businessindustryandtrade/retailindustry/bulletins/retailsales/latest',
    },
    'labour_market': {
        'runtime_ids': ['UK_UNEMP_RATE_history_value', 'UK_EMPLOYMENT_RATE_history_value'],
        'latest': 'https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/bulletins/uklabourmarket/latest',
    },
    'paye': {
        'runtime_ids': ['UK_PAYE_PAYROLLED_EMPLOYEES_SA_history_value'],
        'latest': 'https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/bulletins/earningsandemploymentfrompayasyouearnrealtimeinformationuk/latest',
    },
}

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]
    def handle_starttag(self, tag, attrs):
        if tag.lower()!='a': return
        d=dict(attrs); href=d.get('href')
        if href: self.links.append(href)

def fetch(url: str) -> tuple[str, str]:
    req=urllib.request.Request(url, headers={'User-Agent':UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.geturl(), r.read().decode('utf-8','replace')

def archive_url_from_latest(final_url: str, html: str) -> str:
    p=Links(); p.feed(html)
    candidates=[]
    for href in p.links:
        low=href.lower()
        if 'previousreleases' in low or 'previous-releases' in low:
            candidates.append(urljoin(final_url, href))
    if candidates:
        return sorted(set(candidates), key=len)[0]
    base=final_url.rstrip('/')
    if base.endswith('/latest'):
        return base[:-7] + '/previousreleases'
    return base + '/previousreleases'

def parse_archive(url: str, html: str) -> list[dict]:
    p=Links(); p.feed(html)
    rows=[]; seen=set()
    date_re=re.compile(r'/(\d{1,2}[a-z]+\d{4})(?:/|$)', re.I)
    for href in p.links:
        full=urljoin(url,href)
        m=date_re.search(full)
        if not m: continue
        if full in seen: continue
        seen.add(full)
        rows.append({'url':full,'slug_date':m.group(1)})
    return rows

def main():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    result={'schema':'GMFQ_GBP_ONS_PIT_ARCHIVE_PROBE_V1','status':'PASS','families':{},'guardrails':{
        'read_only':True,'live_data_modified':False,'model_rules_modified':False,'rules_fingerprint_expected_unchanged':'3356baf0'
    }}
    all_ok=True
    for name,cfg in FAMILIES.items():
        try:
            final,html=fetch(cfg['latest'])
            archive=archive_url_from_latest(final,html)
            af,ah=fetch(archive)
            releases=parse_archive(af,ah)
            recent=[r for r in releases if any(str(y) in r['slug_date'] for y in range(2018,2027))]
            row={
                'runtime_ids':cfg['runtime_ids'],'latest_requested':cfg['latest'],'latest_final':final,
                'archive_url':af,'release_link_count':len(releases),'release_links_2018_2026':len(recent),
                'first_release_link':releases[0] if releases else None,'last_release_link':releases[-1] if releases else None,
                'pit_archive_discoverable':len(recent)>=8,
            }
            if not row['pit_archive_discoverable']: all_ok=False
        except Exception as e:
            row={'runtime_ids':cfg['runtime_ids'],'pit_archive_discoverable':False,'error':repr(e)}; all_ok=False
        result['families'][name]=row
    result['status']='PASS' if all_ok else 'FAIL'
    result['summary']={
        'families_total':len(FAMILIES),
        'families_archive_discoverable':sum(1 for x in result['families'].values() if x.get('pit_archive_discoverable')),
        'runtime_series_covered':sum(len(x['runtime_ids']) for x in FAMILIES.values()),
        'next_gate':'value-level first-release extraction from dated ONS release pages; current revised time-series API alone is not PIT evidence'
    }
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(result,indent=2,ensure_ascii=False))
    if not all_ok: raise SystemExit(1)

if __name__=='__main__': main()
