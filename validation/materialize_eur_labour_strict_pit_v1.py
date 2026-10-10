#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,html,json,re,time,urllib.error,urllib.request
from datetime import date,datetime,timedelta,timezone
from html.parser import HTMLParser
from pathlib import Path

START=(2018,1); END=(2026,8)
MONTHS=['january','february','march','april','may','june','july','august','september','october','november','december']
ROW_KEYS=['reference_month','unemployment_rate_pct','release_date','release_geo_vintage','source_url','page_sha256','source_route','pit_status']
SEMANTIC_KEYS=['reference_month','unemployment_rate_pct','release_date','release_geo_vintage','source_route','pit_status']
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

def last_weekday_of_next_month(y:int,m:int)->date:
    ny,nm=(y+1,1) if m==12 else (y,m+1)
    nxt=date(ny+1,1,1) if nm==12 else date(ny,nm+1,1)
    d=nxt-timedelta(days=1)
    while d.weekday()>=5:d-=timedelta(days=1)
    return d

def candidate_dates(y:int,m:int):
    anchor=last_weekday_of_next_month(y,m); ordered=[anchor]; d=anchor
    while len(ordered)<8:
        d+=timedelta(days=1)
        if d.weekday()<5:ordered.append(d)
    d=anchor
    while len(ordered)<12:
        d-=timedelta(days=1)
        if d.weekday()<5:ordered.append(d)
    yield from ordered

def urls_for(d:date):
    key=d.strftime('%d%m%Y'); legacy=[]; modern=[]
    for suffix in ('AP','BP'):
        legacy.append((f'EUROSTAT_UNEMPLOYMENT_LEGACY_{suffix}',f'https://ec.europa.eu/eurostat/web/products-euro-indicators/-/3-{key}-{suffix}'))
        modern.append((f'EUROSTAT_UNEMPLOYMENT_WEB_{suffix}',f'https://ec.europa.eu/eurostat/web/products-euro-indicators/w/3-{key}-{suffix.lower()}'))
    return legacy+modern if d.year<=2024 else modern+legacy

def throttle():
    global _LAST_REQUEST_AT
    now=time.monotonic(); wait=MIN_REQUEST_INTERVAL_SECONDS-(now-_LAST_REQUEST_AT)
    if wait>0: time.sleep(wait)
    _LAST_REQUEST_AT=time.monotonic()

def fetch(url:str):
    req=urllib.request.Request(url,headers={'User-Agent':'global-macro-fx-quant/1.0 strict-pit'})
    for attempt in range(8):
        throttle()
        try:
            with urllib.request.urlopen(req,timeout=30) as r:return r.read(),r.geturl()
        except urllib.error.HTTPError as e:
            if e.code in (404,410): return None
            if e.code==429 and attempt<7:
                retry=e.headers.get('Retry-After') if e.headers else None
                try: delay=max(15.0,float(retry)) if retry else min(120.0,15.0*(2**attempt))
                except (TypeError,ValueError): delay=min(120.0,15.0*(2**attempt))
                print(f'[transport] Eurostat 429; retry same URL in {delay:.0f}s attempt={attempt+1}/8',flush=True); time.sleep(delay); continue
            raise

def parse_period(text:str,y:int,m:int):
    month=MONTHS[m-1].capitalize(); period=f'{month} {y}'
    # Require the release to identify the target reference month.
    if re.search(rf'\b{re.escape(period)}\b',text,re.I) is None: return None
    pats=[
      rf'euro area\s*\((EA\d+)\)\s*seasonally[- ]adjusted unemployment rate was\s*([0-9]+(?:\.[0-9]+)?)\s*%\s*in\s*{re.escape(month)}\s*{y}',
      rf'euro area\s*\((EA\d+)\)\s*seasonally[- ]adjusted unemployment rate was\s*([0-9]+(?:\.[0-9]+)?)%\s*in\s*{re.escape(month)}\s*{y}',
      rf'In\s*{re.escape(month)}\s*{y},?\s*the euro area seasonally adjusted unemployment rate was\s*([0-9]+(?:\.[0-9]+)?)%'
    ]
    hits=[]
    for i,p in enumerate(pats):
        for x in re.finditer(p,text,re.I):
            if i<2: hits.append((x.group(1).upper(),float(x.group(2))))
            else: hits.append(('EA_CURRENT_RELEASE',float(x.group(1))))
    uniq=[]
    for g,v in hits:
        if (g,v) not in uniq: uniq.append((g,v))
    if not uniq:return None
    vals={v for _,v in uniq}
    if len(vals)!=1: raise ValueError(f'ambiguous unemployment headline for {period}: {uniq}')
    geos={g for g,_ in uniq}
    geo=next(iter(geos)) if len(geos)==1 else sorted(geos)[0]
    return geo,next(iter(vals))

def one(y:int,m:int):
    ref=f'{y:04d}-{m:02d}'; hits=[]
    for d in candidate_dates(y,m):
        for route,url in urls_for(d):
            got=fetch(url)
            if got is None:continue
            raw,final=got; parsed=parse_period(text_from_html(raw),y,m)
            if parsed is None:continue
            geo,value=parsed; hits.append((d.isoformat(),geo,value,final,hashlib.sha256(raw).hexdigest(),route)); break
        if hits:break
    if len(hits)!=1: raise ValueError(f'expected one official Eurostat unemployment first release for {ref}, got {hits}')
    rd,geo,value,url,sha,route=hits[0]
    return {'reference_month':ref,'unemployment_rate_pct':value,'release_date':rd,'release_geo_vintage':geo,'source_url':url,'page_sha256':sha,'source_route':route,'pit_status':'STRICT_FIRST_RELEASE'}

def digest(rows):
    canon=[{k:r[k] for k in SEMANTIC_KEYS} for r in rows]
    return hashlib.sha256(json.dumps(canon,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def write_progress(csv_path,evidence_path,rows,status,last_error=None):
    p=Path(csv_path); p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=ROW_KEYS,lineterminator='\n'); w.writeheader(); w.writerows(rows)
    ev={'schema':'GMFQ_EUR_LABOUR_STRICT_PIT_EVIDENCE_V1_RUNTIME','status':status,'target':'EUR.labour','evidence_class':'STRICT_DIRECT_ARCHIVAL_PIT','authority':'Eurostat','coverage':{'start':'2018-01','end':'2026-08','expected_months':104,'materialized_months':len(rows)},'series_contract':{'series_id':'EA_UNEMP','frequency':'M','transformation':'level','unit':'%','first_release_semantics':'MONTHLY_UNEMPLOYMENT_HEADLINE_AS_PUBLISHED','geography_semantics':'CONTEMPORANEOUS_EURO_AREA_COMPOSITION_AS_PUBLISHED'},'unique_page_hashes':len({r['page_sha256'] for r in rows}),'semantic_rowset_sha256':digest(rows),'semantic_fingerprint_fields':SEMANTIC_KEYS,'strict_rules':{'official_publisher_only':True,'period_specific_release_artifact_required':True,'publication_date_required':True,'url_and_sha256_required':True,'current_revised_history_forbidden':True,'revised_history_fallback_used':False},'last_materialized_month':rows[-1]['reference_month'] if rows else None,'last_error':last_error,'generated_at_utc':datetime.now(timezone.utc).isoformat()}
    Path(evidence_path).write_text(json.dumps(ev,indent=2)+'\n',encoding='utf-8')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--csv',required=True); ap.add_argument('--evidence',required=True); a=ap.parse_args(); rows=[]; total=104
    try:
        for i,(y,m) in enumerate(months(),1):
            r=one(y,m); rows.append(r); write_progress(a.csv,a.evidence,rows,'IN_PROGRESS'); print(f'[{i:03d}/{total}] {r["reference_month"]} UNEMP={r["unemployment_rate_pct"]} geo={r["release_geo_vintage"]} release={r["release_date"]}',flush=True)
    except Exception as exc:
        write_progress(a.csv,a.evidence,rows,'FAIL',f'{type(exc).__name__}: {exc}'); raise
    assert len(rows)==104 and rows[0]['reference_month']=='2018-01' and rows[-1]['reference_month']=='2026-08'
    by={r['reference_month']:r for r in rows}
    anchors={'2018-01':(8.6,'2018-03-01'),'2026-07':(6.4,'2026-09-01'),'2026-08':(6.4,'2026-10-01')}
    for k,(v,d) in anchors.items(): assert abs(by[k]['unemployment_rate_pct']-v)<1e-12 and by[k]['release_date']==d,(k,by[k])
    write_progress(a.csv,a.evidence,rows,'PASS')
    ev=json.loads(Path(a.evidence).read_text()); ev['anchor_checks']={k:{'rate':v,'release_date':d} for k,(v,d) in anchors.items()}; Path(a.evidence).write_text(json.dumps(ev,indent=2)+'\n')
    print(json.dumps(ev,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
