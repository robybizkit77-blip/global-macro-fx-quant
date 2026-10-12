#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re,urllib.parse,urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

UA='GMFQ-research/1.0 result-blind-ecb-statement-traversal'
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
    q=urllib.request.Request(u,headers={'User-Agent':UA})
    with urllib.request.urlopen(q,timeout=60) as r:return r.read().decode('utf-8','ignore')

def parse_links(base,body):
    p=P();p.feed(body); return [(urllib.parse.urljoin(base,h),t) for h,t in p.links if h]

def event_date_from_url(u,prefix):
    m=re.search(rf'ecb\.{prefix}(\d{{2}})(\d{{2}})(\d{{2}})',u,re.I)
    if not m:return None
    try:return date(2000+int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()
    except ValueError:return None

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    r=json.load(open(a.input)); assert r['schema']=='GMFQ_CB_PRIORITY_DECISION_EVENT_INVENTORY_V1'
    body=get(INDEX)
    statements=[]
    for u,t in parse_links(INDEX,body):
        host=urllib.parse.urlparse(u).netloc.lower()
        if not (host=='ecb.europa.eu' or host.endswith('.ecb.europa.eu')):continue
        if re.search(r'/press/press_conference/monetary-policy-statement/20(?:1[8-9]|2[0-6])/html/ecb\.is',u,re.I):statements.append(u)
    # Defensive extraction from embedded JSON/data attributes.
    statements += [urllib.parse.urljoin(INDEX,h) for h in re.findall(r'(/press/press_conference/monetary-policy-statement/20(?:1[8-9]|2[0-6])/html/ecb\.is[^"\'<>\s]*?\.en\.html)',body,re.I)]
    statements=sorted(set(statements))
    found={}; unresolved=[]
    for su in statements:
        sdate=event_date_from_url(su,'is')
        if not sdate or not ('2018-01-01'<=sdate<='2026-10-12'):continue
        try:sbody=get(su)
        except Exception as e: unresolved.append((sdate,'statement_fetch',repr(e)));continue
        decisions=[]
        for u,t in parse_links(su,sbody):
            if re.search(r'/press/pr/date/20(?:1[8-9]|2[0-6])/html/ecb\.mp',u,re.I): decisions.append(u)
        decisions += [urllib.parse.urljoin(su,h) for h in re.findall(r'(/press/pr/date/20(?:1[8-9]|2[0-6])/html/ecb\.mp[^"\'<>\s]*?\.en\.html)',sbody,re.I)]
        # Preserve only same-day original monetary-policy decision release.
        valid=[]
        for u in sorted(set(decisions)):
            d=event_date_from_url(u,'mp')
            if d==sdate:valid.append(u)
        if not valid:
            unresolved.append((sdate,'no_same_day_mp_link',su));continue
        # Verify document title from official body.
        chosen=None
        for u in valid:
            try:txt=get(u)
            except Exception:continue
            if 'Monetary policy decisions' in re.sub(r'<[^>]+>',' ',txt): chosen=u;break
        if not chosen:
            unresolved.append((sdate,'mp_title_not_verified',valid[0]));continue
        found.setdefault(sdate,{
          'central_bank':'ECB','decision_date':sdate,'source_url':chosen,'source_document_type':'MONETARY_POLICY_DECISIONS',
          'official_domain_verified':True,'publication_timestamp':sdate+'T14:15:00',
          'timestamp_provenance':'OFFICIAL_DECISION_DAY_STANDARD_14_15_LOCAL',
          'inventory_status':'INVENTORIED_OFFICIAL_DOCUMENT'})
    rows=[x for x in r['events'] if x['central_bank']!='ECB'];rows.extend(found.values())
    dct={}
    for x in sorted(rows,key=lambda z:(z['central_bank'],z['decision_date'],z['source_url'])):dct.setdefault((x['central_bank'],x['decision_date']),x)
    rows=list(dct.values());cbs=('FED','ECB','BOJ','BOC','RBA');counts={cb:sum(x['central_bank']==cb for x in rows) for cb in cbs}
    r['events']=sorted(rows,key=lambda x:(x['decision_date'],x['central_bank']))
    r['counts_by_central_bank']={k:v for k,v in counts.items() if v}
    r['source_errors']['ECB']=None if counts['ECB']>=50 else f'ECB_STATEMENT_TRAVERSAL_COVERAGE_LT_50:{counts["ECB"]}'
    r['status']='RESULT_BLIND_EVENT_INVENTORY_COMPLETE' if all(counts[cb]>=50 for cb in cbs) and not any(r['source_errors'].values()) else 'RESULT_BLIND_EVENT_INVENTORY_PARTIAL'
    assert r['focus_labels_present'] is False and r['performance_data_present'] is False
    Path(a.output).write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':r['status'],'counts':counts,'statement_links':len(statements),'ecb_verified':len(found),'unresolved_n':len(unresolved),'unresolved_sample':unresolved[:10]},indent=2,sort_keys=True))
if __name__=='__main__':main()
