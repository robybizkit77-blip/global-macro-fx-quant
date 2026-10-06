from __future__ import annotations
import csv, html, json, re, time
from datetime import datetime, date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

ARCHIVE='https://www.bls.gov/bls/news-release/cpi.htm'
OUT=Path('history/pit_v1/USD_CPI_HEADLINE_CORE_FIRST_RELEASE_2016_2026.csv')
EVID=Path('validation/USD_CPI_BLS_ARCHIVE_PIT_MATERIALIZATION_2026-10-06.json')
START=(2016,1); END=(2026,8)
WITHHELD={'2025-10':'BLS did not publish an October 2025 CPI news release because of the 2025 lapse in federal government appropriations.'}
REF_EXCEPTIONS={'https://www.bls.gov/news.release/archives/cpi_06162016.htm':(2016,5)}
UA='Mozilla/5.0 GMFQ-PIT-Audit/1.0 (research; contact via repository)'
MONTH_LIST=['january','february','march','april','may','june','july','august','september','october','november','december']
MONTHS={m:i for i,m in enumerate(MONTH_LIST,1)}
MONTH_ALT='|'.join(m.title() for m in MONTH_LIST)
class TP(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]
    def handle_data(self,d): self.parts.append(d)
    def text(self): return re.sub(r'\s+',' ',html.unescape(' '.join(self.parts))).strip()
def get(u,tries=4):
    err=None
    for n in range(tries):
        try:
            with urlopen(Request(u,headers={'User-Agent':UA,'Accept':'text/html,*/*'}),timeout=40) as r: return r.read().decode('utf-8',errors='replace')
        except Exception as e: err=e; time.sleep(1.5*(n+1))
    raise RuntimeError(f'GET failed {u}: {err}')
def ym_between(y,m): return START <= (y,m) <= END
def urls():
    raw=get(ARCHIVE)
    hrefs=re.findall(r'href\s*=\s*["\']([^"\']*cpi_\d{8}\.(?:pdf|htm))["\']',raw,re.I)
    out=set()
    for h in hrefs:
        u=urljoin(ARCHIVE,html.unescape(h)); mm=re.search(r'cpi_(\d{2})(\d{2})(\d{4})',u,re.I)
        if not mm: continue
        rd=date(int(mm.group(3)),int(mm.group(1)),int(mm.group(2)))
        if date(2016,2,1)<=rd<=date(2026,10,6):
            if u.lower().endswith('.pdf'): u=u[:-4]+'.htm'
            out.add(u)
    return sorted(out)
def ref_period(text,u):
    p=re.search(rf'(?:THE\s+)?CONSUMER PRICE INDEX.{{0,30}}?\b({MONTH_ALT})\s+(\d{{4}})\b',text,re.I)
    if p:
        m=MONTHS.get(p.group(1).lower()); y=int(p.group(2))
        if not m: raise ValueError('unknown month')
        return y,m,p.start()
    # One archived 2016 HTML rendering does not expose the title text to the parser,
    # while the official BLS PDF and 2016 release schedule identify it as May 2016.
    # Keep this as a single explicit source exception rather than infer months globally.
    if u in REF_EXCEPTIONS:
        y,m=REF_EXCEPTIONS[u]
        anchor=re.search(r'The Consumer Price Index for All Urban Consumers',text,re.I)
        return y,m,(anchor.start() if anchor else 0)
    raise ValueError('reference title not found')
def parse(text,u):
    y,m,pos=ref_period(text,u)
    ts=re.search(r'8:30\s*a\.m\.\s*\((?:ET|EST|EDT)\)\s*(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday),?\s*)?([A-Za-z]+\s+\d{1,2},\s+\d{4})',text,re.I)
    if not ts:
        ts=re.search(r'8:30\s*a\.m\.\s*(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday),?\s*)?([A-Za-z]+\s+\d{1,2},\s+\d{4})',text,re.I)
    if not ts: raise ValueError('release timestamp not found')
    rd=datetime.strptime(ts.group(1),'%B %d, %Y').date().isoformat()
    body=text[pos:pos+15000]
    h=None
    for pat in [
      r'Over the last 12 months, the all items index (?:increased|rose)\s+(\d+(?:\.\d+)?)\s+percent',
      r'all items index (?:increased|rose)\s+(\d+(?:\.\d+)?)\s+percent (?:over|for) the (?:last )?(?:12 months|year)',
      r'all items index.{0,140}?12-month.{0,100}?(\d+(?:\.\d+)?)\s+percent']:
        q=re.search(pat,body,re.I)
        if q: h=float(q.group(1)); break
    if h is None:
        q=re.search(r'Over the last 12 months, the all items index (?:decreased|fell)\s+(\d+(?:\.\d+)?)\s+percent',body,re.I)
        if q: h=-float(q.group(1))
    if h is None: raise ValueError('headline CPI YoY not found')
    c=None
    core_phrase=r'(?:index for\s+)?all items less food and energy(?:\s+index)?'
    for pat in [
      core_phrase+r'.{0,260}?(?:increased|rose)\s+(\d+(?:\.\d+)?)\s+percent over the (?:last|past) 12 months',
      core_phrase+r'.{0,260}?(?:increased|rose)\s+(\d+(?:\.\d+)?)\s+percent over the year',
      core_phrase+r'.{0,260}?(?:increased|rose)\s+(\d+(?:\.\d+)?)\s+percent for the 12 months ending\s+(?:'+MONTH_ALT+r')',
      core_phrase+r'.{0,260}?12-month.{0,120}?(\d+(?:\.\d+)?)\s+percent']:
        q=re.search(pat,body,re.I)
        if q: c=float(q.group(1)); break
    if c is None: raise ValueError('core CPI YoY not found')
    return {'release_date':rd,'release_time_et':'08:30','reference_month':f'{y:04d}-{m:02d}','headline_cpi_yoy_pct':h,'core_cpi_yoy_pct':c,'source_url':u,'pit_status':'READY_FIRST_RELEASE'}
def months():
    out=[]; y,m=START
    while (y,m)<=END:
        out.append(f'{y:04d}-{m:02d}'); m+=1
        if m==13:y+=1;m=1
    return out
def main():
    allm=months(); expected=[m for m in allm if m not in WITHHELD]; us=urls(); rows=[]; errors=[]
    for u in us:
        try:
            p=TP(); p.feed(get(u)); r=parse(p.text(),u); y,m=map(int,r['reference_month'].split('-'))
            if ym_between(y,m): rows.append(r)
        except Exception as e: errors.append({'url':u,'error':str(e)})
        time.sleep(.12)
    by={}; dup=[]
    for r in rows:
        if r['reference_month'] in by: dup.append(r['reference_month'])
        by[r['reference_month']]=r
    missing=sorted(set(expected)-set(by)); extra=sorted(set(by)-set(expected))
    if errors or dup or missing or extra:
        payload={'status':'FAIL','candidate_urls':len(us),'rows_parsed':len(rows),'structural_withheld':WITHHELD,'missing':missing,'duplicates':sorted(set(dup)),'extra':extra,'errors':errors}
        EVID.write_text(json.dumps(payload,indent=2),encoding='utf-8'); print(json.dumps(payload,indent=2)); raise SystemExit('strict CPI PIT gate failed')
    rows=[by[m] for m in expected]
    for r in rows:
        if not (-5<=r['headline_cpi_yoy_pct']<=20 and -5<=r['core_cpi_yoy_pct']<=20): raise SystemExit(f'implausible CPI {r}')
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    ev={'schema':'GMFQ_USD_CPI_BLS_ARCHIVE_PIT_V1','status':'PASS','source':'Official BLS archived CPI news releases','coverage':{'start':allm[0],'end':allm[-1],'calendar_months':len(allm),'published_complete_releases':len(rows),'structural_withheld_months':len(WITHHELD)},'structural_withheld':WITHHELD,'source_exceptions':{'2016-05':'Official BLS June 16 2016 HTML rendering lacks parser-visible title; reference month is certified from the official BLS archived PDF/release schedule.'},'fields':['headline CPI YoY first-published','core CPI ex-food-energy YoY first-published','release date','08:30 ET release time'],'method':'Opening archived CPI release text only; no current/revised-history substitution.','strict_zero_parse_errors_on_published_releases':True,'output':str(OUT),'notes':['This is a CPI release-state block, not a claim that CPI is the Fed preferred inflation gauge; PCE remains conceptually distinct.','No consensus-surprise series is introduced.','No engine/live-data changes.']}
    EVID.write_text(json.dumps(ev,indent=2),encoding='utf-8');print(json.dumps(ev,indent=2))
if __name__=='__main__':main()
