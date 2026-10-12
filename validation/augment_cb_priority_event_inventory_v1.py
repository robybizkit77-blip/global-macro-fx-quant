#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re,urllib.parse,urllib.request
from datetime import date,timedelta
from html.parser import HTMLParser
from pathlib import Path

UA='GMFQ-research/1.0 official-central-bank-source-inventory'

class P(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]; self.h=None; self.t=[]
    def handle_starttag(self,tag,attrs):
        if tag.lower()=='a': self.h=dict(attrs).get('href'); self.t=[]
    def handle_data(self,d):
        if self.h is not None:self.t.append(d)
    def handle_endtag(self,tag):
        if tag.lower()=='a' and self.h is not None:
            self.links.append((self.h,' '.join(''.join(self.t).split()))); self.h=None; self.t=[]

def get(u):
    q=urllib.request.Request(u,headers={'User-Agent':UA})
    with urllib.request.urlopen(q,timeout=45) as r:return r.read().decode('utf-8','ignore')
def links(u):
    p=P();p.feed(get(u));return [(urllib.parse.urljoin(u,h),t) for h,t in p.links if h]
def ds(u):
    m=re.search(r'(20(?:1[8-9]|2[0-6]))[-_/]?(0[1-9]|1[0-2])[-_/]?([0-3]\d)',u)
    if not m:return None
    try:return date(*map(int,m.groups())).isoformat()
    except ValueError:return None
def row(cb,d,u,typ):
    return {'central_bank':cb,'decision_date':d,'source_url':u,'source_document_type':typ,'official_domain_verified':True,
            'publication_timestamp':(date.fromisoformat(d)+timedelta(days=1)).isoformat()+'T00:00:00',
            'timestamp_provenance':'UNKNOWN_TIME_NEXT_CALENDAR_DAY','inventory_status':'INVENTORIED_OFFICIAL_DOCUMENT'}

def fed():
    out=[]
    # 2018-2020 use historical pages; 2021 onward lives on the unified official calendar.
    urls=[f'https://www.federalreserve.gov/monetarypolicy/fomchistorical{y}.htm' for y in range(2018,2021)]
    urls.append('https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm')
    for base in urls:
        for u,t in links(base):
            low=u.lower()
            if 'federalreserve.gov' not in urllib.parse.urlparse(u).netloc.lower():continue
            if not (('pressreleases/monetary' in low or '/monetarypolicy/' in low) and ('statement' in low or t.strip().lower()=='html')):continue
            d=ds(u)
            if not d or not ('2018-01-01'<=d<='2026-10-12'):continue
            # Require immutable FOMC statement URL family, not strategy statements or implementation notes.
            if 'pressreleases/monetary' not in low and 'fomcstatement' not in low:continue
            out.append(row('FED',d,u,'FOMC_STATEMENT'))
    return out

def boc():
    out=[]
    # Official WordPress archive pages contain immutable FAD decision URLs. Scan all yearly pages without early stopping.
    for y in range(2018,2027):
        for page in range(1,31):
            u=f'https://www.bankofcanada.ca/{y}/?content_type=press-releases&page={page}'
            try: body=get(u)
            except Exception: continue
            candidates=set(re.findall(r'https?://(?:www\.)?bankofcanada\.ca/20(?:1[8-9]|2[0-6])/[01]\d/(?:fad-)?press-release-20(?:1[8-9]|2[0-6])-[01]\d-[0-3]\d/?',body,re.I))
            candidates.update(urllib.parse.urljoin(u,h) for h,_ in links_from_body(u,body) if 'press-release-' in h.lower())
            for v in candidates:
                if 'bankofcanada.ca' not in urllib.parse.urlparse(v).netloc.lower():continue
                d=ds(v)
                if not d or not d.startswith(str(y)) or d>'2026-10-12':continue
                # FAD is canonical; 2020 emergency decisions used press-release-YYYY-MM-DD and are retained as policy decisions.
                if 'fad-press-release-' not in v.lower() and not (d.startswith('2020-03-') and 'press-release-' in v.lower()):continue
                out.append(row('BOC',d,v,'FIXED_OR_EMERGENCY_RATE_DECISION'))
    return out

def links_from_body(base,body):
    p=P();p.feed(body);return [(urllib.parse.urljoin(base,h),t) for h,t in p.links if h]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    r=json.load(open(a.input)); assert r['schema']=='GMFQ_CB_PRIORITY_DECISION_EVENT_INVENTORY_V1'
    rows=list(r['events'])
    for cb,fn in [('FED',fed),('BOC',boc)]:
        try: rows.extend(fn()); r['source_errors'][cb]=None
        except Exception as e:r['source_errors'][cb]=repr(e)
    d={}
    for x in sorted(rows,key=lambda z:(z['central_bank'],z['decision_date'],z['source_url'])):d.setdefault((x['central_bank'],x['decision_date']),x)
    rows=list(d.values()); counts={cb:sum(1 for x in rows if x['central_bank']==cb) for cb in ('FED','ECB','BOJ','BOC','RBA')}
    r['events']=sorted(rows,key=lambda x:(x['decision_date'],x['central_bank']));r['counts_by_central_bank']={k:v for k,v in counts.items() if v}
    r['status']='RESULT_BLIND_EVENT_INVENTORY_COMPLETE' if all(counts.values()) and not any(r['source_errors'].values()) else 'RESULT_BLIND_EVENT_INVENTORY_PARTIAL'
    assert r['focus_labels_present'] is False and r['performance_data_present'] is False
    Path(a.output).write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':r['status'],'counts':counts,'errors':r['source_errors']},indent=2,sort_keys=True))
if __name__=='__main__':main()
