from __future__ import annotations
import json, re
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

OUT = Path('validation/JPY_WAGES_CPI_SOURCE_PROBE_V1_2026-10-06.json')
START=(2018,1); END=(2023,7)
S=requests.Session(); S.headers.update({'User-Agent':'GMFQ-PIT-source-audit/1.1'})


def months():
    y,m=START; out=[]
    while (y,m)<=END:
        out.append(f'{y:04d}-{m:02d}'); m+=1
        if m==13: y+=1; m=1
    return out
TARGET=months()


def req(url):
    try:
        r=S.get(url,timeout=30,allow_redirects=True)
        if r.ok:
            r.encoding=r.apparent_encoding or r.encoding
        return r
    except Exception:
        return None


def mhlw_candidates(y,m):
    yy=y%100
    era=y-2018  # Reiwa 1 == 2019; 2018 is Heisei 30
    ids=[]
    if y==2018:
        ids += [('30',f'30{m:02d}')]
    elif y==2019:
        ids += [('31',f'31{m:02d}'),('r01',f'{yy:02d}{m:02d}'),('r01',f'01{m:02d}')]
    else:
        ids += [(f'r{era:02d}',f'{yy:02d}{m:02d}'),(f'r{era:02d}',f'{era:02d}{m:02d}')]
    seen=[]
    for folder,stem in ids:
        u=f'https://www.mhlw.go.jp/toukei/itiran/roudou/monthly/{folder}/{stem}p/{stem}p.html'
        if u not in seen: seen.append(u)
    return seen


def probe_mhlw():
    found={}; attempts={}
    for ym in TARGET:
        y,m=map(int,ym.split('-')); tries=[]
        for u in mhlw_candidates(y,m):
            r=req(u); code=r.status_code if r else None
            tries.append({'url':u,'status':code})
            if not r or not r.ok: continue
            txt=BeautifulSoup(r.text,'html.parser').get_text(' ',strip=True)
            # immutable month page plus preliminary marker/path suffix p.
            if ('速報' in txt or 'p.html' in r.url) and ('毎月勤労統計' in txt or 'monthly' in r.url):
                soup=BeautifulSoup(r.text,'html.parser')
                docs=[]
                for a in soup.find_all('a',href=True):
                    href=urljoin(r.url,a['href']); at=' '.join(a.stripped_strings)
                    if href.lower().endswith('.pdf') or '/dl/' in href:
                        docs.append({'url':href,'anchor':at})
                found[ym]={'page_url':r.url,'page_status':code,'document_candidates':docs[:30]}
                break
        attempts[ym]=tries
    return {'coverage_count':len(found),'missing_months':[x for x in TARGET if x not in found],
            'months_found':found,'attempts_for_missing':{k:attempts[k] for k in TARGET if k not in found}}

CPI_CONFIG={
 '2015': {'tclass1':'000001085955','tstat':'000001084976'},
 '2020': {'tclass1':'000001150149','tstat':'000001150147'}
}

def cpi_base(ym):
    return '2015' if ym <= '2021-06' else '2020'

def cpi_year_url(y,base):
    c=CPI_CONFIG[base]
    return ('https://www.e-stat.go.jp/stat-search/files?cycle=1&layout=datalist&page=1'
            f'&tclass1={c["tclass1"]}&tclass2val=0&toukei=00200573&tstat={c["tstat"]}&year={y}0')

def month_from_anchor(a,y):
    txt=' '.join(a.stripped_strings)
    mo=re.fullmatch(r'(1[0-2]|[1-9])月',txt)
    if not mo: return None
    href=urljoin('https://www.e-stat.go.jp',a.get('href',''))
    return f'{y:04d}-{int(mo.group(1)):02d}',href

def extract_national_summary_pdf(month_url):
    r=req(month_url)
    if not r or not r.ok: return {'month_page_status':r.status_code if r else None,'pdf_candidates':[]}
    soup=BeautifulSoup(r.text,'html.parser')
    pdf=[]
    # e-Stat renders each file row; keep links near rows mentioning national result overview.
    for textnode in soup.find_all(string=lambda s: s and '結果の概要（全国）' in s):
        node=textnode.parent
        for par in [node]+list(node.parents)[:5]:
            for a in par.find_all('a',href=True):
                h=urljoin(r.url,a['href']); at=' '.join(a.stripped_strings)
                if 'download' in h.lower() or 'PDF' in at.upper() or h.lower().endswith('.pdf'):
                    pdf.append({'url':h,'anchor':at})
            if pdf: break
    # Fallback: record file-download links on month page for later semantic classification.
    if not pdf:
        for a in soup.find_all('a',href=True):
            h=urljoin(r.url,a['href']); at=' '.join(a.stripped_strings)
            if 'file-download' in h or h.lower().endswith('.pdf'):
                pdf.append({'url':h,'anchor':at})
    uniq=[]; seen=set()
    for x in pdf:
        if x['url'] not in seen: seen.add(x['url']); uniq.append(x)
    return {'month_page_status':r.status_code,'resolved_month_url':r.url,'pdf_candidates':uniq[:20]}

def probe_cpi():
    found={}; year_pages={}
    # Each official e-Stat year page exposes immutable month-specific dataset links.
    for base in ('2015','2020'):
        years=range(2018,2022) if base=='2015' else range(2021,2024)
        for y in years:
            u=cpi_year_url(y,base); r=req(u)
            yp={'url':u,'status':r.status_code if r else None,'month_links':{}}
            if r and r.ok:
                soup=BeautifulSoup(r.text,'html.parser')
                for a in soup.find_all('a',href=True):
                    z=month_from_anchor(a,y)
                    if not z: continue
                    ym,href=z
                    if ym in TARGET and cpi_base(ym)==base:
                        yp['month_links'].setdefault(ym,href)
            year_pages[f'{base}:{y}']=yp
    for yp in year_pages.values():
        for ym,u in yp['month_links'].items():
            if ym in found: continue
            detail=extract_national_summary_pdf(u)
            found[ym]={'base':cpi_base(ym),'e_stat_month_url':u,**detail}
    return {'coverage_count':len(found),'missing_months':[x for x in TARGET if x not in found],
            'months_found':found,'year_pages':year_pages,
            'note':'Coverage means an official month-specific e-Stat dataset page was resolved. PDF candidates are separately recorded and must be semantically certified before value extraction.'}

def main():
    w=probe_mhlw(); c=probe_cpi()
    obj={'schema':'GMFQ_JPY_WAGES_CPI_SOURCE_PROBE_V1','probe_revision':'1.1','created_at':'2026-10-06',
         'target_coverage':'2018-01 through 2023-07','required_months':67,
         'wages_mhlw_preliminary':w,'cpi_statistics_bureau_first_release':c,
         'status':'SOURCE_PROBE_COMPLETE',
         'green_for_materialization':w['coverage_count']==67 and c['coverage_count']==67,
         'guardrails':['No revised-history substitution','No current/latest static document used as historical vintage',
                       'Month-specific official source required before value extraction','No engine/live/OOS changes'],
         'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False}
    OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'wages':w['coverage_count'],'cpi':c['coverage_count'],'green':obj['green_for_materialization']}))
if __name__=='__main__': main()
