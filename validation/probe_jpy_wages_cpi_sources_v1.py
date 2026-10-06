from __future__ import annotations
import json, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

OUT=Path('validation/JPY_WAGES_CPI_SOURCE_PROBE_V1_2026-10-06.json')
START=(2018,1); END=(2023,7); UA={'User-Agent':'GMFQ-PIT-source-audit/1.2'}

def months():
    y,m=START; out=[]
    while (y,m)<=END:
        out.append(f'{y:04d}-{m:02d}'); m+=1
        if m==13:y+=1;m=1
    return out
TARGET=months()

def req(url,timeout=8):
    try:
        r=requests.get(url,headers=UA,timeout=timeout,allow_redirects=True)
        if r.ok:r.encoding=r.apparent_encoding or r.encoding
        return r
    except Exception:return None

def mhlw_candidates(y,m):
    yy=y%100; ids=[]
    if y==2018: ids=[('30',f'30{m:02d}')]
    elif y==2019: ids=[('31',f'31{m:02d}'),('r01',f'19{m:02d}'),('r01',f'01{m:02d}')]
    else:
        era=y-2018
        ids=[(f'r{era:02d}',f'{yy:02d}{m:02d}'),(f'r{era:02d}',f'{era:02d}{m:02d}')]
    return list(dict.fromkeys(f'https://www.mhlw.go.jp/toukei/itiran/roudou/monthly/{f}/{s}p/{s}p.html' for f,s in ids))

def one_wage(ym):
    y,m=map(int,ym.split('-')); tries=[]
    for u in mhlw_candidates(y,m):
        r=req(u); code=r.status_code if r else None; tries.append({'url':u,'status':code})
        if not r or not r.ok:continue
        soup=BeautifulSoup(r.text,'html.parser'); txt=soup.get_text(' ',strip=True)
        if 'monthly' not in r.url:continue
        docs=[]
        for a in soup.find_all('a',href=True):
            h=urljoin(r.url,a['href']); at=' '.join(a.stripped_strings)
            if h.lower().endswith('.pdf') or '/dl/' in h:docs.append({'url':h,'anchor':at})
        return ym,{'page_url':r.url,'page_status':code,'preliminary_marker_seen':('速報' in txt or r.url.endswith('p.html')),'document_candidates':docs[:30]},tries
    return ym,None,tries

def probe_mhlw():
    found={}; attempts={}
    with ThreadPoolExecutor(max_workers=16) as ex:
        fut=[ex.submit(one_wage,ym) for ym in TARGET]
        for f in as_completed(fut):
            ym,z,tr=f.result(); attempts[ym]=tr
            if z:found[ym]=z
    return {'coverage_count':len(found),'missing_months':[x for x in TARGET if x not in found],
            'months_found':dict(sorted(found.items())),'attempts_for_missing':{k:attempts[k] for k in TARGET if k not in found}}

CPI_CONFIG={'2015':{'tclass1':'000001085955','tstat':'000001084976'},'2020':{'tclass1':'000001150149','tstat':'000001150147'}}
def cpi_base(ym):return '2015' if ym<='2021-06' else '2020'
def cpi_year_url(y,b):
    c=CPI_CONFIG[b]
    return f'https://www.e-stat.go.jp/stat-search/files?cycle=1&layout=datalist&page=1&tclass1={c["tclass1"]}&tclass2val=0&toukei=00200573&tstat={c["tstat"]}&year={y}0'
def month_from_anchor(a,y):
    mo=re.fullmatch(r'(1[0-2]|[1-9])月',' '.join(a.stripped_strings))
    return None if not mo else (f'{y:04d}-{int(mo.group(1)):02d}',urljoin('https://www.e-stat.go.jp',a['href']))
def month_detail(item):
    ym,u=item; r=req(u)
    if not r or not r.ok:return ym,{'month_page_status':r.status_code if r else None,'pdf_candidates':[]}
    soup=BeautifulSoup(r.text,'html.parser'); pdf=[]
    for textnode in soup.find_all(string=lambda s:s and '結果の概要（全国）' in s):
        node=textnode.parent
        for par in [node]+list(node.parents)[:6]:
            for a in par.find_all('a',href=True):
                h=urljoin(r.url,a['href']); at=' '.join(a.stripped_strings)
                if 'file-download' in h or h.lower().endswith('.pdf') or 'PDF' in at.upper():pdf.append({'url':h,'anchor':at})
            if pdf:break
    if not pdf:
        for a in soup.find_all('a',href=True):
            h=urljoin(r.url,a['href']); at=' '.join(a.stripped_strings)
            if 'file-download' in h or h.lower().endswith('.pdf'):pdf.append({'url':h,'anchor':at})
    uniq=[]; seen=set()
    for x in pdf:
        if x['url'] not in seen:seen.add(x['url']);uniq.append(x)
    return ym,{'month_page_status':r.status_code,'resolved_month_url':r.url,'pdf_candidates':uniq[:20]}
def one_year(y,b):
    u=cpi_year_url(y,b); r=req(u); links={}
    if r and r.ok:
        soup=BeautifulSoup(r.text,'html.parser')
        for a in soup.find_all('a',href=True):
            z=month_from_anchor(a,y)
            if z and z[0] in TARGET and cpi_base(z[0])==b:links.setdefault(*z)
    return f'{b}:{y}',{'url':u,'status':r.status_code if r else None,'month_links':links}
def probe_cpi():
    year_pages={}; jobs=[(y,'2015') for y in range(2018,2022)]+[(y,'2020') for y in range(2021,2024)]
    with ThreadPoolExecutor(max_workers=7) as ex:
        for f in as_completed([ex.submit(one_year,*x) for x in jobs]):k,v=f.result();year_pages[k]=v
    monthlinks={}
    for yp in year_pages.values():monthlinks.update(yp['month_links'])
    details={}
    with ThreadPoolExecutor(max_workers=16) as ex:
        for f in as_completed([ex.submit(month_detail,x) for x in monthlinks.items()]):ym,z=f.result();details[ym]=z
    found={ym:{'base':cpi_base(ym),'e_stat_month_url':monthlinks[ym],**details.get(ym,{})} for ym in monthlinks}
    return {'coverage_count':len(found),'missing_months':[x for x in TARGET if x not in found],
            'months_found':dict(sorted(found.items())),'year_pages':dict(sorted(year_pages.items())),
            'months_with_pdf_candidates':sum(bool(v.get('pdf_candidates')) for v in found.values()),
            'note':'Coverage requires an official month-specific e-Stat dataset page; PDF candidates are recorded separately for semantic certification.'}
def main():
    w=probe_mhlw();c=probe_cpi()
    obj={'schema':'GMFQ_JPY_WAGES_CPI_SOURCE_PROBE_V1','probe_revision':'1.2','created_at':'2026-10-06','target_coverage':'2018-01 through 2023-07','required_months':67,
         'wages_mhlw_preliminary':w,'cpi_statistics_bureau_first_release':c,'status':'SOURCE_PROBE_COMPLETE',
         'green_for_materialization':w['coverage_count']==67 and c['coverage_count']==67,
         'guardrails':['No revised-history substitution','No current/latest static document used as historical vintage','Month-specific official source required before value extraction','No engine/live/OOS changes'],
         'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False}
    OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'wages':w['coverage_count'],'cpi':c['coverage_count'],'cpi_pdf_candidates':c['months_with_pdf_candidates'],'green':obj['green_for_materialization']}))
if __name__=='__main__':main()
