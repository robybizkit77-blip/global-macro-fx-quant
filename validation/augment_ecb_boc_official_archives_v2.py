#!/usr/bin/env python3
from __future__ import annotations
import argparse, html, json, re, urllib.parse, urllib.request
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path

UA='GMFQ-research/1.0 result-blind-cb-event-inventory'

class Parser(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]; self.text=[]; self.href=None; self.buf=[]
    def handle_starttag(self,tag,attrs):
        if tag.lower()=='a': self.href=dict(attrs).get('href'); self.buf=[]
    def handle_data(self,data):
        self.text.append(data)
        if self.href is not None:self.buf.append(data)
    def handle_endtag(self,tag):
        if tag.lower()=='a' and self.href is not None:
            self.links.append((self.href,' '.join(''.join(self.buf).split())));self.href=None;self.buf=[]

def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA})
    with urllib.request.urlopen(req,timeout=45) as r:return r.read().decode('utf-8','ignore')

def parsed(url):
    body=get(url); p=Parser();p.feed(body)
    return body,p

def ecb_date(url):
    m=re.search(r'ecb\.mp(\d{2})(\d{2})(\d{2})',url,re.I)
    if not m:return None
    try:return date(2000+int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()
    except ValueError:return None

def official_row(cb,ds,url,typ,timestamp,prov):
    return {'central_bank':cb,'decision_date':ds,'source_url':url,'source_document_type':typ,'official_domain_verified':True,
            'publication_timestamp':timestamp,'timestamp_provenance':prov,'inventory_status':'INVENTORIED_OFFICIAL_DOCUMENT'}

def ecb_rows():
    out=[]; errors=[]
    for y in range(2018,2027):
        # Legacy yearly press-release route redirects to the current official publications-by-date archive.
        url=f'https://www.ecb.europa.eu/press/pubbydate/html/index.en.html?name_of_publication=Press%20release&year={y}'
        try: body,p=parsed(url)
        except Exception as e: errors.append(f'{y}:{e!r}'); continue
        candidates=[]
        for href,text in p.links:
            u=urllib.parse.urljoin(url,href)
            if 'ecb.europa.eu' not in urllib.parse.urlparse(u).netloc.lower():continue
            if re.search(r'/press/pr/date/20(?:1[8-9]|2[0-6])/html/ecb\.mp',u,re.I): candidates.append(u)
        # Some archive cards expose URLs in attributes/scripts rather than anchor hrefs.
        candidates += ['https://www.ecb.europa.eu'+x for x in re.findall(r'["\'](/press/pr/date/20(?:1[8-9]|2[0-6])/html/ecb\.mp[^"\'<>\s]*?\.en\.html)["\']',body,re.I)]
        for u in sorted(set(candidates)):
            d=ecb_date(u)
            if not d or not d.startswith(str(y)) or d>'2026-10-12':continue
            out.append(official_row('ECB',d,u,'MONETARY_POLICY_DECISIONS',d+'T14:15:00','OFFICIAL_DECISION_ARCHIVE_14_15_LOCAL'))
    return out,errors

MONTHS={m.lower():i for i,m in enumerate(['','January','February','March','April','May','June','July','August','September','October','November','December']) if m}
BOC_SCHEDULES={
  2018:'https://www.bankofcanada.ca/2017/07/boc-2018-schedule-fad-mpr-releases/',
  2019:'https://www.bankofcanada.ca/2018/07/bank-canada-publishes-2019-schedule-fad-announcements-release-mpr-bos-slos/',
  2020:'https://www.bankofcanada.ca/2019/07/bank-canada-publishes-2020-schedule-policy-interest-rate-announcements-release-mpr-other-major-publications/',
  2021:'https://www.bankofcanada.ca/2020/07/2021-schedule-policy-interest-rate-announcements/',
  2022:'https://www.bankofcanada.ca/2021/07/bank-canada-publishes-its-2022-schedule-policy-interest-rate-announcements-release-monetary-policy-report-other-major-publications/',
  2023:'https://www.bankofcanada.ca/2022/07/2023-schedule-interest-rate-announcements/',
  2024:'https://www.bankofcanada.ca/2023/07/2024-schedule-policy-interest-rate-announcements-major-publications/',
  2025:'https://www.bankofcanada.ca/2024/08/bank-canada-publishes-2025-schedule-policy-interest-rate-announcements-other-major-publications/',
  2026:'https://www.bankofcanada.ca/2025/08/bank-canada-publishes-2026-schedule-policy-interest-rate-announcements-other-major-publications/'
}

def extract_boc_schedule(year,url):
    body,p=parsed(url); text=' '.join(' '.join(p.text).split())
    # Isolate the target-year schedule to avoid the page's reconfirmed prior-year dates.
    markers=[f'scheduled dates for the interest rate announcements for {year} are as follows',
             f'scheduled announcement dates for {year} are as follows',
             f'dates are as follows']
    low=text.lower(); start=None
    for marker in markers:
        i=low.find(marker.lower())
        if i>=0:start=i+len(marker);break
    if start is None: raise RuntimeError(f'BoC target-year schedule marker missing {year}')
    tail=text[start:start+1800]
    matches=re.findall(r'(?i)\b(?:Monday|Tuesday|Wednesday|Thursday|Friday),?\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+([0-3]?\d)',tail)
    out=[]
    for mon,day in matches[:8]:
        try: out.append(date(year,MONTHS[mon.lower()],int(day)).isoformat())
        except ValueError: pass
    if len(out)<8: raise RuntimeError(f'BoC schedule {year} yielded {len(out)} dates: {out}')
    return out[:8]

def verify_boc_release(ds):
    y,mo,_=ds.split('-')
    variants=[
      f'https://www.bankofcanada.ca/{y}/{mo}/fad-press-release-{ds}/',
      f'https://www.bankofcanada.ca/{y}/{mo}/press-release-{ds}/'
    ]
    for u in variants:
        try:
            body=get(u)
            low=re.sub(r'<[^>]+>',' ',body).lower()
            if 'bank of canada' in low and ('overnight rate' in low or 'policy rate' in low or 'interest rate' in low):return u
        except Exception:pass
    raise RuntimeError(f'No official BoC decision release resolved for {ds}')

def boc_rows():
    out=[]; errors=[]
    for y,url in BOC_SCHEDULES.items():
        try: dates=extract_boc_schedule(y,url)
        except Exception as e: errors.append(f'schedule-{y}:{e!r}');continue
        for ds in dates:
            if ds>'2026-10-12':continue
            try:u=verify_boc_release(ds)
            except Exception as e: errors.append(f'release-{ds}:{e!r}');continue
            # Official schedule pages state 10:00 ET historically, changing to 09:45 ET in 2025.
            hh='09:45:00' if y>=2025 else '10:00:00'
            out.append(official_row('BOC',ds,u,'SCHEDULED_POLICY_RATE_DECISION',ds+'T'+hh,'OFFICIAL_ANNUAL_POLICY_SCHEDULE_LOCAL_ET'))
    return out,errors

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    r=json.load(open(a.input));assert r['schema']=='GMFQ_CB_PRIORITY_DECISION_EVENT_INVENTORY_V1'
    rows=[x for x in r['events'] if x['central_bank'] not in ('ECB','BOC')]
    erows,eerr=ecb_rows(); brows,berr=boc_rows(); rows.extend(erows);rows.extend(brows)
    d={}
    for x in sorted(rows,key=lambda z:(z['central_bank'],z['decision_date'],z['source_url'])):d.setdefault((x['central_bank'],x['decision_date']),x)
    rows=list(d.values()); cbs=('FED','ECB','BOJ','BOC','RBA'); counts={cb:sum(x['central_bank']==cb for x in rows) for cb in cbs}
    r['events']=sorted(rows,key=lambda x:(x['decision_date'],x['central_bank']));r['counts_by_central_bank']={k:v for k,v in counts.items() if v}
    r['source_errors']['ECB']=None if counts['ECB']>=50 else 'ECB_OFFICIAL_ARCHIVE_COVERAGE_LT_50:'+(';'.join(eerr[:3]) if eerr else 'NO_TRANSPORT_ERROR')
    r['source_errors']['BOC']=None if counts['BOC']>=50 else 'BOC_OFFICIAL_SCHEDULE_RELEASE_COVERAGE_LT_50:'+(';'.join(berr[:6]) if berr else 'NO_TRANSPORT_ERROR')
    r['status']='RESULT_BLIND_EVENT_INVENTORY_COMPLETE' if all(counts[cb]>=50 for cb in cbs) and not any(r['source_errors'].values()) else 'RESULT_BLIND_EVENT_INVENTORY_PARTIAL'
    assert r['focus_labels_present'] is False and r['performance_data_present'] is False
    Path(a.output).write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':r['status'],'counts':counts,'ecb_errors':eerr[:3],'boc_errors':berr[:10]},indent=2,sort_keys=True))
if __name__=='__main__':main()
