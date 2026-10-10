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

def candidate_dates(y:int,m:int):
    # Eurostat flash estimate is issued at/around month-end. Search a deliberately
    # narrow official window only; fail closed if no unique period-specific release exists.
    if m==12: nxt=date(y+1,1,1)
    else: nxt=date(y,m+1,1)
    start=nxt-timedelta(days=7); end=nxt+timedelta(days=7)
    d=start
    while d<=end:
        if d.weekday()<5: yield d
        d+=timedelta(days=1)

def urls_for(d:date):
    key=d.strftime('%d%m%Y')
    return [
      ('EUROSTAT_EURO_INDICATORS_WEB',f'https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-{key}-ap'),
      ('EUROSTAT_EURO_INDICATORS_LEGACY',f'https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-{key}-AP'),
    ]

def fetch(url:str):
    req=urllib.request.Request(url,headers={'User-Agent':'global-macro-fx-quant/1.0 strict-pit'})
    try:
        with urllib.request.urlopen(req,timeout=25) as r:
            raw=r.read(); final=r.geturl(); return raw,final
    except urllib.error.HTTPError as e:
        if e.code in (404,410): return None
        raise

def parse_period(text:str,y:int,m:int):
    month=MONTHS[m-1].capitalize(); period=f'{month} {y}'
    if re.search(rf'Flash estimate\s*[-–]\s*{re.escape(period)}',text,re.I) is None:
        return None
    pats=[
      rf'Euro area annual inflation is expected to be\s+(-?[0-9]+(?:\.[0-9]+)?)\s*%\s+in\s+{re.escape(month)}',
      rf'Euro area annual inflation\s+is expected to be\s+(-?[0-9]+(?:\.[0-9]+)?)%\s+in\s+{re.escape(month)}',
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

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--csv',required=True); ap.add_argument('--evidence',required=True); a=ap.parse_args()
    rows=[]; total=105
    for i,(y,m) in enumerate(months(),1):
        r=one(y,m); rows.append(r); print(f'[{i:03d}/{total}] {r["reference_month"]} HICP_FLASH={r["headline_hicp_yoy_pct"]} release={r["release_date"]}',flush=True); time.sleep(.02)
    assert len(rows)==105 and rows[0]['reference_month']=='2018-01' and rows[-1]['reference_month']=='2026-09'
    assert len({r['page_sha256'] for r in rows})==105
    by={r['reference_month']:r for r in rows}
    anchors={'2018-01':(1.3,'2018-01-31'),'2020-01':(1.4,'2020-01-31'),'2026-08':(3.3,'2026-09-01'),'2026-09':(3.8,'2026-10-02')}
    for k,(v,d) in anchors.items(): assert abs(by[k]['headline_hicp_yoy_pct']-v)<1e-12 and by[k]['release_date']==d,(k,by[k])
    Path(a.csv).parent.mkdir(parents=True,exist_ok=True)
    with open(a.csv,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=ROW_KEYS,lineterminator='\n'); w.writeheader(); w.writerows(rows)
    ev={'schema':'GMFQ_EUR_INFLATION_STRICT_PIT_EVIDENCE_V1_RUNTIME','status':'PASS','target':'EUR.inflation','evidence_class':'STRICT_DIRECT_ARCHIVAL_PIT','authority':'Eurostat','coverage':{'start':'2018-01','end':'2026-09','expected_months':105,'materialized_months':105},'series_contract':{'series_id':'EA_HICP_HEADLINE_YOY','frequency':'M','transformation':'reported_yoy_rate','unit':'% YoY','first_release_semantics':'FLASH_ESTIMATE'},'unique_page_hashes':105,'semantic_rowset_sha256':digest(rows),'semantic_fingerprint_fields':SEMANTIC_KEYS,'strict_rules':{'official_publisher_only':True,'period_specific_release_artifact_required':True,'publication_date_required':True,'url_and_sha256_required':True,'current_revised_history_forbidden':True,'final_release_fallback_forbidden':True,'revised_history_fallback_used':False},'anchor_checks':{k:{'rate':v,'release_date':d} for k,(v,d) in anchors.items()},'generated_at_utc':datetime.now(timezone.utc).isoformat()}
    Path(a.evidence).write_text(json.dumps(ev,indent=2)+'\n',encoding='utf-8'); print(json.dumps(ev,indent=2)); return 0

if __name__=='__main__': raise SystemExit(main())
