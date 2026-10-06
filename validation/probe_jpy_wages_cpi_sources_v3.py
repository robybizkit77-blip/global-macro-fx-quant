from __future__ import annotations
import json,re
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

OUT=Path('validation/JPY_WAGES_CPI_SOURCE_PROBE_V3_2026-10-06.json')
TARGET=[]
y,m=2018,1
while (y,m)<=(2023,7):
    TARGET.append(f'{y:04d}-{m:02d}'); m+=1
    if m==13:y+=1;m=1
S=requests.Session(); S.headers.update({'User-Agent':'GMFQ-PIT-source-audit/3.0'})

def get(url):
    r=S.get(url,timeout=30); r.raise_for_status(); return r

def parse_mhlw_index(url, allowed_years):
    r=get(url); r.encoding=r.apparent_encoding or r.encoding
    soup=BeautifulSoup(r.text,'html.parser')
    found={}; current_year=None; active=False
    for tag in soup.find_all(['h2','h3','a']):
        txt=' '.join(tag.stripped_strings)
        if tag.name=='h2':
            active=('全国調査' in txt and '月別結果' in txt)
            current_year=None
            continue
        if not active: continue
        if tag.name=='h3':
            g=re.search(r'(20\d{2})',txt)
            if g: current_year=int(g.group(1))
            elif '平成31' in txt or '令和元' in txt: current_year=2019
            else:
                h=re.search(r'平成(\d+)年',txt)
                current_year=1988+int(h.group(1)) if h else None
            continue
        if tag.name=='a' and current_year in allowed_years:
            mm=re.fullmatch(r'(\d{1,2})月速報',txt)
            if mm:
                k=f'{current_year:04d}-{int(mm.group(1)):02d}'
                if k in TARGET:
                    found[k]={'page_url':urljoin(url,tag.get('href')),'index_url':url,'label':txt}
    return found

def year_near(a):
    # e-Stat year is a local list label near the month anchor.
    node=a
    for _ in range(7):
        node=getattr(node,'parent',None)
        if node is None: break
        t=' '.join(node.stripped_strings)
        ys=re.findall(r'(20\d{2})年',t)
        if len(set(ys))==1: return int(ys[0])
    for x in a.find_all_previous(string=re.compile(r'20\d{2}年'),limit=8):
        g=re.search(r'(20\d{2})年',str(x))
        if g:return int(g.group(1))
    return None

def parse_estat(url,wanted):
    r=get(url); soup=BeautifulSoup(r.text,'html.parser'); found={}
    for a in soup.find_all('a',href=True):
        txt=' '.join(a.stripped_strings)
        mm=re.fullmatch(r'(\d{1,2})月',txt)
        if not mm: continue
        yy=year_near(a)
        if not yy: continue
        k=f'{yy:04d}-{int(mm.group(1)):02d}'
        if k in wanted:
            found[k]={'month_list_url':urljoin(url,a['href']),'collection_url':url}
    return found

def main():
    current='https://www.mhlw.go.jp/toukei/list/30-1a.html'
    historic='https://www.mhlw.go.jp/toukei/list/30-1k.html'
    wages={**parse_mhlw_index(historic,{2018,2019}),**parse_mhlw_index(current,{2020,2021,2022,2023})}
    b15='https://www.e-stat.go.jp/stat-search/files?cycle=1&layout=datalist&page=1&tclass1=000001085955&toukei=00200573&tstat=000001084976'
    b20='https://www.e-stat.go.jp/stat-search/files?cycle=1&layout=datalist&page=1&tclass1=000001150149&toukei=00200573&tstat=000001150147'
    w15={k for k in TARGET if k<='2021-06'}; w20={k for k in TARGET if k>='2021-07'}
    cpi={**parse_estat(b15,w15),**parse_estat(b20,w20)}
    obj={
      'schema':'GMFQ_JPY_WAGES_CPI_SOURCE_PROBE_V3','created_at':'2026-10-06','required_months':67,
      'target_coverage':'2018-01 through 2023-07',
      'wages_mhlw_preliminary':{'coverage_count':sum(k in wages for k in TARGET),'missing_months':[k for k in TARGET if k not in wages],'months_found':wages,'indexes':[historic,current]},
      'cpi_estat_monthly_reports':{'coverage_count':sum(k in cpi for k in TARGET),'missing_months':[k for k in TARGET if k not in cpi],'months_found':cpi,'collections':[b15,b20]},
      'green_for_document_materialization':len(wages)==67 and len(cpi)==67,
      'next_gate':'For each month download the contemporaneous preliminary/monthly report, extract declared metric values, store document URL and SHA-256; do not infer from current revised history.',
      'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False}
    OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'wages':len(wages),'cpi':len(cpi),'green':obj['green_for_document_materialization']}))
if __name__=='__main__':main()
