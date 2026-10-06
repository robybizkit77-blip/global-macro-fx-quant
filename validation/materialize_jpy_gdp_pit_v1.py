#!/usr/bin/env python3
import csv, io, json, re, urllib.request
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

ESRI='https://www.esri.cao.go.jp'
START_YEAR=2018; END_YEAR=2023; END_Q=2
OUT=Path('history/pit_v1/JPY_GROWTH_GDP_FIRST_PRELIM_2018_2023.csv')
EVID=Path('validation/JPY_GDP_PIT_ACTIVATION_V1_2026-10-06.json')
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36'

def request(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,text/csv,*/*','Accept-Language':'ja,en-US;q=0.9,en;q=0.8'})
    with urllib.request.urlopen(req,timeout=45) as r:return r.read()

def qcode(year,q): return f'qe{str(year)[2:]}{q}'
def pages(year,q):
    c=qcode(year,q);base=f'{ESRI}/en/sna/data/sokuhou/files/{year}/{c}/'
    return base+'gdemenuea.html',f'{ESRI}/jp/sna/data/data_list/sokuhou/files/{year}/{c}/gdemenuja.html'

def release_date_from_jp_page(url):
    text=BeautifulSoup(request(url).decode('utf-8','replace'),'html.parser').get_text(' ',strip=True)
    # Japanese first-preliminary page explicitly shows <YYYY年M月D日公表>.
    m=re.search(r'[<＜]?\s*(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*公表\s*[>＞]?',text)
    if not m:
        # Some pages omit brackets around publication date.
        m=re.search(r'(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',text)
    if not m: raise ValueError('publication date not found on first-preliminary page')
    return f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'

def fnum(s):
    try:return float(s.strip().replace(',',''))
    except:return None

def parse_quarter(year,q):
    en,jp=pages(year,q); rd=release_date_from_jp_page(jp)
    soup=BeautifulSoup(request(en).decode('utf-8','replace'),'html.parser')
    target=None
    for a in soup.find_all('a',href=True):
        t=' '.join(a.stripped_strings)
        if 'Real, Seasonally Adjusted Series' in t and 'Quarter-to-Quarter' in t and a['href'].lower().endswith('.csv'):
            target=urljoin(en,a['href']);break
    if not target:raise ValueError('real SA q/q CSV link not found')
    raw=request(target);text=None
    for enc in ('cp932','shift_jis','utf-8-sig','utf-8'):
        try:text=raw.decode(enc);break
        except:pass
    if text is None:raise ValueError('CSV decode failed')
    latest=None
    for row in csv.reader(io.StringIO(text)):
        if len(row)<2:continue
        v=fnum(row[1])
        if v is not None:latest=(row[0].strip(),v)
    if latest is None:raise ValueError('latest GDP q/q row not found')
    return {'reference_quarter':f'{year}-Q{q}','release_date':rd,'release_time_jst':'08:50','availability_timestamp_jst':rd+'T08:50:00+09:00','real_gdp_sa_qoq_pct':latest[1],'source_row_label':latest[0],'source_page':en,'source_csv':target,'pit_status':'READY_FIRST_PRELIMINARY'}

def main():
    rows=[];errors=[];expected=[]
    for y in range(START_YEAR,END_YEAR+1):
        qmax=END_Q if y==END_YEAR else 4
        for q in range(1,qmax+1):
            expected.append(f'{y}-Q{q}')
            try:rows.append(parse_quarter(y,q))
            except Exception as e:errors.append({'reference_quarter':f'{y}-Q{q}','error':str(e)})
    got=[r['reference_quarter'] for r in rows];missing=sorted(set(expected)-set(got));dup=sorted({x for x in got if got.count(x)>1})
    status='PASS' if not errors and not missing and not dup and len(rows)==len(expected) else 'FAIL'
    ev={'schema':'GMFQ_JPY_GDP_PIT_ACTIVATION_V1','status':status,'coverage':{'start':expected[0],'end':expected[-1],'expected_quarters':len(expected),'materialized_quarters':len(rows)},'series':'Cabinet Office ESRI Real GDP SA q/q first preliminary estimate','source_policy':'Deterministic first-preliminary page per quarter; publication date parsed from contemporaneous Japanese page; vintage-specific real SA q/q CSV from same release.','event_time_policy':'08:50 JST official ESRI Quarterly Estimates release schedule','errors':errors,'missing':missing,'duplicates':dup,'revised_history_fallback_used':False,'pit_active_gdp':status=='PASS','changes_engine_rules':False,'changes_live_data':False}
    EVID.write_text(json.dumps(ev,indent=2)+'\n',encoding='utf-8')
    if status!='PASS':print(json.dumps(ev,indent=2));raise SystemExit(1)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(ev,indent=2))
if __name__=='__main__':main()
