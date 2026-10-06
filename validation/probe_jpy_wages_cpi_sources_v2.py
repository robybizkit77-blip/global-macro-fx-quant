from __future__ import annotations
import json, re, time
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

OUT=Path('validation/JPY_WAGES_CPI_SOURCE_PROBE_V2_2026-10-06.json')
START=(2018,1); END=(2023,7)
S=requests.Session(); S.headers.update({'User-Agent':'GMFQ-PIT-source-audit/2.0 (+research validation)'})


def months():
    y,m=START; out=[]
    while (y,m)<=END:
        out.append(f'{y:04d}-{m:02d}'); m+=1
        if m==13: y+=1; m=1
    return out
TARGET=months()


def get(url, timeout=35):
    r=S.get(url,timeout=timeout)
    return r


def decode_jp(r):
    enc=r.apparent_encoding or r.encoding or 'utf-8'
    try: return r.content.decode(enc,errors='replace')
    except Exception: return r.text


def jp_ym(text):
    text=re.sub(r'\s+','',text)
    m=re.search(r'平成(\d+)年(\d{1,2})月',text)
    if m:
        return 1988+int(m.group(1)), int(m.group(2))
    m=re.search(r'令和(元|\d+)年(\d{1,2})月',text)
    if m:
        ry=1 if m.group(1)=='元' else int(m.group(1))
        return 2018+ry, int(m.group(2))
    m=re.search(r'(20\d{2})年(\d{1,2})月',text)
    if m: return int(m.group(1)),int(m.group(2))
    return None


def probe_mhlw():
    idx='https://www.mhlw.go.jp/toukei/list/30-1a.html'
    r=get(idx); html=decode_jp(r); soup=BeautifulSoup(html,'html.parser')
    hrefs=[]
    for a in soup.find_all('a',href=True):
        href=urljoin(idx,a['href'])
        if '/toukei/itiran/roudou/monthly/' in href and re.search(r'p(?:/[^/]+)?\.html(?:$|\?)',href):
            hrefs.append(href.split('#')[0])
    # de-dupe, keep order
    seen=set(); hrefs=[u for u in hrefs if not (u in seen or seen.add(u))]
    found={}; checked=0; failures=[]
    for u in hrefs:
        try:
            rr=get(u,25); checked+=1
            if not rr.ok: continue
            txt=BeautifulSoup(decode_jp(rr),'html.parser').get_text(' ',strip=True)
            ym=jp_ym(txt[:12000])
            if not ym: continue
            k=f'{ym[0]:04d}-{ym[1]:02d}'
            if k in TARGET:
                found.setdefault(k,[]).append({'page_url':u,'http_status':rr.status_code})
        except Exception as e: failures.append({'url':u,'error':type(e).__name__})
        if len(found)==67: break
    return {'index_url':idx,'index_status':r.status_code,'candidate_pages_checked':checked,
            'coverage_count':sum(k in found for k in TARGET),'missing_months':[k for k in TARGET if k not in found],
            'months_found':found,'request_failures':failures[:20]}


def year_near_anchor(a):
    # Search progressively wider ancestors for a 4-digit Gregorian year label.
    node=a
    for _ in range(8):
        node=getattr(node,'parent',None)
        if node is None: break
        t=' '.join(node.stripped_strings)
        ys=re.findall(r'(20\d{2})年',t)
        if ys:
            # nearest year-like text is normally first in the local list block
            return int(ys[0])
    # fallback: walk previous elements
    for p in a.find_all_previous(string=re.compile(r'20\d{2}年'),limit=5):
        m=re.search(r'(20\d{2})年',str(p))
        if m: return int(m.group(1))
    return None


def collect_estat(base_url, wanted):
    r=get(base_url); soup=BeautifulSoup(r.text,'html.parser')
    found={}
    for a in soup.find_all('a',href=True):
        label=' '.join(a.stripped_strings)
        mm=re.fullmatch(r'(\d{1,2})月',label)
        if not mm: continue
        y=year_near_anchor(a)
        if not y: continue
        k=f'{y:04d}-{int(mm.group(1)):02d}'
        if k in wanted:
            found[k]={'month_list_url':urljoin(base_url,a['href']),'collection_url':base_url}
    return r.status_code,found


def probe_cpi():
    base2015='https://www.e-stat.go.jp/stat-search/files?cycle=1&layout=datalist&page=1&tclass1=000001085955&toukei=00200573&tstat=000001084976'
    base2020='https://www.e-stat.go.jp/stat-search/files?cycle=1&layout=datalist&page=1&tclass1=000001150149&toukei=00200573&tstat=000001150147'
    w15={m for m in TARGET if m<='2021-06'}
    w20={m for m in TARGET if m>='2021-07'}
    s15,f15=collect_estat(base2015,w15)
    s20,f20=collect_estat(base2020,w20)
    found={**f15,**f20}
    verified={}; failures=[]
    # Require each month-specific e-Stat result page to resolve successfully.
    for k,v in found.items():
        try:
            rr=get(v['month_list_url'],25)
            if rr.ok and ('消費者物価指数' in rr.text or 'stat-search' in rr.url):
                verified[k]={**v,'http_status':rr.status_code,'resolved_url':rr.url}
        except Exception as e: failures.append({'month':k,'error':type(e).__name__})
    return {'2015_base_collection':base2015,'2015_status':s15,'2020_base_collection':base2020,'2020_status':s20,
            'coverage_count':sum(k in verified for k in TARGET),'missing_months':[k for k in TARGET if k not in verified],
            'months_found':verified,'request_failures':failures[:20],
            'note':'These are month-specific official e-Stat result pages. Materialization still requires selecting the contemporaneous national monthly report file and storing its URL plus SHA-256 checksum.'}


def main():
    wages=probe_mhlw(); cpi=probe_cpi()
    obj={'schema':'GMFQ_JPY_WAGES_CPI_SOURCE_PROBE_V2','created_at':'2026-10-06','required_months':67,
         'target_coverage':'2018-01 through 2023-07','wages_mhlw_preliminary':wages,
         'cpi_estat_monthly_reports':cpi,
         'green_for_document_materialization':wages['coverage_count']==67 and cpi['coverage_count']==67,
         'guardrails':['Official MHLW preliminary pages only','Official e-Stat CPI monthly-report collections only','No revised-history fallback','No static latest-document substitution','No engine/live/OOS changes'],
         'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False}
    OUT.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'wages':wages['coverage_count'],'cpi':cpi['coverage_count'],'green':obj['green_for_document_materialization']}))

if __name__=='__main__': main()
