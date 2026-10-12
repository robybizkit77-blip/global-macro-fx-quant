#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, re, urllib.parse, urllib.request
from collections import Counter
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path

UA='GMFQ-research/1.0 official-central-bank-source-inventory'
YEARS=range(2018,2027)
ALLOWED_DOMAINS={
 'FED':'federalreserve.gov','ECB':'ecb.europa.eu','BOJ':'boj.or.jp','BOC':'bankofcanada.ca','RBA':'rba.gov.au'
}

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self._href=None; self._txt=[]
    def handle_starttag(self,tag,attrs):
        if tag.lower()=='a':
            self._href=dict(attrs).get('href'); self._txt=[]
    def handle_data(self,data):
        if self._href is not None: self._txt.append(data)
    def handle_endtag(self,tag):
        if tag.lower()=='a' and self._href is not None:
            self.links.append((self._href,' '.join(''.join(self._txt).split())))
            self._href=None; self._txt=[]

def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA})
    with urllib.request.urlopen(req,timeout=60) as r:
        return r.read().decode('utf-8','ignore')

def links(url):
    p=LinkParser(); p.feed(get(url));
    out=[]
    for h,t in p.links:
        if not h: continue
        out.append((urllib.parse.urljoin(url,h),t))
    return out

def official(cb,url):
    host=urllib.parse.urlparse(url).netloc.lower().split(':')[0]
    dom=ALLOWED_DOMAINS[cb]
    return host==dom or host.endswith('.'+dom)

def iso_from_url_or_text(url,text):
    blob=url+' '+text
    pats=[
      r'(?<!\d)(20(?:1[8-9]|2[0-6]))[-_/](0[1-9]|1[0-2])[-_/]([0-3]\d)(?!\d)',
      r'(?<!\d)(20(?:1[8-9]|2[0-6]))(0[1-9]|1[0-2])([0-3]\d)(?!\d)',
    ]
    for p in pats:
        m=re.search(p,blob)
        if m:
            y,mo,d=map(int,m.groups())
            try: return date(y,mo,d).isoformat()
            except ValueError: pass
    months={'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,'july':7,'august':8,'september':9,'october':10,'november':11,'december':12}
    m=re.search(r'(?i)(january|february|march|april|may|june|july|august|september|october|november|december)\s+([0-3]?\d),?\s+(20(?:1[8-9]|2[0-6]))',blob)
    if m:
        try:return date(int(m.group(3)),months[m.group(1).lower()],int(m.group(2))).isoformat()
        except ValueError: pass
    return None

def next_day(ds): return (date.fromisoformat(ds)+timedelta(days=1)).isoformat()

def row(cb,ds,url,doctype,timestamp=None,prov='UNKNOWN_TIME_NEXT_CALENDAR_DAY'):
    assert official(cb,url),(cb,url)
    return {
      'central_bank':cb,'decision_date':ds,
      'source_url':url,'source_document_type':doctype,
      'official_domain_verified':True,
      'publication_timestamp': timestamp or (next_day(ds)+'T00:00:00'),
      'timestamp_provenance':prov if not timestamp else prov,
      'inventory_status':'INVENTORIED_OFFICIAL_DOCUMENT',
    }

def fed():
    out=[]
    for y in YEARS:
        u=f'https://www.federalreserve.gov/monetarypolicy/fomchistorical{y}.htm'
        for v,t in links(u):
            low=(v+' '+t).lower()
            if 'statement' not in low: continue
            if not official('FED',v): continue
            ds=iso_from_url_or_text(v,t)
            if not ds or not ds.startswith(str(y)): continue
            out.append(row('FED',ds,v,'FOMC_STATEMENT'))
    return out

def ecb():
    # Decision archive is chronological and its decision links carry dates in official URLs.
    u='https://www.ecb.europa.eu/press/govcdec/mopo/html/index.en.html'
    out=[]
    for v,t in links(u):
        low=(v+' '+t).lower()
        if not official('ECB',v): continue
        if not any(k in low for k in ('monetary policy decision','monetary policy decisions','ecb.mp')): continue
        ds=iso_from_url_or_text(v,t)
        if not ds or not ('2018-01-01'<=ds<='2026-10-12'): continue
        # ECB archive documents standard decision publication at 14:15 local time; store conservative UTC-neutral local marker.
        out.append(row('ECB',ds,v,'MONETARY_POLICY_DECISIONS',ds+'T14:15:00','OFFICIAL_ARCHIVE_STANDARD_14_15_LOCAL'))
    return out

def boj():
    out=[]
    for y in YEARS:
        u=f'https://www.boj.or.jp/en/mopo/mpmdeci/state_{y}/index.htm'
        for v,t in links(u):
            low=(v+' '+t).lower()
            if not official('BOJ',v): continue
            if 'statement on monetary policy' not in low and '/mopo/mpmdeci/' not in v.lower(): continue
            ds=iso_from_url_or_text(v,t)
            if not ds or not ds.startswith(str(y)): continue
            out.append(row('BOJ',ds,v,'STATEMENT_ON_MONETARY_POLICY'))
    return out

def rba():
    out=[]
    for y in YEARS:
        u=f'https://www.rba.gov.au/media-releases/{y}/'
        for v,t in links(u):
            low=(v+' '+t).lower()
            if not official('RBA',v) or 'monetary policy decision' not in low: continue
            # Release URLs do not consistently encode the date; fetch the release and use its official page text/meta.
            body=get(v)
            ds=iso_from_url_or_text(v, re.sub('<[^>]+>',' ',body[:120000]))
            if not ds or not ds.startswith(str(y)): continue
            out.append(row('RBA',ds,v,'MONETARY_POLICY_DECISION'))
    return out

def boc():
    # Use official site search pages by year and FAD URL pattern; final source URLs are official decision releases.
    out=[]
    for y in YEARS:
        for page in range(1,8):
            u=f'https://www.bankofcanada.ca/{y}/?content_type=press-releases&page={page}'
            try: ls=links(u)
            except Exception: break
            found=0
            for v,t in ls:
                low=(v+' '+t).lower()
                if not official('BOC',v): continue
                if 'fad-press-release-' not in v.lower() and 'policy interest rate' not in low and 'maintains overnight rate' not in low and 'raises overnight rate' not in low and 'lowers overnight rate' not in low: continue
                ds=iso_from_url_or_text(v,t)
                if not ds or not ds.startswith(str(y)): continue
                out.append(row('BOC',ds,v,'FIXED_ANNOUNCEMENT_DATE_RATE_DECISION'))
                found+=1
            if page>1 and found==0: break
    return out

def dedup(rows):
    # exactly one primary decision document per CB/date; deterministic URL choice.
    d={}
    for r in sorted(rows,key=lambda x:(x['central_bank'],x['decision_date'],x['source_url'])):
        k=(r['central_bank'],r['decision_date'])
        d.setdefault(k,r)
    return list(d.values())

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True); a=ap.parse_args()
    all_rows=[]
    errors={}
    for cb,fn in [('FED',fed),('ECB',ecb),('BOJ',boj),('BOC',boc),('RBA',rba)]:
        try: rr=fn(); all_rows.extend(rr); errors[cb]=None
        except Exception as e: errors[cb]=repr(e)
    rows=dedup(all_rows)
    counts=Counter(r['central_bank'] for r in rows)
    out={
      'schema':'GMFQ_CB_PRIORITY_DECISION_EVENT_INVENTORY_V1',
      'status':'RESULT_BLIND_EVENT_INVENTORY_COMPLETE' if all(errors[x] is None for x in errors) else 'RESULT_BLIND_EVENT_INVENTORY_PARTIAL',
      'as_of':'2026-10-12','history_start':'2018-01-01',
      'counts_by_central_bank':dict(sorted(counts.items())),
      'source_errors':errors,
      'events':sorted(rows,key=lambda r:(r['decision_date'],r['central_bank'])),
      'focus_labels_present':False,
      'performance_data_present':False,
      'labeling_authorized':False,
      'performance_test_authorized':False,
      'production_signal_authorized':False,
      'sizing_authorized':False,
    }
    Path(a.output).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':out['status'],'counts':out['counts_by_central_bank'],'errors':errors},indent=2,sort_keys=True))
if __name__=='__main__': main()
