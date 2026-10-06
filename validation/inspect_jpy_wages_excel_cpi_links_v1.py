from __future__ import annotations
import hashlib, io, json, re
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import pandas as pd

OUT=Path('validation/JPY_WAGES_EXCEL_CPI_LINKS_INSPECTION_V1_2026-10-06.json')
S=requests.Session();S.headers.update({'User-Agent':'GMFQ-PIT-parser-inspection/1.0'})
W={
 '2018-01':'https://www.mhlw.go.jp/toukei/itiran/roudou/monthly/30/3001p/xls/3001c01p.xls',
 '2023-07':'https://www.mhlw.go.jp/toukei/itiran/roudou/monthly/r05/2307p/xls/2307c01p.xlsx'}
C={
 '2018-01':'https://www.e-stat.go.jp/stat-search/files?cycle=1&layout=datalist&month=11010301&page=1&result_back=1&tclass1=000001085955&tclass2val=0&toukei=00200573&tstat=000001084976&year=20180',
 '2023-07':'https://www.e-stat.go.jp/stat-search/files?cycle=1&layout=datalist&month=23070907&page=1&result_back=1&tclass1=000001150149&tclass2val=0&toukei=00200573&tstat=000001150147&year=20230'}

def inspect_excel(url):
    r=S.get(url,timeout=40);r.raise_for_status();b=r.content
    engine='xlrd' if url.lower().endswith('.xls') else 'openpyxl'
    book=pd.ExcelFile(io.BytesIO(b),engine=engine)
    out={'url':url,'status':r.status_code,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'sheets':book.sheet_names,'matches':[]}
    for sh in book.sheet_names[:8]:
        df=pd.read_excel(io.BytesIO(b),sheet_name=sh,header=None,engine=engine,dtype=object)
        for i,row in df.iterrows():
            vals=['' if pd.isna(x) else str(x).strip() for x in row.tolist()]
            joined=' | '.join(vals)
            if 'きまって支給する給与' in joined or '定期給与' in joined:
                out['matches'].append({'sheet':sh,'row_index':int(i),'row':vals[:40],
                  'prev_row':['' if pd.isna(x) else str(x).strip() for x in df.iloc[max(0,i-1)].tolist()[:40]],
                  'next_row':['' if pd.isna(x) else str(x).strip() for x in df.iloc[min(len(df)-1,i+1)].tolist()[:40]]})
    return out

def inspect_cpi_page(url):
    r=S.get(url,timeout=40);r.raise_for_status();soup=BeautifulSoup(r.text,'html.parser');links=[]
    for a in soup.find_all('a',href=True):
        label=' '.join(a.stripped_strings);href=urljoin(r.url,a['href'])
        ll=label.upper();hl=href.lower()
        if any(k in ll for k in ['EXCEL','CSV','XLS','PDF']) or any(k in hl for k in ['download','file-download','.xls','.xlsx','.csv','.pdf']):
            parent=' '.join(a.parent.stripped_strings) if a.parent else label
            links.append({'label':label[:120],'url':href,'context':parent[:500]})
    # include contexts mentioning headline/core and table numbers, even if anchor label generic
    txt=' '.join(soup.stripped_strings)
    snippets=[]
    for key in ['総合','生鮮食品を除く総合','前年同月比','表番号 1','表番号 2']:
        p=txt.find(key)
        if p>=0:snippets.append({'key':key,'text':txt[max(0,p-300):p+800]})
    return {'url':url,'status':r.status_code,'links':links[:250],'snippets':snippets,'html_bytes':len(r.content)}

def main():
    out={'schema':'GMFQ_JPY_WAGES_EXCEL_CPI_LINKS_INSPECTION_V1','created_at':'2026-10-06','wages':{},'cpi':{}}
    for k,u in W.items():
        try:out['wages'][k]=inspect_excel(u)
        except Exception as e:out['wages'][k]={'error':type(e).__name__+': '+str(e)}
    for k,u in C.items():
        try:out['cpi'][k]=inspect_cpi_page(u)
        except Exception as e:out['cpi'][k]={'error':type(e).__name__+': '+str(e)}
    out.update(changes_engine_rules=False,changes_live_data=False,changes_oos_baseline=False)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'wages':{k:{'matches':len(v.get('matches',[])),'error':v.get('error')} for k,v in out['wages'].items()},'cpi':{k:{'links':len(v.get('links',[])),'error':v.get('error')} for k,v in out['cpi'].items()}},ensure_ascii=False))
if __name__=='__main__':main()
