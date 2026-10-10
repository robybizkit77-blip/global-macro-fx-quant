#!/usr/bin/env python3
from __future__ import annotations

import argparse,csv,hashlib,html,json,re,time,urllib.error,urllib.request
from datetime import date,datetime,timedelta,timezone
from html.parser import HTMLParser
from pathlib import Path

START=(2018,1)
END=(2026,9)
MONTHS=['january','february','march','april','may','june','july','august','september','october','november','december']
ROW_KEYS=['reference_month','headline_hicp_yoy_pct','release_date','source_url','page_sha256','source_route','pit_status']
SEMANTIC_KEYS=['reference_month','headline_hicp_yoy_pct','release_date','source_route','pit_status']
MIN_REQUEST_INTERVAL_SECONDS=1.25
_LAST_REQUEST_AT=0.0

class Text(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]
    def handle_data(self,data):
        s=' '.join(data.split())
        if s:self.parts.append(s)

def text_from_html(raw:bytes)->str:
    p=Text(); p.feed(raw.decode('utf-8',errors='replace')); return html.unescape(' '.join(p.parts))

def months():
    y,m=START
    while (y,m)<=END:
        yield y,m; m+=1
        if m==13:y+=1;m=1

def last_weekday_of_month(y:int,m:int)->date:
    nxt=date(y+1,1,1) if m==12 else date(y,m+1,1)
    d=nxt-timedelta(days=1)
    while d.weekday()>=5: d-=timedelta(days=1)
    return d

def candidate_dates(y:int,m:int):
    # Eurostat flash estimates are normally released on the last working day
    # of the reference month or shortly thereafter. The search order is fixed
    # and deliberately narrow; it does not broaden the source contract.
    anchor=last_weekday_of_month(y,m)
    ordered=[anchor]
    d=anchor
    while len(ordered)<6:
        d+=timedelta(days=1)
        if d.weekday()<5: ordered.append(d)
    d=anchor
    while len(ordered)<9:
        d-=timedelta(days=1)
        if d.weekday()<5: ordered.append(d)
    yield from ordered

def urls_for(d:date):
    key=d.strftime('%d%m%Y')
    legacy=('EUROSTAT_EURO_INDICATORS_LEGACY',f'https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-{key}-AP')
    modern=('EUROSTAT_EURO_INDICATORS_WEB',f'https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-{key}-ap')
    return [legacy,modern] if d.year<=2024 else [modern,legacy]

def throttle():
    global _LAST_REQUEST_AT
    now=time.monotonic()
    wait=MIN_REQUEST_INTERVAL_SECONDS-(now-_LAST_REQUEST_AT)
    if wait>0: time.sleep(wait)
    _LAST_REQUEST_AT=time.monotonic()

def fetch(url:str):
    req=urllib.request.Request(url,headers={'User-Agent':'global-macro-fx-quant/1.0 strict-pit'})
    for attempt in range(8):
        throttle()
        try:
            with urllib.request.urlopen(req,timeout=30) as r:
                raw=r.read(); final=r.geturl(); return raw,final
        except urllib.error.HTTPError as e:
            if e.code in (404,410): return None
            if e.code==429 and attempt<7:
                retry_after=e.headers.get('Retry-After') if e.headers else None
                try:
                    delay=max(15.0,float(retry_after)) if retry_after else min(120.0,15.0*(2**attempt))
                except (TypeError,ValueError):
                    delay=min(120.0,15.0*(2**attempt))
                print(f'[transport] Eurostat 429; retry same URL in {delay:.0f}s attempt={attempt+1}/8',flush=True)
                time.sleep(delay)
                continue
            raise

def parse_period(text:str,y:int,m:int):
    month=MONTHS[m-1].capitalize(); period=f'{month} {y}'
    if re.search(rf'Flash estimate\s*[-–]\s*{re.escape(period)}',text,re.I) is None:
        if re.search(rf'expected to be\s+[-0-9.]+\s*%\s+in\s+{re.escape(month)}(?:\s+{y})?',text,re.I) is None:
            return None
    pats=[
      rf'Euro area annual inflation is expected to be\s+(-?[0-9]+(?:\.[0-9]+)?)\s*%\s+in\s+{re.escape(month)}',
      rf'Euro area annual inflation\s+is expected to be\s+(-?[0-9]+(?:\.[0-9]+)?)%\s+in\s+{re.escape(month)}',
      rf'In\s+{re.escape(month)}\s+{y}[^.]*?Euro area annual inflation is expected to be\s+(-?[0-9]+(?:\.[0-9]+)?)%'
    ]
    vals=[]
    for p in pats:
        vals += [float(x.group(1)) for x in re.finditer(p,text,re.I)]
    uniq=[]
    for v in vals:
        if all(abs(v-u)>1e-12 for u in uniq): uniq.append(v)
    if len(uniq)!=1: raise ValueError(f'ambiguous flash headline for {period}: {uniq}')
    return uniq[0]

def one(y:int,m:int):
    ref=f'{y:04d}-{m:02d}'; hits=[]
    for d in candidate_dates(y,m):
        for route,url in urls_for(d):
            got=fetch(url)
            if got is None: continue
            raw,final=got; text=text_from_html(raw); value=parse_period(text,y,m)
            if value is None: continue
            hits.append((d.isoformat(),value,final,hashlib.sha256(raw).hexdigest(),route))
            break
        if hits: break
    if len(hits)!=1: raise ValueError(f'expected one official Eurostat flash release for {ref}, got {hits}')
    rd,value,url,sha,route=hits[0]
    return {'reference_month':ref,'headline_hicp_yoy_pct':value,'release_date':rd,'source_url':url,'page_sha256':sha,'source_route':route,'pit_status':'STRICT_FIRST_RELEASE_FLASH'}

def digest(rows):
    canon=[{k:r[k] for k in SEMANTIC_KEYS} for r in rows]
    return hashlib.sha256(json.dumps(canon,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def write_progress(csv_path:str,evidence_path:str,rows:list[dict],status:str,last_error:str|None=None):
    p=Path(csv_path); p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=ROW_KEYS,lineterminator='\n'); w.writeheader(); w.writerows(rows)
    ev={
      'schema':'GMFQ_EUR_INFLATION_STRICT_PIT_EVIDENCE_V1_RUNTIME',
      'status':status,'target':'EUR.inflation','evidence_class':'STRICT_DIRECT_ARCHIVAL_PIT',
      'authority':'Eurostat',
      'coverage':{'start':'2018-01','end':'2026-09','expected_months':105,'materialized_months':len(rows)},
      'series_contract':{'series_id':'EA_HICP_HEADLINE_YOY','frequency':'M','transformation':'reported_yoy_rate','unit':'% YoY','first_release_semantics':'FLASH_ESTIMATE'},
      'unique_page_hashes':len({r['page_sha256'] for r in rows}),
      'semantic_rowset_sha256':digest(rows),
      'semantic_fingerprint_fields':SEMANTIC_KEYS,
      'strict_rules':{'official_publisher_only':True,'period_specific_release_artifact_required':True,'publication_date_required':True,'url_and_sha256_required':True,'current_revised_history_forbidden':True,'final_release_fallback_forbidden':True,'revised_history_fallback_used':False},
      'last_materialized_month':rows[-1]['reference_month'] if rows else None,
      'last_error':last_error,
      'generated_at_utc':datetime.now(timezone.utc).isoformat(),
    }
    Path(evidence_path).write_text(json.dumps(ev,indent=2)+'\n',encoding='utf-8')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--csv',required=True); ap.add_argument('--evidence',required=True); a=ap.parse_args()
    rows=[]; total=105
    try:
        for i,(y,m) in enumerate(months(),1):
            r=one(y,m); rows.append(r)
            write_progress(a.csv,a.evidence,rows,'IN_PROGRESS')
            print(f'[{i:03d}/{total}] {r["reference_month"]} HICP_FLASH={r["headline_hicp_yoy_pct"]} release={r["release_date"]}',flush=True)
    except Exception as exc:
        write_progress(a.csv,a.evidence,rows,'FAIL',f'{type(exc).__name__}: {exc}')
        raise
    assert len(rows)==105 and rows[0]['reference_month']=='2018-01' and rows[-1]['reference_month']=='2026-09'
    assert len({r['page_sha256'] for r in rows})==105
    by={r['reference_month']:r for r in rows}
    anchors={'2018-01':(1.3,'2018-01-31'),'2020-01':(1.4,'2020-01-31'),'2026-08':(3.3,'2026-09-01'),'2026-09':(3.8,'2026-10-02')}
    for k,(v,d) in anchors.items(): assert abs(by[k]['headline_hicp_yoy_pct']-v)<1e-12 and by[k]['release_date']==d,(k,by[k])
    write_progress(a.csv,a.evidence,rows,'PASS')
    ev=json.loads(Path(a.evidence).read_text(encoding='utf-8'))
    ev['anchor_checks']={k:{'rate':v,'release_date':d} for k,(v,d) in anchors.items()}
    Path(a.evidence).write_text(json.dumps(ev,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(ev,indent=2)); return 0

if __name__=='__main__': raise SystemExit(main())
