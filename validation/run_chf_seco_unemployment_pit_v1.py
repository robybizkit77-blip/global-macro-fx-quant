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
MONTHS={'januar':1,'februar':2,'märz':3,'maerz':3,'april':4,'mai':5,'juni':6,'juli':7,'august':8,'september':9,'oktober':10,'november':11,'dezember':12}
ANCHORS={
 ('2019-01',2.4),
 ('2020-01',2.3),
 ('2022-11',2.0),
 ('2024-06',2.4),
 ('2026-06',3.1),
}

def get(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=120) as r: return r.read()

def parse_reference_month(text,url):
    s=(text+' '+url).lower().replace('_',' ').replace('-',' ')
    ymatch=re.search(r'\b(2018|2019|2020|2021|2022|2023|2024|2025|2026)\b',s)
    if not ymatch: return None
    year=int(ymatch.group(1))
    m=None
    for name,num in MONTHS.items():
        if name in s: m=num; break
    if m is None:
        # support compact filenames e.g. alz_03_2023, 2406, 1812
        q=re.search(r'(?:alz[ _]|pressedok)?(?:20)?(1[89]|2[0-6])?\s*(0[1-9]|1[0-2])',s)
        if q:
            m=int(q.group(2))
    return f'{year:04d}-{m:02d}' if m else None

def publication_date_from_context(a):
    node=a.parent
    for _ in range(4):
        if node is None: break
        txt=' '.join(node.stripped_strings)
        # German archive uses e.g. 6. Februar 2026 or 04.12.2025
        d=re.search(r'\b(\d{1,2})\.(\d{1,2})\.(20\d{2})\b',txt)
        if d: return f'{int(d.group(3)):04d}-{int(d.group(2)):02d}-{int(d.group(1)):02d}'
        d=re.search(r'\b(\d{1,2})\.\s*(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+(20\d{2})\b',txt,re.I)
        if d:
            m=MONTHS[d.group(2).lower()]
            return f'{int(d.group(3)):04d}-{m:02d}-{int(d.group(1)):02d}'
        node=node.parent
    return None

def archive_links():
    html=get(ARCHIVE)
    soup=BeautifulSoup(html,'html.parser')
    found={}
    for a in soup.find_all('a',href=True):
        href=urljoin(ARCHIVE,a['href'])
        label=' '.join(a.stripped_strings)
        if '.pdf' not in href.lower(): continue
        if 'arbeitsmarkt' not in (href+' '+label).lower(): continue
        ym=parse_reference_month(label,href)
        if not ym or not ('2018-01'<=ym<='2026-09'): continue
        pub=publication_date_from_context(a)
        # prefer German PDF if duplicates
        score=(('/de/' in href.lower())*2 + ('_d.pdf' in href.lower()) + ('de.pdf' in href.lower()))
        old=found.get(ym)
        if old is None or score>old['score']:
            found[ym]={'reference_month':ym,'url':href,'publication_date':pub,'label':label,'score':score}
    return found

def extract_rate(pdf_bytes):
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        texts=[]
        for p in pdf.pages[:8]:
            try: texts.append(p.extract_text(x_tolerance=1.5,y_tolerance=3) or '')
            except Exception: texts.append('')
    text='\n'.join(texts)
    # restrict near unemployment-rate table where possible
    pos=text.lower().find('t1b')
    if pos>=0: text=text[pos:pos+9000]
    # line-based primary parser
    for line in text.splitlines():
        if 'Saisonbereinigt' not in line: continue
        after=line.split('Saisonbereinigt',1)[1]
        nums=re.findall(r'(?<!\d)(\d[\.,]\d)(?!\d)',after)
        if nums:
            x=float(nums[0].replace(',','.'))
            if 0.5<=x<=10: return x,line.strip()
    # wrapped-text fallback: first decimal within 120 chars after keyword
    m=re.search(r'Saisonbereinigt.{0,120}?(\d[\.,]\d)',text,re.S)
    if m:
        x=float(m.group(1).replace(',','.'))
        if 0.5<=x<=10: return x,m.group(0)[:180].replace('\n',' ')
    raise RuntimeError('seasonally adjusted unemployment rate not found')

def main():
    links=archive_links()
    if len(links)<70: raise RuntimeError(f'archive link coverage too short n={len(links)} sample={list(links)[:10]}')
    rows=[]; failures=[]
    for ym in sorted(links):
        meta=links[ym]
        try:
            rate,ctx=extract_rate(get(meta['url']))
            rows.append({**meta,'rate':rate,'parser_context':ctx})
        except Exception as e:
            failures.append({'reference_month':ym,'url':meta['url'],'error':str(e)})
    if len(rows)<65: raise RuntimeError(f'parsed coverage too short n={len(rows)} failures={failures[:8]}')
    by={r['reference_month']:r['rate'] for r in rows}
    anchor_results=[]
    for ym,expected in sorted(ANCHORS):
        got=by.get(ym)
        ok=got is not None and abs(got-expected)<1e-9
        anchor_results.append({'reference_month':ym,'expected':expected,'got':got,'pass':ok})
    if not all(x['pass'] for x in anchor_results): raise RuntimeError(f'anchor mismatch {anchor_results}')
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['reference_month','unemployment_rate_sa_pct','release_date','source','source_url','vintage_policy'])
        for r in rows:
            w.writerow([r['reference_month'],f"{r['rate']:.1f}",r['publication_date'] or '', 'SECO - Die Lage auf dem Arbeitsmarkt',r['url'],'value extracted from archived monthly first-release PDF'])
    payload={
      'schema':'GMFQ_CHF_UNEMPLOYMENT_SA_PIT_V1','status':'PASS' if len(rows)>=65 else 'FAIL','created_at':'2026-10-07',
      'source':'SECO archived monthly Die Lage auf dem Arbeitsmarkt PDFs','archive_url':ARCHIVE,
      'series':'Arbeitslosenquote - Saisonbereinigt','coverage':{'n':len(rows),'first':rows[0]['reference_month'],'last':rows[-1]['reference_month']},
      'anchors':anchor_results,'failures':failures,
      'pit_policy':'use the seasonally adjusted unemployment rate printed in each contemporaneous monthly SECO release; do not substitute the current recomputed SA history',
      'revisions_note':'SECO states seasonal adjustment is recomputed when new observations arrive; archived monthly release values are therefore required for PIT replay',
      'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False
    }
    EVID.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(payload,indent=2,ensure_ascii=False))
if __name__=='__main__': main()
