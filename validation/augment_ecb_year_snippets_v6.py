#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re,urllib.parse,urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

UA='GMFQ-research/1.0 result-blind-ecb-year-snippets'
BASE='https://www.ecb.europa.eu/press/govcdec/mopo/html/index.en.html'

class P(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]; self.h=None; self.buf=[]
    def handle_starttag(self,tag,attrs):
        if tag.lower()=='a': self.h=dict(attrs).get('href'); self.buf=[]
    def handle_data(self,d):
        if self.h is not None:self.buf.append(d)
    def handle_endtag(self,tag):
        if tag.lower()=='a' and self.h is not None:
            self.links.append((self.h,' '.join(''.join(self.buf).split()))); self.h=None; self.buf=[]

def get(u,timeout=20):
    q=urllib.request.Request(u,headers={'User-Agent':UA})
    with urllib.request.urlopen(q,timeout=timeout) as r:return r.read().decode('utf-8','ignore')

def parse_links(base,body):
    p=P();p.feed(body);return [(urllib.parse.urljoin(base,h),t) for h,t in p.links if h]

def mp_date(u):
    m=re.search(r'ecb\.mp(\d{2})(\d{2})(\d{2})',u,re.I)
    if not m:return None
    try:return date(2000+int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()
    except ValueError:return None

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    r=json.load(open(a.input));assert r['schema']=='GMFQ_CB_PRIORITY_DECISION_EVENT_INVENTORY_V1'

    shell=get(BASE)
    m=re.search(r"data-snippets=['\"]([^'\"]+)['\"]",shell,re.I)
    if not m: raise RuntimeError('ECB data-snippets attribute not found')
    snippet_specs=[x.strip() for x in m.group(1).split(',') if x.strip()]
    wanted=[]
    for spec in snippet_specs:
        u=urllib.parse.urljoin(BASE,spec)
        yr=re.search(r'/mopo/(20\d{2})/html/index_include\.en\.html',u)
        if yr and 2018<=int(yr.group(1))<=2026:wanted.append((int(yr.group(1)),u))
    if {y for y,_ in wanted}!={2018,2019,2020,2021,2022,2023,2024,2025,2026}:
        raise RuntimeError(f'ECB annual snippet coverage unexpected: {[y for y,_ in wanted]}')

    found={}; diagnostics={}
    for y,u in sorted(wanted):
        body=get(u)
        archive_links=[]
        for v,t in parse_links(u,body):
            host=urllib.parse.urlparse(v).netloc.lower()
            ds=mp_date(v)
            if not (host=='ecb.europa.eu' or host.endswith('.ecb.europa.eu')): continue
            if not re.search(r'/press/pr/date/20(?:1[8-9]|2[0-6])/html/ecb\.mp',v,re.I): continue
            if not ds or not ds.startswith(str(y)) or ds>'2026-10-12': continue
            # The official yearly monetary-policy archive is itself the semantic authority.
            # Require the archive anchor text to identify the release as Monetary policy decisions.
            if 'monetary policy decisions' not in t.lower(): continue
            archive_links.append((v,t,ds))
        for v,t,ds in archive_links:
            found.setdefault(ds,{
              'central_bank':'ECB','decision_date':ds,'source_url':v,
              'source_document_type':'MONETARY_POLICY_DECISIONS','official_domain_verified':True,
              'publication_timestamp':ds+'T14:15:00',
              'timestamp_provenance':'OFFICIAL_DECISION_DAY_STANDARD_14_15_LOCAL',
              'inventory_status':'INVENTORIED_OFFICIAL_DOCUMENT',
              'archive_evidence_title':t,
              'archive_index_url':u})
        diagnostics[str(y)]={'snippet_url':u,'bytes':len(body),'candidate_links':len(archive_links),'verified':len(archive_links)}

    rows=[x for x in r['events'] if x['central_bank']!='ECB'];rows.extend(found.values())
    d={}
    for x in sorted(rows,key=lambda z:(z['central_bank'],z['decision_date'],z['source_url'])):d.setdefault((x['central_bank'],x['decision_date']),x)
    rows=list(d.values());cbs=('FED','ECB','BOJ','BOC','RBA');counts={cb:sum(x['central_bank']==cb for x in rows) for cb in cbs}
    r['events']=sorted(rows,key=lambda x:(x['decision_date'],x['central_bank']))
    r['counts_by_central_bank']={k:v for k,v in counts.items() if v}
    r['source_errors']['ECB']=None if counts['ECB']>=50 else f'ECB_YEAR_SNIPPETS_COVERAGE_LT_50:{counts["ECB"]}'
    r['status']='RESULT_BLIND_EVENT_INVENTORY_COMPLETE' if all(counts[cb]>=50 for cb in cbs) and not any(r['source_errors'].values()) else 'RESULT_BLIND_EVENT_INVENTORY_PARTIAL'
    r['ecb_transport_receipt']={'source_shell':BASE,'mechanism':'official data-snippets annual include files','verification_transport':'official_archive_anchor_semantic_authority_v3','annual_diagnostics':diagnostics}
    assert r['focus_labels_present'] is False and r['performance_data_present'] is False
    Path(a.output).write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':r['status'],'counts':counts,'ecb_verified':len(found),'annual_diagnostics':diagnostics},indent=2,sort_keys=True))
if __name__=='__main__':main()
