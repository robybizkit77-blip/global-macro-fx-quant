#!/usr/bin/env python3
import csv,json,re,urllib.request
from pathlib import Path
from bs4 import BeautifulSoup

START=(2018,1); END=(2023,7)
OUT=Path('history/pit_v1/JPY_GROWTH_MACHINERY_ORDERS_FIRST_RELEASE_2018_2023.csv')
EVID=Path('validation/JPY_MACHINERY_ORDERS_PIT_ACTIVATION_V1_2026-10-06.json')
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36'
BASE='https://www.esri.cao.go.jp'
MONTH_NAMES={1:'January',2:'February',3:'March',4:'April',5:'May',6:'June',7:'July',8:'August',9:'September',10:'October',11:'November',12:'December'}

def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*','Accept-Language':'ja,en-US;q=0.9,en;q=0.8'})
    with urllib.request.urlopen(req,timeout=40) as r:return r.read().decode('utf-8','replace')

def months():
    out=[];y,m=START
    while (y,m)<=END:
        out.append((y,m));m+=1
        if m==13:y+=1;m=1
    return out

def en_urls(y,m):
    stem=f'{str(y)[2:]}{m:02d}juchu-e.html'
    if y<=2019:return [f'{BASE}/en/stat/juchu/{stem}']
    return [f'{BASE}/en/stat/juchu/{y}/{stem}',f'{BASE}/en/stat/juchu/{stem}']

def jp_urls(y,m):
    stem=f'{str(y)[2:]}{m:02d}juchu.html'
    if y<=2019:return [f'{BASE}/jp/stat/juchu/{stem}']
    return [f'{BASE}/jp/stat/juchu/{y}/{stem}',f'{BASE}/jp/stat/juchu/{stem}']

def first_html(urls):
    last=None
    for u in urls:
        try:return get(u),u
        except Exception as e:last=e
    raise RuntimeError(str(last))

def parse_value(y,m):
    raw,used=first_html(en_urls(y,m)); text=' '.join(BeautifulSoup(raw,'html.parser').stripped_strings); mn=MONTH_NAMES[m]
    pats=[
      rf'Private-sector machinery orders, excluding volatile ones for ships and those from electric power companies,\s*(increased|decreased)\s+(?:a\s+)?seasonally adjusted by\s*([0-9]+(?:\.[0-9]+)?)%\s+in\s+{mn}',
      rf'Private-sector machinery orders[^.]*?(increased|decreased)\s+(?:a\s+)?seasonally adjusted by\s*([0-9]+(?:\.[0-9]+)?)%\s+in\s+{mn}',
      rf'Private-sector machinery orders[^.]*?{mn}[^.]*?(increased|decreased)[^.]*?([0-9]+(?:\.[0-9]+)?)%'
    ]
    for p in pats:
        mm=re.search(p,text,re.I)
        if mm:
            v=float(mm.group(2))*(1 if mm.group(1).lower()=='increased' else -1)
            return v,used
    raise ValueError('monthly private-sector ex-volatile value not found')

def era_to_year(era,yr):
    n=1 if yr=='元' else int(yr)
    if era=='平成': return 1988+n
    if era=='令和': return 2018+n
    raise ValueError('unknown era')

def parse_release_date(y,m):
    raw,used=first_html(jp_urls(y,m)); text=' '.join(BeautifulSoup(raw,'html.parser').stripped_strings)
    mm=re.search(r'(平成|令和)\s*(元|\d+)\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',text)
    if mm:
        yy=era_to_year(mm.group(1),mm.group(2)); return f'{yy:04d}-{int(mm.group(3)):02d}-{int(mm.group(4)):02d}',used
    mm=re.search(r'(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',text)
    if mm:return f'{int(mm.group(1)):04d}-{int(mm.group(2)):02d}-{int(mm.group(3)):02d}',used
    raise ValueError('release date not found on contemporaneous Japanese result page')

def main():
    rows=[];errors=[]
    for y,m in months():
        try:
            v,en_u=parse_value(y,m); rd,jp_u=parse_release_date(y,m)
            rows.append({'reference_month':f'{y:04d}-{m:02d}','release_date':rd,'release_time_jst':'08:50','availability_timestamp_jst':rd+'T08:50:00+09:00','private_core_orders_sa_mom_pct':v,'source_result_url_en':en_u,'source_result_url_jp':jp_u,'pit_status':'READY_FIRST_RELEASE'})
        except Exception as e:errors.append({'reference_month':f'{y:04d}-{m:02d}','error':str(e)})
    exp=[f'{y:04d}-{m:02d}' for y,m in months()];got=[r['reference_month'] for r in rows]
    missing=sorted(set(exp)-set(got));dup=sorted({x for x in got if got.count(x)>1})
    status='PASS' if not errors and not missing and not dup and len(rows)==len(exp) else 'FAIL'
    ev={'schema':'GMFQ_JPY_MACHINERY_ORDERS_PIT_ACTIVATION_V1','status':status,'coverage':{'start':exp[0],'end':exp[-1],'expected_months':len(exp),'materialized_months':len(rows)},'series':'Private-sector machinery orders excluding ships and electric power, SA m/m','source_policy':'Contemporaneous ESRI English monthly result page for first-published value + matching contemporaneous Japanese result page for release date (Heisei/Reiwa aware)','event_time_policy':'08:50 JST official Machinery Orders publication time','errors':errors,'missing':missing,'duplicates':dup,'revised_history_fallback_used':False,'pit_active_machinery_orders':status=='PASS','changes_engine_rules':False,'changes_live_data':False}
    EVID.write_text(json.dumps(ev,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    if status!='PASS':print(json.dumps(ev,indent=2,ensure_ascii=False));raise SystemExit(1)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(ev,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
