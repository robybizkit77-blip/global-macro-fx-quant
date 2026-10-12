#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re,urllib.parse,urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

UA='GMFQ-research/1.0 result-blind-ecb-statement-index'
INDEX='https://www.ecb.europa.eu/press/press_conference/monetary-policy-statement/html/index.en.html'

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
    req=urllib.request.Request(u,headers={'User-Agent':UA})
    with urllib.request.urlopen(req,timeout=60) as r:return r.read().decode('utf-8','ignore')

def mp_date(u):
    m=re.search(r'ecb\.mp(\d{2})(\d{2})(\d{2})',u,re.I)
    if not m:return None
    try:return date(2000+int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()
    except ValueError:return None

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    r=json.load(open(a.input)); assert r['schema']=='GMFQ_CB_PRIORITY_DECISION_EVENT_INVENTORY_V1'
    body=get(INDEX); p=P();p.feed(body)
    candidates=[]
    for h,t in p.links:
        u=urllib.parse.urljoin(INDEX,h or '')
        host=urllib.parse.urlparse(u).netloc.lower()
        if not (host=='ecb.europa.eu' or host.endswith('.ecb.europa.eu')):continue
        if re.search(r'/press/pr/date/20(?:1[8-9]|2[0-6])/html/ecb\.mp',u,re.I):
            candidates.append((u,t,'INDEX_ANCHOR'))
    # Defensive extraction for links emitted in data attributes/scripts.
    for h in re.findall(r'(/press/pr/date/20(?:1[8-9]|2[0-6])/html/ecb\.mp[^"\'<>\s]*?\.en\.html)',body,re.I):
        candidates.append((urllib.parse.urljoin(INDEX,h),'','INDEX_EMBEDDED_URL'))
    rows=[x for x in r['events'] if x['central_bank']!='ECB']
    found={}
    for u,t,prov in sorted(set(candidates)):
        ds=mp_date(u)
        if not ds or not ('2018-01-01'<=ds<='2026-10-12'):continue
        # Verify this is actually the decision press release, not another mp-prefixed document.
        try: txt=get(u)
        except Exception: continue
        plain=re.sub(r'<[^>]+>',' ',txt)
        if 'Monetary policy decisions' not in plain:continue
        found.setdefault(ds,{
          'central_bank':'ECB','decision_date':ds,'source_url':u,'source_document_type':'MONETARY_POLICY_DECISIONS',
          'official_domain_verified':True,'publication_timestamp':ds+'T14:15:00',
          'timestamp_provenance':'OFFICIAL_DECISION_DAY_STANDARD_14_15_LOCAL',
          'inventory_status':'INVENTORIED_OFFICIAL_DOCUMENT'})
    rows.extend(found.values())
    d={}
    for x in sorted(rows,key=lambda z:(z['central_bank'],z['decision_date'],z['source_url'])): d.setdefault((x['central_bank'],x['decision_date']),x)
    rows=list(d.values()); cbs=('FED','ECB','BOJ','BOC','RBA'); counts={cb:sum(x['central_bank']==cb for x in rows) for cb in cbs}
    r['events']=sorted(rows,key=lambda x:(x['decision_date'],x['central_bank']))
    r['counts_by_central_bank']={k:v for k,v in counts.items() if v}
    r['source_errors']['ECB']=None if counts['ECB']>=50 else f'ECB_STATEMENT_INDEX_COVERAGE_LT_50:{counts["ECB"]}'
    r['status']='RESULT_BLIND_EVENT_INVENTORY_COMPLETE' if all(counts[cb]>=50 for cb in cbs) and not any(r['source_errors'].values()) else 'RESULT_BLIND_EVENT_INVENTORY_PARTIAL'
    assert r['focus_labels_present'] is False and r['performance_data_present'] is False
    Path(a.output).write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':r['status'],'counts':counts,'ecb_candidates':len(candidates),'ecb_verified':len(found)},indent=2,sort_keys=True))
if __name__=='__main__':main()
