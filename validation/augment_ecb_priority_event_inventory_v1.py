#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re,urllib.parse,urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

UA='GMFQ-research/1.0 official-ecb-account-index'
class P(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.h=None;self.t=[]
    def handle_starttag(self,tag,attrs):
        if tag.lower()=='a':self.h=dict(attrs).get('href');self.t=[]
    def handle_data(self,d):
        if self.h is not None:self.t.append(d)
    def handle_endtag(self,tag):
        if tag.lower()=='a' and self.h is not None:self.links.append((self.h,' '.join(''.join(self.t).split())));self.h=None;self.t=[]
def get(u):
    q=urllib.request.Request(u,headers={'User-Agent':UA})
    with urllib.request.urlopen(q,timeout=45) as r:return r.read().decode('utf-8','ignore')
def links_from(base,body):
    p=P();p.feed(body);return [(urllib.parse.urljoin(base,h),t) for h,t in p.links if h]
def dt_from_mp(u):
    m=re.search(r'ecb\.mp(\d{2})(\d{2})(\d{2})',u,re.I)
    if not m:return None
    try:return date(2000+int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()
    except ValueError:return None
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    r=json.load(open(a.input));rows=list(r['events']);found=[];errs=[]
    for y in range(2018,2027):
        idx=f'https://www.ecb.europa.eu/press/accounts/{y}/html/index.en.html'
        try: body=get(idx)
        except Exception as e: errs.append(f'{y}:{e!r}');continue
        account_urls=[]
        for u,t in links_from(idx,body):
            if 'ecb.europa.eu' not in urllib.parse.urlparse(u).netloc.lower():continue
            if f'/press/accounts/{y}/html/ecb.mg' in u and '.en.' in u:account_urls.append(u)
        # Some annual indexes embed account URLs outside normal anchors.
        account_urls += ['https://www.ecb.europa.eu'+x for x in re.findall(r'"(/press/accounts/%d/html/ecb\.mg[^"<> ]*?\.en\.html)"'%y,body,re.I)]
        for au in sorted(set(account_urls)):
            try: txt=get(au)
            except Exception:continue
            candidates=set(re.findall(r'https?://(?:www\.)?ecb\.europa\.eu/press/pr/date/20(?:1[8-9]|2[0-6])/html/ecb\.mp[^"<>\s]*?\.en\.html',txt,re.I))
            candidates.update('https://www.ecb.europa.eu'+x for x in re.findall(r'["\'](/press/pr/date/20(?:1[8-9]|2[0-6])/html/ecb\.mp[^"\'<>\s]*?\.en\.html)["\']',txt,re.I))
            for u in candidates:
                d=dt_from_mp(u)
                if not d or not ('2018-01-01'<=d<='2026-10-12'):continue
                found.append({'central_bank':'ECB','decision_date':d,'source_url':u.replace('http://','https://'),'source_document_type':'MONETARY_POLICY_DECISIONS','official_domain_verified':True,
                              'publication_timestamp':d+'T14:15:00','timestamp_provenance':'OFFICIAL_ARCHIVE_STANDARD_14_15_LOCAL','inventory_status':'INVENTORIED_OFFICIAL_DOCUMENT'})
    rows.extend(found);dct={}
    for x in sorted(rows,key=lambda z:(z['central_bank'],z['decision_date'],z['source_url'])):dct.setdefault((x['central_bank'],x['decision_date']),x)
    rows=list(dct.values());r['events']=sorted(rows,key=lambda x:(x['decision_date'],x['central_bank']))
    counts={cb:sum(1 for x in rows if x['central_bank']==cb) for cb in ('FED','ECB','BOJ','BOC','RBA')};r['counts_by_central_bank']={k:v for k,v in counts.items() if v}
    r['source_errors']['ECB']=None if found else ('ECB_ACCOUNT_INDEX_DISCOVERY_EMPTY'+(':'+','.join(errs[:3]) if errs else ''))
    r['status']='RESULT_BLIND_EVENT_INVENTORY_COMPLETE' if all(counts.values()) and not any(r['source_errors'].values()) else 'RESULT_BLIND_EVENT_INVENTORY_PARTIAL'
    assert r['focus_labels_present'] is False and r['performance_data_present'] is False
    Path(a.output).write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':r['status'],'counts':counts,'ecb_discovered':len(found),'ecb_errors':errs[:3]},indent=2,sort_keys=True))
if __name__=='__main__':main()
