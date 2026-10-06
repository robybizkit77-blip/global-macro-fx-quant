#!/usr/bin/env python3
import csv, io, json, re, urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

ESRI='https://www.esri.cao.go.jp'
START_YEAR=2018; END_YEAR=2023; END_Q=2
OUT=Path('history/pit_v1/JPY_GROWTH_GDP_FIRST_PRELIM_2018_2023.csv')
EVID=Path('validation/JPY_GDP_PIT_ACTIVATION_V1_2026-10-06.json')
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36'

def request(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,text/csv,*/*','Accept-Language':'en-US,en;q=0.9,ja;q=0.7'})
    with urllib.request.urlopen(req,timeout=45) as r:return r.read()

def parse_date_text(s):
    s=re.sub(r'\s+',' ',s).strip().replace('Sept.','Sep').replace('Sept','Sep')
    for a,b in [('Jan.','Jan'),('Feb.','Feb'),('Mar.','Mar'),('Apr.','Apr'),('Jun.','Jun'),('Jul.','Jul'),('Aug.','Aug'),('Sep.','Sep'),('Oct.','Oct'),('Nov.','Nov'),('Dec.','Dec')]: s=s.replace(a,b)
    for fmt in ('%B %d, %Y','%b %d, %Y','%B %d %Y','%b %d %Y'):
        try:return datetime.strptime(s,fmt).date().isoformat()
        except:pass
    return None

def release_map(year):
    u=f'{ESRI}/en/sna/data/sokuhou/files/{year}/toukei_{year}.html'
    soup=BeautifulSoup(request(u).decode('utf-8','replace'),'html.parser')
    out={}
    # First-preliminary page is the deterministic gdemenuea.html page (second prelim uses a different target).
    # Do not depend on archive wording because Q1 rows in some years use different labels.
    for tr in soup.find_all('tr'):
        a=tr.find('a',href=re.compile(r'qe\d{3}/gdemenuea\.html$'))
        if not a: continue
        m=re.search(r'qe(\d{2})([1-4])/gdemenuea\.html$',a.get('href',''))
        if not m: continue
        q=int(m.group(2))
        cells=tr.find_all('td')
        rd=None
        for td in cells[:2]:
            rd=parse_date_text(' '.join(td.stripped_strings))
            if rd: break
        if rd: out[q]={'release_date':rd,'page_url':urljoin(u,a['href'])}
    return out

def fnum(s):
    try:return float(s.strip().replace(',',''))
    except:return None

def parse_quarter(year,q,meta):
    soup=BeautifulSoup(request(meta['page_url']).decode('utf-8','replace'),'html.parser')
    target=None
    for a in soup.find_all('a',href=True):
        t=' '.join(a.stripped_strings)
        if 'Real, Seasonally Adjusted Series' in t and 'Quarter-to-Quarter' in t and a['href'].lower().endswith('.csv'):
            target=urljoin(meta['page_url'],a['href']);break
    if not target:raise ValueError('real SA q/q CSV link not found')
    raw=request(target); text=None
    for enc in ('cp932','shift_jis','utf-8-sig','utf-8'):
        try:text=raw.decode(enc);break
        except:pass
    if text is None:raise ValueError('CSV decode failed')
    latest=None
    for row in csv.reader(io.StringIO(text)):
        if len(row)<2:continue
        v=fnum(row[1])
        if v is not None: latest=(row[0].strip(),v)
    if latest is None:raise ValueError('latest GDP q/q row not found')
    return {'reference_quarter':f'{year}-Q{q}','release_date':meta['release_date'],'release_time_jst':'08:50','availability_timestamp_jst':meta['release_date']+'T08:50:00+09:00','real_gdp_sa_qoq_pct':latest[1],'source_row_label':latest[0],'source_page':meta['page_url'],'source_csv':target,'pit_status':'READY_FIRST_PRELIMINARY'}

def main():
    rows=[];errors=[];expected=[]
    for y in range(START_YEAR,END_YEAR+1):
        qmax=END_Q if y==END_YEAR else 4
        expected += [f'{y}-Q{q}' for q in range(1,qmax+1)]
        try: mp=release_map(y)
        except Exception as e:
            errors.append({'year':y,'error':'archive '+str(e)});continue
        for q in range(1,qmax+1):
            try:
                if q not in mp: raise ValueError('first preliminary archive row/page not found')
                rows.append(parse_quarter(y,q,mp[q]))
            except Exception as e: errors.append({'reference_quarter':f'{y}-Q{q}','error':str(e)})
    got=[r['reference_quarter'] for r in rows];missing=sorted(set(expected)-set(got));dup=sorted({x for x in got if got.count(x)>1})
    status='PASS' if not errors and not missing and not dup and len(rows)==len(expected) else 'FAIL'
    ev={'schema':'GMFQ_JPY_GDP_PIT_ACTIVATION_V1','status':status,'coverage':{'start':expected[0],'end':expected[-1],'expected_quarters':len(expected),'materialized_quarters':len(rows)},'series':'Cabinet Office ESRI Real GDP SA q/q first preliminary estimate','event_time_policy':'08:50 JST official ESRI Quarterly Estimates release schedule','errors':errors,'missing':missing,'duplicates':dup,'revised_history_fallback_used':False,'pit_active_gdp':status=='PASS','changes_engine_rules':False,'changes_live_data':False}
    EVID.write_text(json.dumps(ev,indent=2)+'\n',encoding='utf-8')
    if status!='PASS':print(json.dumps(ev,indent=2));raise SystemExit(1)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(ev,indent=2))
if __name__=='__main__':main()
