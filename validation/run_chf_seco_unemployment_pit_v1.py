#!/usr/bin/env python3
from __future__ import annotations
import io,csv,json,re,urllib.request
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import pdfplumber

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'history/pit_v1/CHF_UNEMPLOYMENT_SA_FIRST_RELEASE_2019_2026.csv'
EVID=ROOT/'validation/CHF_UNEMPLOYMENT_SA_PIT_V1_2026-10-07.json'
ARCHIVE='https://www.seco.admin.ch/de/arbeitsmarktstatistik-berichte-rechtsgrundlagen'
UA={'User-Agent':'Mozilla/5.0 (compatible; global-macro-fx-quant/1.0)'}
MONTH_NAMES={1:'januar',2:'februar',3:'maerz',4:'april',5:'mai',6:'juni',7:'juli',8:'august',9:'september',10:'oktober',11:'november',12:'dezember'}
MONTHS={**{v:k for k,v in MONTH_NAMES.items()},'märz':3}
ANCHORS={('2019-01',2.4),('2020-01',2.3),('2022-11',2.0),('2024-06',2.4),('2026-06',3.1)}
LEGACY={
'2019-01':'https://www.seco.admin.ch/dam/seco/de/dokumente/Publikationen_Dienstleistungen/Publikationen_Formulare/Arbeit/Arbeitslosenversicherung/Die%20Lage%20auf%20dem%20Arbeitsmarkt/Arbeitsmarkt_2019/alz_01_19.pdf.download.pdf/PRESSEDOK1901_D.pdf',
'2020-01':'https://www.seco.admin.ch/dam/seco/de/dokumente/Publikationen_Dienstleistungen/Publikationen_Formulare/Arbeit/Arbeitslosenversicherung/Die%20Lage%20auf%20dem%20Arbeitsmarkt/arbeitsmarkt_2020/pressedok_alz_01_20.pdf.download.pdf/pressedok_alz_01_20_de.pdf'}

def get(url,timeout=15):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=timeout) as r:return r.read()

def try_get(url):
    try:return get(url)
    except Exception:return None

def parse_ref(text,url):
    s=(text+' '+url).lower().replace('_',' ').replace('-',' ')
    y=re.search(r'\b(2019|2020|2021|2022|2023|2024|2025|2026)\b',s)
    if not y:return None
    m=next((n for k,n in MONTHS.items() if k in s),None)
    if m is None:
        q=re.search(r'(?:19|20|21|22|23|24|25|26)\s*(0[1-9]|1[0-2])',s)
        if q:m=int(q.group(1))
    return f'{int(y.group(1)):04d}-{m:02d}' if m else None

def parse_pub(text):
    d=re.search(r'\b(\d{1,2})\.(\d{1,2})\.(20\d{2})\b',text)
    return f'{int(d.group(3)):04d}-{int(d.group(2)):02d}-{int(d.group(1)):02d}' if d else None

def monthly_page(year,month):
    b='https://www.seco.admin.ch/seco/de/home/Publikationen_Dienstleistungen/Publikationen_und_Formulare/Arbeit/Arbeitslosenversicherung/Die_Lage_auf_dem_Arbeitsmarkt/'
    return f'{b}lage_arbeitsmarkt_{year}/lage_arbeitsmarkt_{MONTH_NAMES[month]}_{year}.html'

def discover_one(year,month):
    ym=f'{year:04d}-{month:02d}';page=monthly_page(year,month);raw=try_get(page)
    if raw is None:return None,{'reference_month':ym,'stage':'monthly_page','url':page}
    soup=BeautifulSoup(raw,'html.parser');whole=' '.join(soup.stripped_strings);pub=parse_pub(whole)
    for a in soup.find_all('a',href=True):
        href=urljoin(page,a['href'])
        if '.pdf' in href.lower() and 'arbeitsmarkt' in href.lower():
            return {'reference_month':ym,'url':href,'publication_date':pub,'timing_quality':'ACTUAL_RELEASE_PAGE_DATE'},None
    return None,{'reference_month':ym,'stage':'no_pdf_link','url':page}

def discover_mid():
    found={};fail=[]
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs=[ex.submit(discover_one,y,m) for y in range(2021,2025) for m in range(1,13)]
        for f in as_completed(futs):
            meta,err=f.result()
            if meta:found[meta['reference_month']]=meta
            elif err:fail.append(err)
    return found,fail

def discover_current():
    soup=BeautifulSoup(get(ARCHIVE),'html.parser');found={}
    for a in soup.find_all('a',href=True):
        href=urljoin(ARCHIVE,a['href']);label=' '.join(a.stripped_strings)
        if '.pdf' not in href.lower() or 'arbeitsmarkt' not in (href+' '+label).lower():continue
        ym=parse_ref(label,href)
        if not ym or not ('2025-01'<=ym<='2026-09'):continue
        node=a.parent;pub=None
        for _ in range(5):
            if node is None:break
            pub=parse_pub(' '.join(node.stripped_strings))
            if pub:break
            node=node.parent
        found[ym]={'reference_month':ym,'url':href,'publication_date':pub,'timing_quality':'ACTUAL_ARCHIVE_DATE'}
    return found

def extract_rate(raw):
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        text='\n'.join((p.extract_text(x_tolerance=1.5,y_tolerance=3) or '') for p in pdf.pages[:9])
    pos=text.lower().find('t1b')
    if pos>=0:text=text[pos:pos+12000]
    for line in text.splitlines():
        if 'Saisonbereinigt' in line:
            nums=re.findall(r'(?<!\d)(\d[\.,]\d)(?!\d)',line.split('Saisonbereinigt',1)[1])
            if nums:
                x=float(nums[0].replace(',','.'))
                if 0.5<=x<=10:return x
    m=re.search(r'Saisonbereinigt.{0,200}?(\d[\.,]\d)',text,re.S)
    if m:
        x=float(m.group(1).replace(',','.'))
        if 0.5<=x<=10:return x
    raise RuntimeError('SA unemployment not found')

def parse_meta(meta):
    raw=try_get(meta['url'])
    if raw is None:return None,{'reference_month':meta['reference_month'],'stage':'pdf_download','url':meta['url']}
    try:return {**meta,'rate':extract_rate(raw)},None
    except Exception as e:return None,{'reference_month':meta['reference_month'],'stage':'pdf_parse','url':meta['url'],'error':str(e)}

def main():
    metas={
      '2019-01':{'reference_month':'2019-01','url':LEGACY['2019-01'],'publication_date':'2019-02-15','timing_quality':'CONSERVATIVE_15TH_NEXT_MONTH'},
      '2020-01':{'reference_month':'2020-01','url':LEGACY['2020-01'],'publication_date':'2020-02-10','timing_quality':'ACTUAL_PDF_DATE'}}
    mid,failures=discover_mid();metas.update(mid);metas.update(discover_current())
    rows=[]
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs=[ex.submit(parse_meta,m) for m in metas.values()]
        for f in as_completed(futs):
            row,err=f.result()
            if row:rows.append(row)
            elif err:failures.append(err)
    rows.sort(key=lambda r:r['reference_month']);failures.sort(key=lambda r:r['reference_month'])
    if len(rows)<65:raise RuntimeError(f'parsed coverage too short n={len(rows)} failures={failures[:25]}')
    by={r['reference_month']:r['rate'] for r in rows};anchors=[]
    for ym,expected in sorted(ANCHORS):
        got=by.get(ym);ok=got is not None and abs(got-expected)<1e-9;anchors.append({'reference_month':ym,'expected':expected,'got':got,'pass':ok})
    if not all(a['pass'] for a in anchors):raise RuntimeError(f'anchor mismatch {anchors}')
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['reference_month','unemployment_rate_sa_pct','available_from','timing_quality','source','source_url','vintage_policy'])
        for r in rows:w.writerow([r['reference_month'],f"{r['rate']:.1f}",r['publication_date'] or '',r['timing_quality'],'SECO - Die Lage auf dem Arbeitsmarkt',r['url'],'contemporaneous archived monthly release PDF'])
    payload={'schema':'GMFQ_CHF_UNEMPLOYMENT_SA_PIT_V1','status':'PASS','created_at':'2026-10-07','source':'SECO archived monthly releases','series':'Arbeitslosenquote - Saisonbereinigt','coverage':{'n':len(rows),'first':rows[0]['reference_month'],'last':rows[-1]['reference_month'],'continuous_replay_core':'2021-01 onward subject to listed gaps'},'anchors':anchors,'failures':failures,'timing_policy':'actual release dates except Jan-2019 conservative 15th next month','pit_policy':'contemporaneous SA rate only; never current recomputed history','replay_scope_note':'2019/2020 anchors; replay uses 2021+ core consistent with SNB FX transactions','changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False}
    EVID.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(payload,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
