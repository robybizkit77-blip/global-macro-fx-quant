#!/usr/bin/env python3
from __future__ import annotations
import io,csv,json,re,urllib.request
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import pdfplumber

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'history/pit_v1/CHF_UNEMPLOYMENT_SA_FIRST_RELEASE_2018_2026.csv'
EVID=ROOT/'validation/CHF_UNEMPLOYMENT_SA_PIT_V1_2026-10-07.json'
ARCHIVE='https://www.seco.admin.ch/de/arbeitsmarktstatistik-berichte-rechtsgrundlagen'
UA={'User-Agent':'Mozilla/5.0 (compatible; global-macro-fx-quant/1.0)'}
MONTH_NAMES={1:'januar',2:'februar',3:'maerz',4:'april',5:'mai',6:'juni',7:'juli',8:'august',9:'september',10:'oktober',11:'november',12:'dezember'}
MONTHS={**{v:k for k,v in MONTH_NAMES.items()},'märz':3}
ANCHORS={('2019-01',2.4),('2020-01',2.3),('2022-11',2.0),('2024-06',2.4),('2026-06',3.1)}

def get(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=7) as r:return r.read()

def try_get(url):
    try:return get(url)
    except Exception:return None

def next_month_15(year,month):
    return f'{year+1:04d}-01-15' if month==12 else f'{year:04d}-{month+1:02d}-15'

def parse_reference_month(text,url):
    s=(text+' '+url).lower().replace('_',' ').replace('-',' ')
    y=re.search(r'\b(2018|2019|2020|2021|2022|2023|2024|2025|2026)\b',s)
    year=int(y.group(1)) if y else None
    m=None
    for name,num in MONTHS.items():
        if name in s:m=num;break
    if year and m:return f'{year:04d}-{m:02d}'
    q=re.search(r'(?:20)?(1[89]|2[0-6])\s*(0[1-9]|1[0-2])',s)
    if q:return f'{2000+int(q.group(1)):04d}-{int(q.group(2)):02d}'
    return None

def parse_pub(txt):
    d=re.search(r'\b(\d{1,2})\.(\d{1,2})\.(20\d{2})\b',txt)
    return f'{int(d.group(3)):04d}-{int(d.group(2)):02d}-{int(d.group(1)):02d}' if d else None

def new_archive_links():
    soup=BeautifulSoup(get(ARCHIVE),'html.parser');found={}
    for a in soup.find_all('a',href=True):
        href=urljoin(ARCHIVE,a['href']);label=' '.join(a.stripped_strings)
        if '.pdf' not in href.lower() or 'arbeitsmarkt' not in (href+' '+label).lower():continue
        ym=parse_reference_month(label,href)
        if not ym or ym<'2025-01' or ym>'2026-09':continue
        node=a.parent;pub=None
        for _ in range(4):
            if node is None:break
            pub=parse_pub(' '.join(node.stripped_strings))
            if pub:break
            node=node.parent
        found[ym]={'reference_month':ym,'urls':[href],'publication_date':pub,'discovery':'new_archive'}
    return found

def candidate_urls(year,month):
    yy=str(year)[2:];mm=f'{month:02d}';mn=MONTH_NAMES[month];cap=mn.capitalize()
    root='https://www.seco.admin.ch/dam/seco/de/dokumente/Publikationen_Dienstleistungen/Publikationen_Formulare/Arbeit/Arbeitslosenversicherung/Die%20Lage%20auf%20dem%20Arbeitsmarkt/'
    folder='Lage_arbeitsmarkt_2018' if year==2018 else ('Arbeitsmarkt_2019' if year==2019 else f'arbeitsmarkt_{year}')
    p=root+folder+'/'
    pairs=[]
    if year==2018:
        pairs=[(f'Arbeitsmarkt_{cap}_{year}.pdf.download.pdf',f'PRESSEDOK{yy}{mm}_D.pdf'),(f'alz_{mm}_{yy}.pdf.download.pdf',f'PRESSEDOK{yy}{mm}_D.pdf')]
    elif year==2019:
        pairs=[(f'alz_{mm}_{yy}.pdf.download.pdf',f'PRESSEDOK{yy}{mm}_D.pdf'),(f'ALZ_PRESSEDOK{yy}{mm}.pdf.download.pdf',f'PRESSEDOK{yy}{mm}_D.pdf'),(f'ALZ_PRESSEDOK_{yy}{mm}.pdf.download.pdf',f'PRESSEDOK{yy}{mm}_D.pdf')]
    elif year==2020:
        pairs=[(f'alz_{mm}_{year}.pdf.download.pdf',f'PRESSEDOK{yy}{mm}_D.pdf'),(f'alz_pressedok_{yy}{mm}.pdf.download.pdf',f'PRESSEDOK{yy}{mm}_D.pdf'),(f'lage_arbeitsmarkt_{mn}-{year}.pdf.download.pdf',f'PRESSEDOK{yy}{mm}_D.pdf')]
    elif year==2021:
        pairs=[(f'alz_{mm}_{year}.pdf.download.pdf',f'PRESSEDOK{yy}{mm}_D.pdf'),(f'alz_{mm}_{yy}.pdf.download.pdf',f'PRESSEDOK{yy}{mm}_D.pdf'),(f'alz_{mm}_{year}.pdf.download.pdf',f'alz_{mn}_{year}_de.pdf'),(f'lage_arbeitsmarkt_{mn}-{year}.pdf.download.pdf',f'PRESSEDOK{yy}{mm}_D.pdf')]
    elif year==2022:
        pairs=[(f'lage_arbeitsmarkt_{mn}_{year}.pdf.download.pdf',f'PRESSEDOK{yy}{mm}_D.pdf'),(f'lage_arbeitsmarkt_{mn}-{year}.pdf.download.pdf',f'PRESSEDOK{yy}{mm}_D.pdf'),(f'alz_{mm}_{yy}.pdf.download.pdf',f'PRESSEDOK{yy}{mm}_D.pdf'),(f'alz_{mm}_{year}.pdf.download.pdf',f'PRESSEDOK{yy}{mm}_D.pdf')]
    elif year==2023:
        pairs=[(f'alz_{mm}_{year}.pdf.download.pdf',f'alz_{mm}_{year}_de.pdf'),(f'alz_{mm}_{year}.pdf.download.pdf',f'PRESSEDOK{yy}{mm}_D.pdf'),(f'lage_arbeitsmarkt_{mn}_{year}.pdf.download.pdf',f'PRESSEDOK{yy}{mm}_D.pdf')]
    elif year==2024:
        pairs=[(f'lage_arbeitsmarkt_{mn}_{year}.pdf.download.pdf',f'PRESSEDOK{yy}{mm}_D.pdf'),(f'lage_arbeitsmarkt_{mn}-{year}.pdf.download.pdf',f'PRESSEDOK{yy}{mm}_D.pdf'),(f'large_arbeitsmarkt_{mn}_{year}.pdf.download.pdf',f'{year}-{mm}_Die_Lage_auf_dem_Arbeitsmarkt_DE.pdf')]
    return [p+s+'/'+t for s,t in pairs]

def all_months():
    found=new_archive_links()
    for year in range(2018,2025):
        for month in range(1,13):
            ym=f'{year:04d}-{month:02d}'
            found.setdefault(ym,{'reference_month':ym,'urls':candidate_urls(year,month),'publication_date':next_month_15(year,month),'discovery':'deterministic_asset_fallback_conservative_timing'})
    return found

def extract_rate(pdf_bytes):
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text='\n'.join((p.extract_text(x_tolerance=1.5,y_tolerance=3) or '') for p in pdf.pages[:8])
    pos=text.lower().find('t1b')
    if pos>=0:text=text[pos:pos+10000]
    for line in text.splitlines():
        if 'Saisonbereinigt' not in line:continue
        nums=re.findall(r'(?<!\d)(\d[\.,]\d)(?!\d)',line.split('Saisonbereinigt',1)[1])
        if nums:
            x=float(nums[0].replace(',','.'))
            if 0.5<=x<=10:return x,line.strip()
    m=re.search(r'Saisonbereinigt.{0,180}?(\d[\.,]\d)',text,re.S)
    if m:
        x=float(m.group(1).replace(',','.'))
        if 0.5<=x<=10:return x,m.group(0)[:220].replace('\n',' ')
    raise RuntimeError('seasonally adjusted unemployment rate not found')

def main():
    metas=all_months();rows=[];failures=[]
    for ym in sorted(metas):
        meta=metas[ym];success=None;errs=[]
        for url in meta['urls']:
            raw=try_get(url)
            if raw is None:continue
            try:rate,ctx=extract_rate(raw);success=(url,rate,ctx);break
            except Exception as e:errs.append(str(e))
        if success:
            url,rate,ctx=success;rows.append({**meta,'url':url,'rate':rate,'parser_context':ctx})
        else:failures.append({'reference_month':ym,'n_candidates':len(meta['urls']),'errors':errs[:3]})
    if len(rows)<65:raise RuntimeError(f'parsed coverage too short n={len(rows)} failures={failures[:20]}')
    by={r['reference_month']:r['rate'] for r in rows};anchor_results=[]
    for ym,expected in sorted(ANCHORS):
        got=by.get(ym);ok=got is not None and abs(got-expected)<1e-9
        anchor_results.append({'reference_month':ym,'expected':expected,'got':got,'pass':ok})
    if not all(x['pass'] for x in anchor_results):raise RuntimeError(f'anchor mismatch {anchor_results}')
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['reference_month','unemployment_rate_sa_pct','available_from','timing_quality','source','source_url','vintage_policy'])
        for r in rows:w.writerow([r['reference_month'],f"{r['rate']:.1f}",r['publication_date'] or '','ACTUAL_ARCHIVE_DATE' if r['discovery']=='new_archive' else 'CONSERVATIVE_15TH_NEXT_MONTH','SECO - Die Lage auf dem Arbeitsmarkt',r['url'],'value extracted from archived monthly first-release PDF'])
    payload={'schema':'GMFQ_CHF_UNEMPLOYMENT_SA_PIT_V1','status':'PASS','created_at':'2026-10-07','source':'SECO archived monthly Die Lage auf dem Arbeitsmarkt PDFs','series':'Arbeitslosenquote - Saisonbereinigt','coverage':{'n':len(rows),'first':rows[0]['reference_month'],'last':rows[-1]['reference_month']},'anchors':anchor_results,'failures':failures,'timing_policy':'actual archive release date when available; otherwise conservative 15th of following month, deliberately later than normal SECO release timing','pit_policy':'use the SA unemployment rate printed in each contemporaneous monthly SECO PDF; never substitute current recomputed SA history','changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False}
    EVID.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(payload,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
