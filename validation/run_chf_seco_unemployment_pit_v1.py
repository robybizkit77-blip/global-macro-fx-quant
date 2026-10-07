#!/usr/bin/env python3
from __future__ import annotations
import io,csv,json,re,urllib.request,urllib.error
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import pdfplumber

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'history/pit_v1/CHF_UNEMPLOYMENT_SA_FIRST_RELEASE_2018_2026.csv'
EVID=ROOT/'validation/CHF_UNEMPLOYMENT_SA_PIT_V1_2026-10-07.json'
ARCHIVE='https://www.seco.admin.ch/de/arbeitsmarktstatistik-berichte-rechtsgrundlagen'
OLD_BASE='https://www.seco.admin.ch/seco/de/home/Publikationen_Dienstleistungen/Publikationen_und_Formulare/Arbeit/Arbeitslosenversicherung/Die_Lage_auf_dem_Arbeitsmarkt/'
UA={'User-Agent':'Mozilla/5.0 (compatible; global-macro-fx-quant/1.0)'}
MONTHS={'januar':1,'februar':2,'märz':3,'maerz':3,'april':4,'mai':5,'juni':6,'juli':7,'august':8,'september':9,'oktober':10,'november':11,'dezember':12}
ANCHORS={('2019-01',2.4),('2020-01',2.3),('2022-11',2.0),('2024-06',2.4),('2026-06',3.1)}

def get(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=120) as r:return r.read()

def try_get(url):
    try:return get(url)
    except Exception:return None

def parse_reference_month(text,url):
    s=(text+' '+url).lower().replace('_',' ').replace('-',' ')
    year=None
    ymatch=re.search(r'\b(2018|2019|2020|2021|2022|2023|2024|2025|2026)\b',s)
    if ymatch:year=int(ymatch.group(1))
    if year is None:
        q=re.search(r'(?:pressedok|alz|arbeitsmarkt)?\s*(1[89]|2[0-6])(0[1-9]|1[0-2])',s)
        if q:year=2000+int(q.group(1))
    if year is None:return None
    m=None
    for name,num in MONTHS.items():
        if name in s:m=num;break
    if m is None:
        q=re.search(r'(?:alz|pressedok|arbeitsmarkt)[^0-9]{0,5}(?:20)?(?:1[89]|2[0-6])?[ _-]?(0[1-9]|1[0-2])',s)
        if q:m=int(q.group(1))
        else:
            q=re.search(r'(?:20)?(?:1[89]|2[0-6])(0[1-9]|1[0-2])',s)
            if q:m=int(q.group(1))
    return f'{year:04d}-{m:02d}' if m else None

def parse_pub_text(txt):
    d=re.search(r'\b(\d{1,2})\.(\d{1,2})\.(20\d{2})\b',txt)
    if d:return f'{int(d.group(3)):04d}-{int(d.group(2)):02d}-{int(d.group(1)):02d}'
    d=re.search(r'\b(\d{1,2})\.\s*(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+(20\d{2})\b',txt,re.I)
    if d:return f'{int(d.group(3)):04d}-{MONTHS[d.group(2).lower()]:02d}-{int(d.group(1)):02d}'
    return None

def publication_date_from_context(a):
    node=a.parent
    for _ in range(5):
        if node is None:break
        d=parse_pub_text(' '.join(node.stripped_strings))
        if d:return d
        node=node.parent
    return None

def put(found,ym,href,pub,label,score=0):
    if not ym or not ('2018-01'<=ym<='2026-09'):return
    old=found.get(ym)
    if old is None or score>old['score']:
        found[ym]={'reference_month':ym,'url':href,'publication_date':pub,'label':label,'score':score}

def scan_page_for_pdfs(page_url,found,default_ym=None):
    raw=try_get(page_url)
    if raw is None:return
    soup=BeautifulSoup(raw,'html.parser')
    whole=' '.join(soup.stripped_strings)
    page_pub=parse_pub_text(whole)
    for a in soup.find_all('a',href=True):
        href=urljoin(page_url,a['href']);label=' '.join(a.stripped_strings)
        if '.pdf' not in href.lower():continue
        if 'arbeitsmarkt' not in (href+' '+label).lower():continue
        ym=parse_reference_month(label,href) or default_ym
        pub=publication_date_from_context(a) or page_pub
        score=(('/de/' in href.lower())*2+('_d.pdf' in href.lower())+('de.pdf' in href.lower()))
        put(found,ym,href,pub,label,score)

def archive_links():
    found={}
    # New archive: direct PDFs for current/previous year.
    scan_page_for_pdfs(ARCHIVE,found)
    # Legacy annual archive pages. Some link directly to PDFs, others to one monthly HTML page.
    for year in range(2018,2025):
        variants=[
          f'Lage_Arbeitsmarkt_{year}.html',f'lage_arbeitsmarkt_{year}.html',
          f'Die_Lage_auf_dem_Arbeitsmarkt_{year}.html'
        ]
        annual=None;annual_url=None
        for v in variants:
            u=urljoin(OLD_BASE,v);raw=try_get(u)
            if raw is not None:annual=raw;annual_url=u;break
        if annual is None:continue
        soup=BeautifulSoup(annual,'html.parser')
        # direct PDFs if any
        scan_page_for_pdfs(annual_url,found)
        # monthly child pages
        for a in soup.find_all('a',href=True):
            href=urljoin(annual_url,a['href']);label=' '.join(a.stripped_strings)
            ym=parse_reference_month(label,href)
            if not ym or not ym.startswith(str(year)):continue
            if '.pdf' in href.lower():continue
            if not href.lower().endswith(('.html','.htm')):continue
            scan_page_for_pdfs(href,found,default_ym=ym)
    return found

def extract_rate(pdf_bytes):
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        texts=[]
        for p in pdf.pages[:8]:
            try:texts.append(p.extract_text(x_tolerance=1.5,y_tolerance=3) or '')
            except Exception:texts.append('')
    text='\n'.join(texts)
    pos=text.lower().find('t1b')
    if pos>=0:text=text[pos:pos+9000]
    for line in text.splitlines():
        if 'Saisonbereinigt' not in line:continue
        after=line.split('Saisonbereinigt',1)[1]
        nums=re.findall(r'(?<!\d)(\d[\.,]\d)(?!\d)',after)
        if nums:
            x=float(nums[0].replace(',','.'))
            if 0.5<=x<=10:return x,line.strip()
    m=re.search(r'Saisonbereinigt.{0,160}?(\d[\.,]\d)',text,re.S)
    if m:
        x=float(m.group(1).replace(',','.'))
        if 0.5<=x<=10:return x,m.group(0)[:220].replace('\n',' ')
    raise RuntimeError('seasonally adjusted unemployment rate not found')

def main():
    links=archive_links()
    if len(links)<70:raise RuntimeError(f'archive link coverage too short n={len(links)} sample={list(links)[:20]}')
    rows=[];failures=[]
    for ym in sorted(links):
        meta=links[ym]
        try:
            rate,ctx=extract_rate(get(meta['url']))
            rows.append({**meta,'rate':rate,'parser_context':ctx})
        except Exception as e:failures.append({'reference_month':ym,'url':meta['url'],'error':str(e)})
    if len(rows)<65:raise RuntimeError(f'parsed coverage too short n={len(rows)} failures={failures[:12]}')
    by={r['reference_month']:r['rate'] for r in rows}
    anchor_results=[]
    for ym,expected in sorted(ANCHORS):
        got=by.get(ym);ok=got is not None and abs(got-expected)<1e-9
        anchor_results.append({'reference_month':ym,'expected':expected,'got':got,'pass':ok})
    if not all(x['pass'] for x in anchor_results):raise RuntimeError(f'anchor mismatch {anchor_results}')
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['reference_month','unemployment_rate_sa_pct','release_date','source','source_url','vintage_policy'])
        for r in rows:w.writerow([r['reference_month'],f"{r['rate']:.1f}",r['publication_date'] or '','SECO - Die Lage auf dem Arbeitsmarkt',r['url'],'value extracted from archived monthly first-release PDF'])
    payload={'schema':'GMFQ_CHF_UNEMPLOYMENT_SA_PIT_V1','status':'PASS','created_at':'2026-10-07','source':'SECO archived monthly Die Lage auf dem Arbeitsmarkt PDFs','archive_url':ARCHIVE,'series':'Arbeitslosenquote - Saisonbereinigt','coverage':{'n':len(rows),'first':rows[0]['reference_month'],'last':rows[-1]['reference_month']},'anchors':anchor_results,'failures':failures,'pit_policy':'use the seasonally adjusted unemployment rate printed in each contemporaneous monthly SECO release; do not substitute the current recomputed SA history','revisions_note':'SECO states seasonal adjustment is recomputed when new observations arrive; archived monthly release values are therefore required for PIT replay','changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False}
    EVID.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(payload,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
