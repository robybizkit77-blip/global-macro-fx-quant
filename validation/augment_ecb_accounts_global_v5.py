#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re,urllib.parse,urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

UA='GMFQ-research/1.0 result-blind-ecb-accounts-index'
INDEX='https://www.ecb.europa.eu/press/accounts/html/index.en.html'

class P(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]; self.h=None; self.buf=[]
    def handle_starttag(self,tag,attrs):
        if tag.lower()=='a': self.h=dict(attrs).get('href'); self.buf=[]
    def handle_data(self,d):
        if self.h is not None:self.buf.append(d)
    def handle_endtag(self,tag):
        if tag.lower()=='a' and self.h is not None:
            self.links.append((self.h,' '.join(''.join(self.buf).split()))); self.h=None; self.buf=[]

def get(u):
    q=urllib.request.Request(u,headers={'User-Agent':UA})
    with urllib.request.urlopen(q,timeout=60) as r:return r.read().decode('utf-8','ignore')

def parse_links(base,body):
    p=P();p.feed(body);return [(urllib.parse.urljoin(base,h),t) for h,t in p.links if h]

def mp_date(u):
    m=re.search(r'ecb\.mp(\d{2})(\d{2})(\d{2})',u,re.I)
    if not m:return None
    try:return date(2000+int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()
    except ValueError:return None

def account_year(u):
    m=re.search(r'/press/accounts/(20(?:1[8-9]|2[0-6]))/',u)
    return int(m.group(1)) if m else None

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    r=json.load(open(a.input));assert r['schema']=='GMFQ_CB_PRIORITY_DECISION_EVENT_INVENTORY_V1'
    body=get(INDEX)
    accounts=[]
    for u,t in parse_links(INDEX,body):
        host=urllib.parse.urlparse(u).netloc.lower()
        if not (host=='ecb.europa.eu' or host.endswith('.ecb.europa.eu')):continue
        if re.search(r'/press/accounts/20(?:1[8-9]|2[0-6])/html/ecb\.mg',u,re.I):accounts.append(u)
    accounts += [urllib.parse.urljoin(INDEX,h) for h in re.findall(r'(/press/accounts/20(?:1[8-9]|2[0-6])/html/ecb\.mg[^"\'<>\s]*?\.en\.html)',body,re.I)]
    accounts=sorted(set(accounts))
    found={};unresolved=[]
    for au in accounts:
        y=account_year(au)
        if y is None:continue
        try:abody=get(au)
        except Exception as e:unresolved.append((au,'account_fetch',repr(e)));continue
        candidates=[]
        for u,t in parse_links(au,abody):
            if re.search(r'/press/pr/date/20(?:1[8-9]|2[0-6])/html/ecb\.mp',u,re.I):candidates.append(u)
        candidates += [urllib.parse.urljoin(au,h) for h in re.findall(r'(/press/pr/date/20(?:1[8-9]|2[0-6])/html/ecb\.mp[^"\'<>\s]*?\.en\.html)',abody,re.I)]
        for u in sorted(set(candidates)):
            ds=mp_date(u)
            if not ds or not ('2018-01-01'<=ds<='2026-10-12'):continue
            # Accounts are published later, but only index the contemporaneous decision-day URL.
            # Verify the target is the original monetary-policy decision press release.
            try:txt=get(u)
            except Exception:continue
            plain=re.sub(r'<[^>]+>',' ',txt)
            if 'Monetary policy decisions' not in plain:continue
            found.setdefault(ds,{
              'central_bank':'ECB','decision_date':ds,'source_url':u,'source_document_type':'MONETARY_POLICY_DECISIONS',
              'official_domain_verified':True,'publication_timestamp':ds+'T14:15:00',
              'timestamp_provenance':'OFFICIAL_DECISION_DAY_STANDARD_14_15_LOCAL',
              'inventory_status':'INVENTORIED_OFFICIAL_DOCUMENT'})
    rows=[x for x in r['events'] if x['central_bank']!='ECB'];rows.extend(found.values())
    d={}
    for x in sorted(rows,key=lambda z:(z['central_bank'],z['decision_date'],z['source_url'])):d.setdefault((x['central_bank'],x['decision_date']),x)
    rows=list(d.values());cbs=('FED','ECB','BOJ','BOC','RBA');counts={cb:sum(x['central_bank']==cb for x in rows) for cb in cbs}
    r['events']=sorted(rows,key=lambda x:(x['decision_date'],x['central_bank']))
    r['counts_by_central_bank']={k:v for k,v in counts.items() if v}
    r['source_errors']['ECB']=None if counts['ECB']>=50 else f'ECB_GLOBAL_ACCOUNTS_COVERAGE_LT_50:{counts["ECB"]}'
    r['status']='RESULT_BLIND_EVENT_INVENTORY_COMPLETE' if all(counts[cb]>=50 for cb in cbs) and not any(r['source_errors'].values()) else 'RESULT_BLIND_EVENT_INVENTORY_PARTIAL'
    assert r['focus_labels_present'] is False and r['performance_data_present'] is False
    Path(a.output).write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':r['status'],'counts':counts,'accounts_found':len(accounts),'ecb_verified':len(found),'unresolved_n':len(unresolved),'unresolved_sample':unresolved[:5]},indent=2,sort_keys=True))
if __name__=='__main__':main()
