from __future__ import annotations
import json,re
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

OUT=Path('validation/JPY_WAGES_CPI_DOCUMENT_FORMAT_INSPECTION_V1_2026-10-06.json')
S=requests.Session(); S.headers.update({'User-Agent':'GMFQ-PIT-format-inspection/1.0'})

SAMPLES={
 'wages_2018_01':'https://www.mhlw.go.jp/toukei/itiran/roudou/monthly/30/3001p/3001p.html',
 'wages_2023_07':'https://www.mhlw.go.jp/toukei/itiran/roudou/monthly/r05/2307p/2307p.html',
 'cpi_2018_01':'https://www.e-stat.go.jp/stat-search/files?cycle=1&layout=datalist&month=11010301&page=1&result_back=1&tclass1=000001085955&tclass2val=0&toukei=00200573&tstat=000001084976&year=20180',
 'cpi_2023_07':'https://www.e-stat.go.jp/stat-search/files?cycle=1&layout=datalist&month=23070907&page=1&result_back=1&tclass1=000001150149&tclass2val=0&toukei=00200573&tstat=000001150147&year=20230'
}
KEYS=['きまって支給する給与','所定内給与','現金給与総額','前年比','生鮮食品を除く総合','総合','前年同月比','結果概要']

def dec(r):
    enc=r.apparent_encoding or r.encoding or 'utf-8'
    try:return r.content.decode(enc,errors='replace')
    except:return r.text

def inspect(name,url):
    r=S.get(url,timeout=40,allow_redirects=True)
    text=dec(r); soup=BeautifulSoup(text,'html.parser')
    links=[]
    for a in soup.find_all('a',href=True):
        href=urljoin(r.url,a['href']); label=' '.join(a.stripped_strings)
        low=href.lower()
        if any(x in low for x in ['.pdf','.xls','.xlsx','.csv','.zip']) or any(k in label for k in KEYS):
            links.append({'label':label[:240],'url':href})
    flat=' '.join(soup.stripped_strings)
    snippets=[]
    for k in KEYS:
        start=0
        for _ in range(4):
            p=flat.find(k,start)
            if p<0:break
            snippets.append({'key':k,'text':flat[max(0,p-180):p+380]})
            start=p+len(k)
    return {'requested_url':url,'resolved_url':r.url,'status':r.status_code,'content_type':r.headers.get('content-type'),
            'encoding_detected':r.apparent_encoding,'title':soup.title.get_text(' ',strip=True) if soup.title else None,
            'candidate_links':links[:120],'snippets':snippets[:40],'html_bytes':len(r.content)}

def main():
    out={'schema':'GMFQ_JPY_WAGES_CPI_DOCUMENT_FORMAT_INSPECTION_V1','created_at':'2026-10-06','samples':{}}
    for n,u in SAMPLES.items():
        try:out['samples'][n]=inspect(n,u)
        except Exception as e:out['samples'][n]={'error':type(e).__name__+': '+str(e)}
    out['changes_engine_rules']=False;out['changes_live_data']=False;out['changes_oos_baseline']=False
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k: {'status':v.get('status'),'links':len(v.get('candidate_links',[])),'snippets':len(v.get('snippets',[])),'error':v.get('error')} for k,v in out['samples'].items()},ensure_ascii=False))
if __name__=='__main__':main()
