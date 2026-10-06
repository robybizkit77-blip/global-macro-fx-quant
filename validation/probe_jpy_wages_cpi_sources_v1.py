from __future__ import annotations
import json, re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

OUT = Path('validation/JPY_WAGES_CPI_SOURCE_PROBE_V1_2026-10-06.json')
START = (2018,1)
END = (2023,7)


def months(start=START, end=END):
    y,m=start
    out=[]
    while (y,m) <= end:
        out.append(f'{y:04d}-{m:02d}')
        m += 1
        if m == 13:
            y += 1; m = 1
    return out

TARGET = months()
S = requests.Session()
S.headers.update({'User-Agent':'GMFQ-PIT-source-audit/1.0'})


def get(url):
    r=S.get(url, timeout=30)
    return {'url':url,'status':r.status_code,'text':r.text if r.ok else ''}


def parse_mhlw():
    index='https://www.mhlw.go.jp/toukei/list/30-1a.html'
    res=get(index)
    found={}
    if res['status']==200:
        soup=BeautifulSoup(res['text'],'html.parser')
        for a in soup.find_all('a', href=True):
            txt=' '.join(a.stripped_strings)
            href=urljoin(index,a['href'])
            # Prefer official preliminary-result links. Infer month primarily from URL patterns.
            mo=re.search(r'/monthly/(?:30|31|r0[1-5])/(\d{4})p/', href)
            if mo and ('速報' in txt or href.endswith('p.html')):
                yy=int(mo.group(1)[:2]); mm=int(mo.group(1)[2:])
                if '/30/' in href: year=2018
                elif '/31/' in href: year=2019
                else:
                    era=re.search(r'/r0([1-5])/',href)
                    year=2018+int(era.group(1)) if era else None
                if year and 1 <= mm <= 12:
                    k=f'{year:04d}-{mm:02d}'
                    if k in TARGET:
                        found.setdefault(k,[]).append({'page_url':href,'anchor':txt})
    return {'index_url':index,'index_status':res['status'],'months_found':found,
            'coverage_count':sum(1 for m in TARGET if m in found),
            'missing_months':[m for m in TARGET if m not in found]}


def parse_cpi():
    # Official Statistics Bureau monthly report archive, containing links by CPI base/year.
    index='https://www.stat.go.jp/english/data/cpi/1588.htm'
    res=get(index)
    links=[]
    if res['status']==200:
        soup=BeautifulSoup(res['text'],'html.parser')
        for a in soup.find_all('a', href=True):
            href=urljoin(index,a['href'])
            txt=' '.join(a.stripped_strings)
            if 'cpi' in href.lower(): links.append({'url':href,'anchor':txt})

    # Also certify predictable historical monthly-report endpoints by requesting candidate PDF paths.
    # We do not extract values here; we only establish retrievability and source URLs.
    found={}
    candidates=[]
    for ym in TARGET:
        y,m=map(int,ym.split('-'))
        # Current archive pages have used zenkoku.pdf for the national monthly report.
        # Historic documents may be reachable via date-stamped or archived paths; probe search-friendly URLs first.
        urls=[
            f'https://www.stat.go.jp/data/cpi/sokuhou/tsuki/pdf/zenkoku.pdf',
        ]
        # A static current URL cannot prove vintage identity; retain it only as archive-index evidence, not a GREEN month.
        candidates.append({'month':ym,'candidate_urls':urls})

    return {'index_url':index,'index_status':res['status'],'archive_links_count':len(links),
            'archive_links_sample':links[:50],
            'coverage_count':0,
            'missing_months':TARGET,
            'note':'Static latest zenkoku.pdf is explicitly NOT accepted as vintage evidence. Month-level GREEN requires an immutable/month-specific official URL or archived first-release document.'}


def main():
    wages=parse_mhlw(); cpi=parse_cpi()
    obj={
      'schema':'GMFQ_JPY_WAGES_CPI_SOURCE_PROBE_V1',
      'created_at':'2026-10-06',
      'target_coverage':'2018-01 through 2023-07',
      'required_months':67,
      'wages_mhlw_preliminary':wages,
      'cpi_statistics_bureau_first_release':cpi,
      'status': 'SOURCE_PROBE_COMPLETE',
      'green_for_materialization': wages['coverage_count']==67 and cpi['coverage_count']==67,
      'guardrails':[
        'No revised-history substitution',
        'No current/latest static document used as historical vintage',
        'No value extraction until immutable month-specific official source coverage is certified',
        'No engine/live/OOS changes'
      ],
      'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False
    }
    OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'wages':wages['coverage_count'],'cpi':cpi['coverage_count'],'green':obj['green_for_materialization']}))

if __name__=='__main__': main()
