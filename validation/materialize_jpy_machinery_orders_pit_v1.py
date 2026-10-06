#!/usr/bin/env python3
import csv,json,re,urllib.request
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

START=(2018,1); END=(2023,7)
OUT=Path('history/pit_v1/JPY_GROWTH_MACHINERY_ORDERS_FIRST_RELEASE_2018_2023.csv')
EVID=Path('validation/JPY_MACHINERY_ORDERS_PIT_ACTIVATION_V1_2026-10-06.json')
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36'
BASE='https://www.esri.cao.go.jp'
MONTH_NAMES={1:'January',2:'February',3:'March',4:'April',5:'May',6:'June',7:'July',8:'August',9:'September',10:'October',11:'November',12:'December'}

def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*','Accept-Language':'en-US,en;q=0.9,ja;q=0.8'})
    with urllib.request.urlopen(req,timeout=40) as r:return r.read().decode('utf-8','replace')

def months():
    out=[];y,m=START
    while (y,m)<=END:
        out.append((y,m));m+=1
        if m==13:y+=1;m=1
    return out

def result_urls(y,m):
    stem=f'{str(y)[2:]}{m:02d}juchu-e.html'
    if y<=2019:return [f'{BASE}/en/stat/juchu/{stem}']
    return [f'{BASE}/en/stat/juchu/{y}/{stem}',f'{BASE}/en/stat/juchu/{stem}']

def parse_value(y,m):
    raw=None;used=None;err=None
    for u in result_urls(y,m):
        try:raw=get(u);used=u;break
        except Exception as e:err=e
    if raw is None:raise RuntimeError(str(err))
    text=' '.join(BeautifulSoup(raw,'html.parser').stripped_strings)
    mn=MONTH_NAMES[m]
    p=rf'Private-sector machinery orders, excluding volatile ones for ships and those from electric power companies,\s*(increased|decreased)\s+(?:a\s+)?seasonally adjusted by\s*([0-9]+(?:\.[0-9]+)?)%\s+in\s+{mn}'
    mm=re.search(p,text,re.I)
    if not mm:
        p=rf'Private-sector machinery orders[^.]*?(increased|decreased)\s+(?:a\s+)?seasonally adjusted by\s*([0-9]+(?:\.[0-9]+)?)%\s+in\s+{mn}'
        mm=re.search(p,text,re.I)
    if not mm:raise ValueError('monthly private-sector ex-volatile value not found')
    v=float(mm.group(2))*(1 if mm.group(1).lower()=='increased' else -1)
    return v,used

def news_release_map(year):
    u=f'{BASE}/en/news/{year}/index.html'
    text='\n'.join(BeautifulSoup(get(u),'html.parser').stripped_strings)
    # Each news item is rendered as a date line followed by its title. Capture Machinery Orders month/year.
    out={}
    lines=[re.sub(r'\s+',' ',x).strip() for x in text.splitlines() if x.strip()]
    current_date=None
    for line in lines:
        md=re.fullmatch(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.\s*(\d{1,2}),\s*(20\d{2})',line)
        if md:
            mon=datetime.strptime(md.group(1),'%b').month
            current_date=f'{int(md.group(3)):04d}-{mon:02d}-{int(md.group(2)):02d}'
            continue
        mm=re.search(r'Machinery Orders in\s+([A-Za-z]+),\s*(20\d{2})',line,re.I)
        if mm and current_date:
            try:refm=datetime.strptime(mm.group(1).rstrip('.'),'%B').month
            except:
                try:refm=datetime.strptime(mm.group(1).rstrip('.'),'%b').month
                except:continue
            out[(int(mm.group(2)),refm)]=current_date
    return out,u

def main():
    release_maps={}; release_sources={}
    for y in range(2018,2024):
        try:release_maps[y],release_sources[y]=news_release_map(y)
        except Exception as e:release_maps[y]={};release_sources[y]=str(e)
    rows=[];errors=[]
    for y,m in months():
        key=(y,m)
        try:
            v,u=parse_value(y,m)
            # Release normally occurs 1-2 months after reference month; search current and following calendar year news indexes.
            rd=None;news_u=None
            for ny in (y,y+1):
                if ny not in release_maps:
                    try:release_maps[ny],release_sources[ny]=news_release_map(ny)
                    except Exception as e:release_maps[ny]={};release_sources[ny]=str(e)
                if key in release_maps[ny]: rd=release_maps[ny][key];news_u=f'{BASE}/en/news/{ny}/index.html';break
            if not rd:raise ValueError('release date not found in ESRI What’s New archive')
            rows.append({'reference_month':f'{y:04d}-{m:02d}','release_date':rd,'release_time_jst':'08:50','availability_timestamp_jst':rd+'T08:50:00+09:00','private_core_orders_sa_mom_pct':v,'source_result_url':u,'source_release_index':news_u,'pit_status':'READY_FIRST_RELEASE'})
        except Exception as e:errors.append({'reference_month':f'{y:04d}-{m:02d}','error':str(e)})
    exp=[f'{y:04d}-{m:02d}' for y,m in months()];got=[r['reference_month'] for r in rows]
    missing=sorted(set(exp)-set(got));dup=sorted({x for x in got if got.count(x)>1})
    status='PASS' if not errors and not missing and not dup and len(rows)==len(exp) else 'FAIL'
    ev={'schema':'GMFQ_JPY_MACHINERY_ORDERS_PIT_ACTIVATION_V1','status':status,'coverage':{'start':exp[0],'end':exp[-1],'expected_months':len(exp),'materialized_months':len(rows)},'series':'Private-sector machinery orders excluding ships and electric power, SA m/m','source_policy':'Contemporaneous ESRI English monthly result page for first-published value + annual ESRI What’s New archive for release date','event_time_policy':'08:50 JST official Machinery Orders publication time','errors':errors,'missing':missing,'duplicates':dup,'revised_history_fallback_used':False,'pit_active_machinery_orders':status=='PASS','changes_engine_rules':False,'changes_live_data':False}
    EVID.write_text(json.dumps(ev,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    if status!='PASS':print(json.dumps(ev,indent=2,ensure_ascii=False));raise SystemExit(1)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(ev,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
