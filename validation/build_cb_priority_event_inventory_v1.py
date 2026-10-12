#!/usr/bin/env python3
from __future__ import annotations

import argparse, html, json, re, urllib.parse, urllib.request
from collections import Counter
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path

UA='GMFQ-research/1.0 official-central-bank-source-inventory'
YEARS=range(2018,2027)
ALLOWED_DOMAINS={'FED':'federalreserve.gov','ECB':'ecb.europa.eu','BOJ':'boj.or.jp','BOC':'bankofcanada.ca','RBA':'rba.gov.au'}

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self._href=None; self._txt=[]
    def handle_starttag(self,tag,attrs):
        if tag.lower()=='a': self._href=dict(attrs).get('href'); self._txt=[]
    def handle_data(self,data):
        if self._href is not None: self._txt.append(data)
    def handle_endtag(self,tag):
        if tag.lower()=='a' and self._href is not None:
            self.links.append((self._href,' '.join(''.join(self._txt).split())))
            self._href=None; self._txt=[]

def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA})
    with urllib.request.urlopen(req,timeout=45) as r: return r.read().decode('utf-8','ignore')

def links(url):
    p=LinkParser(); p.feed(get(url)); return [(urllib.parse.urljoin(url,h),t) for h,t in p.links if h]

def official(cb,url):
    host=urllib.parse.urlparse(url).netloc.lower().split(':')[0]; dom=ALLOWED_DOMAINS[cb]
    return host==dom or host.endswith('.'+dom)

def iso_from_url_or_text(url,text):
    blob=html.unescape(url+' '+text)
    for p in [r'(?<!\d)(20(?:1[8-9]|2[0-6]))[-_/](0[1-9]|1[0-2])[-_/]([0-3]\d)(?!\d)',r'(?<!\d)(20(?:1[8-9]|2[0-6]))(0[1-9]|1[0-2])([0-3]\d)(?!\d)']:
        m=re.search(p,blob)
        if m:
            try:return date(*map(int,m.groups())).isoformat()
            except ValueError:pass
    # BOJ filenames such as k180123a.pdf.
    m=re.search(r'/[a-z](\d{2})(\d{2})(\d{2})[a-z]?\.(?:pdf|htm|html)',blob,re.I)
    if m:
        try:return date(2000+int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()
        except ValueError:pass
    months={'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,'july':7,'august':8,'september':9,'october':10,'november':11,'december':12,
            'jan':1,'feb':2,'mar':3,'apr':4,'jun':6,'jul':7,'aug':8,'sep':9,'sept':9,'oct':10,'nov':11,'dec':12}
    # Month day, year.
    m=re.search(r'(?i)(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\.?\s+([0-3]?\d),?\s+(20(?:1[8-9]|2[0-6]))',blob)
    if m:
        try:return date(int(m.group(3)),months[m.group(1).lower()],int(m.group(2))).isoformat()
        except ValueError:pass
    # Day month year (RBA/BOJ archive style).
    m=re.search(r'(?i)([0-3]?\d)\s+(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\.?[,]?\s+(20(?:1[8-9]|2[0-6]))',blob)
    if m:
        try:return date(int(m.group(3)),months[m.group(2).lower()],int(m.group(1))).isoformat()
        except ValueError:pass
    return None

def next_day(ds): return (date.fromisoformat(ds)+timedelta(days=1)).isoformat()
def row(cb,ds,url,doctype,timestamp=None,prov='UNKNOWN_TIME_NEXT_CALENDAR_DAY'):
    assert official(cb,url),(cb,url)
    return {'central_bank':cb,'decision_date':ds,'source_url':url,'source_document_type':doctype,'official_domain_verified':True,
            'publication_timestamp':timestamp or (next_day(ds)+'T00:00:00'),'timestamp_provenance':prov,
            'inventory_status':'INVENTORIED_OFFICIAL_DOCUMENT'}

def fed():
    out=[]
    for y in YEARS:
        u='https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm' if y==2026 else f'https://www.federalreserve.gov/monetarypolicy/fomchistorical{y}.htm'
        try: ls=links(u)
        except Exception: continue
        for v,t in ls:
            low=(v+' '+t).lower()
            if 'statement' not in low or not official('FED',v): continue
            ds=iso_from_url_or_text(v,t)
            if not ds or not ds.startswith(str(y)) or ds>'2026-10-12': continue
            out.append(row('FED',ds,v,'FOMC_STATEMENT'))
    return out

def xml_locs(url):
    txt=get(url)
    return [html.unescape(x.strip()) for x in re.findall(r'<loc>\s*(.*?)\s*</loc>',txt,re.I|re.S)]

def sitemap_expand(root, wanted, max_children=120):
    """Result-blind URL discovery only; never reads document economics."""
    seen=set(); out=[]
    try:first=xml_locs(root)
    except Exception:return out
    q=list(first)
    nchild=0
    while q:
        u=q.pop(0)
        if u in seen: continue
        seen.add(u)
        if wanted(u): out.append(u); continue
        if (u.endswith('.xml') or 'sitemap' in u.lower()) and nchild<max_children:
            nchild+=1
            try:q.extend(xml_locs(u))
            except Exception:pass
    return out

def ecb():
    # The visible archive is JS-backed; use the official ECB sitemap to discover the immutable press-release URLs.
    urls=sitemap_expand('https://www.ecb.europa.eu/sitemap.xml', lambda u: bool(re.search(r'/press/pr/date/20(?:1[8-9]|2[0-6])/html/ecb\.mp',u,re.I)) and '.en.' in u.lower())
    out=[]
    for v in urls:
        if not official('ECB',v): continue
        ds=iso_from_url_or_text(v,'')
        if not ds or not ('2018-01-01'<=ds<='2026-10-12'):continue
        out.append(row('ECB',ds,v,'MONETARY_POLICY_DECISIONS',ds+'T14:15:00','OFFICIAL_ARCHIVE_STANDARD_14_15_LOCAL'))
    return out

def boj():
    out=[]
    for y in YEARS:
        u=f'https://www.boj.or.jp/en/mopo/mpmdeci/state_{y}/index.htm'
        try:ls=links(u)
        except Exception:continue
        for v,t in ls:
            low=(v+' '+t).lower()
            if not official('BOJ',v):continue
            if 'statement on monetary policy' not in low and 'strengthening the framework for continuous powerful monetary easing' not in low:continue
            ds=iso_from_url_or_text(v,t)
            if not ds:
                try: ds=iso_from_url_or_text(v,re.sub('<[^>]+>',' ',get(v)[:50000]))
                except Exception: ds=None
            if not ds or not ds.startswith(str(y)) or ds>'2026-10-12':continue
            out.append(row('BOJ',ds,v,'STATEMENT_ON_MONETARY_POLICY'))
    return out

def rba():
    out=[]
    for y in YEARS:
        u=f'https://www.rba.gov.au/media-releases/{y}/'
        try:ls=links(u)
        except Exception:continue
        for v,t in ls:
            if not official('RBA',v) or 'monetary policy decision' not in (v+' '+t).lower():continue
            try: body=get(v)
            except Exception:continue
            ds=iso_from_url_or_text(v,re.sub('<[^>]+>',' ',body[:120000]))
            if not ds or not ds.startswith(str(y)) or ds>'2026-10-12':continue
            out.append(row('RBA',ds,v,'MONETARY_POLICY_DECISION'))
    return out

def boc():
    # Prefer official sitemap discovery of fixed-announcement releases; retain archive crawl as a conservative fallback.
    urls=sitemap_expand('https://www.bankofcanada.ca/sitemap_index.xml',lambda u:'fad-press-release-' in u.lower(),max_children=180)
    out=[]
    for v in urls:
        if not official('BOC',v):continue
        ds=iso_from_url_or_text(v,'')
        if ds and '2018-01-01'<=ds<='2026-10-12':out.append(row('BOC',ds,v,'FIXED_ANNOUNCEMENT_DATE_RATE_DECISION'))
    if len(out)<50:
        for y in YEARS:
            for page in range(1,12):
                u=f'https://www.bankofcanada.ca/{y}/?content_type=press-releases&page={page}'
                try:ls=links(u)
                except Exception:break
                for v,t in ls:
                    if not official('BOC',v) or 'fad-press-release-' not in v.lower():continue
                    ds=iso_from_url_or_text(v,t)
                    if ds and ds.startswith(str(y)) and ds<='2026-10-12':out.append(row('BOC',ds,v,'FIXED_ANNOUNCEMENT_DATE_RATE_DECISION'))
    return out

def dedup(rows):
    d={}
    for r in sorted(rows,key=lambda x:(x['central_bank'],x['decision_date'],x['source_url'])):d.setdefault((r['central_bank'],r['decision_date']),r)
    return list(d.values())

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);a=ap.parse_args()
    all_rows=[];errors={}
    for cb,fn in [('FED',fed),('ECB',ecb),('BOJ',boj),('BOC',boc),('RBA',rba)]:
        try:rr=fn();all_rows.extend(rr);errors[cb]=None
        except Exception as e:errors[cb]=repr(e)
    rows=dedup(all_rows);counts=Counter(r['central_bank'] for r in rows)
    all5=all(errors[x] is None for x in errors) and set(counts)==set(ALLOWED_DOMAINS)
    out={'schema':'GMFQ_CB_PRIORITY_DECISION_EVENT_INVENTORY_V1','status':'RESULT_BLIND_EVENT_INVENTORY_COMPLETE' if all5 else 'RESULT_BLIND_EVENT_INVENTORY_PARTIAL',
         'as_of':'2026-10-12','history_start':'2018-01-01','counts_by_central_bank':dict(sorted(counts.items())),'source_errors':errors,
         'events':sorted(rows,key=lambda r:(r['decision_date'],r['central_bank'])),'focus_labels_present':False,'performance_data_present':False,
         'labeling_authorized':False,'performance_test_authorized':False,'production_signal_authorized':False,'sizing_authorized':False}
    Path(a.output).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':out['status'],'counts':out['counts_by_central_bank'],'errors':errors},indent=2,sort_keys=True))
if __name__=='__main__':main()
