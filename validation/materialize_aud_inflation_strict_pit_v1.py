#!/usr/bin/env python3
import argparse,csv,hashlib,json,re,sys,time
from pathlib import Path
from datetime import datetime,timezone
from urllib.error import HTTPError,URLError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from validation.sources.aud_abs_core import fetch_bytes,text_from_html,parse_table17_quarterly_yoy

MON={3:('mar','Mar','March'),6:('jun','Jun','June'),9:('sep','Sep','September'),12:('dec','Dec','December')}
START=(2018,3);END=(2026,6)
ROW_KEYS=['reference_quarter','cpi_yoy','release_date','release_time','timezone','source_url','source_sha256','route','pit_status']
SEMANTIC_KEYS=['reference_quarter','cpi_yoy','release_date','release_time','timezone','pit_status']

def quarters():
    y,m=START
    while (y,m)<=END:
        yield y,m;m+=3
        if m>12:y+=1;m=3

def modern_url(y,m):return f'https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/{MON[m][0]}-{y}'
def legacy_urls(y,m):
    token=MON[m][1]
    return [
      f'https://www.abs.gov.au/ausstats/abs%40.nsf/lookup/6401.0Media%20Release1{token}%20{y}',
      f'https://www.abs.gov.au/AUSSTATS/Abs%40.Nsf/Lookup/6401.0Main%2BFeatures1{token}%20{y}',
      f'https://www.abs.gov.au/ausstats/abs%40.nsf/Lookup/6401.0Main%20Features1{token}%20{y}',
    ]

def stamp(text):
    x=re.search(r'Release date and time\s+(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d{2}\s*(?:am|pm))\s*([A-Z]{3,5})',text,flags=re.I)
    if x:return x.group(1),re.sub(r'\s+','',x.group(2)).lower(),x.group(3).upper()
    x=re.search(r'Released at\s+(\d{1,2}:\d{2})\s*(AM|PM)\s*\(CANBERRA TIME\)\s*(\d{1,2}/\d{1,2}/\d{4})',text,flags=re.I)
    if x:return x.group(3),x.group(1)+x.group(2).lower(),'CANBERRA_TIME'
    x=re.search(r'(\d{1,2}\s+[A-Z][a-z]+\s+\d{4}).{0,220}?(?:Embargoed?:|Embargo:)\s*(\d{1,2}[\.:]\d{2})\s*(am|pm)\s*\(Canberra time\)',text,flags=re.I|re.S)
    if x:return x.group(1),x.group(2).replace('.',':')+x.group(3).lower(),'CANBERRA_TIME'
    raise ValueError('explicit ABS release timestamp not found')

def reported_yoy(text,y,m):
    full=MON[m][2]
    unit=r'(?:%|per cent)(?:\s+per cent)?'
    pats=[
      rf'Over the twelve months to the {full} {y} quarter[,]? the CPI\s+(rose|fell)\s+([0-9]+(?:\.[0-9]+)?)\s*{unit}',
      rf'(?:The\s+)?CPI\s+(rose|fell)\s+([0-9]+(?:\.[0-9]+)?)\s*{unit}\s+(?:through the year|over the twelve months)\s+to the {full} {y} quarter',
      rf'Annual inflation\s+(rose|fell)\s+([0-9]+(?:\.[0-9]+)?)\s*{unit}\s+in the {full} {y} quarter',
      rf'All groups CPI[^.\n]{{0,200}}?\s+(rose|fell)\s+([0-9]+(?:\.[0-9]+)?)\s*{unit}\s+for the year',
      rf'Annually[,]?\s+the CPI\s+(rose|fell)\s+([0-9]+(?:\.[0-9]+)?)\s*{unit}',
    ]
    for p in pats:
        x=re.search(p,text,flags=re.I|re.S)
        if x:
            v=float(x.group(2));return -v if x.group(1).lower()=='fell' else v
    raise ValueError(f'explicit headline CPI YoY not found for {y}-{m:02d}')

def legacy_2018_table_yoy(text):
    for p in [
      r'All groups CPI\s+(-?[0-9]+(?:\.[0-9]+)?)\s+(-?[0-9]+(?:\.[0-9]+)?)',
      r'All Groups CPI\s+(-?[0-9]+(?:\.[0-9]+)?)\s+(-?[0-9]+(?:\.[0-9]+)?)',
    ]:
        x=re.search(p,text,flags=re.I|re.S)
        if x:return float(x.group(2))
    raise ValueError('2018 archived annual CPI table value not found')

def digest(rows,keys):
    canon=[{k:r[k] for k in keys} for r in rows]
    return hashlib.sha256(json.dumps(canon,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def one(y,m):
    ref=f'{y:04d}-{m:02d}';rel=modern_url(y,m)
    try:
        page_raw=fetch_bytes(rel);page=text_from_html(page_raw.decode('utf-8',errors='replace'))
        if 'Consumer Price Index' not in page:raise ValueError('modern CPI identity missing')
        rd,rt,tz=stamp(page)
        if y<=2020:
            value=reported_yoy(page,y,m)
            return {'reference_quarter':ref,'cpi_yoy':value,'release_date':rd,'release_time':rt,'timezone':tz,'source_url':rel,'source_sha256':hashlib.sha256(page_raw).hexdigest(),'route':'MODERN_REPORTED_YOY','pit_status':'STRICT_FIRST_RELEASE'}
        table=rel+'/6401017.xlsx';wb=fetch_bytes(table)
        date,value,_=parse_table17_quarterly_yoy(wb,y,m)
        if date!=ref:raise ValueError('modern quarter identity mismatch')
        return {'reference_quarter':ref,'cpi_yoy':value,'release_date':rd,'release_time':rt,'timezone':tz,'source_url':table,'source_sha256':hashlib.sha256(wb).hexdigest(),'route':'MODERN_TABLE17','pit_status':'STRICT_FIRST_RELEASE'}
    except (HTTPError,URLError,TimeoutError,ValueError):
        pass
    for url in legacy_urls(y,m):
        try:raw=fetch_bytes(url)
        except (HTTPError,URLError,TimeoutError):continue
        text=text_from_html(raw.decode('utf-8',errors='replace'))
        if 'Consumer Price Index' not in text:continue
        try:
            rd,rt,tz=stamp(text)
            value=legacy_2018_table_yoy(text) if y==2018 else reported_yoy(text,y,m)
        except ValueError:continue
        route='LEGACY_2018_TABLE_YOY' if y==2018 else 'LEGACY_REPORTED_YOY'
        return {'reference_quarter':ref,'cpi_yoy':value,'release_date':rd,'release_time':rt,'timezone':tz,'source_url':url,'source_sha256':hashlib.sha256(raw).hexdigest(),'route':route,'pit_status':'STRICT_FIRST_RELEASE'}
    raise ValueError(f'no strict ABS CPI source for {ref}')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--csv',required=True);ap.add_argument('--evidence',required=True);a=ap.parse_args()
    rows=[]
    for i,(y,m) in enumerate(quarters(),1):
        r=one(y,m);rows.append(r);print(f'[{i:02d}/34] {r["reference_quarter"]} {r["cpi_yoy"]} {r["route"]}',flush=True);time.sleep(.03)
    assert len(rows)==34 and rows[0]['reference_quarter']=='2018-03' and rows[-1]['reference_quarter']=='2026-06'
    assert len({r['source_sha256'] for r in rows})==34
    with open(a.csv,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=ROW_KEYS,lineterminator='\n');w.writeheader();w.writerows(rows)
    rc={}
    for r in rows:rc[r['route']]=rc.get(r['route'],0)+1
    ev={'schema':'GMFQ_AUD_INFLATION_STRICT_PIT_EVIDENCE_V1_RUNTIME','status':'PASS','target':'AUD.inflation','evidence_class':'STRICT_DIRECT_ARCHIVAL_PIT','authority':'Australian Bureau of Statistics','coverage':{'start':'2018-03','end':'2026-06','expected_quarters':34,'materialized_quarters':34},'series_contract':{'series_id':'AU_CPI_HEADLINE_Q_YOY','frequency':'Q','transformation':'reported_yoy_rate','modern_2021_plus_derivation':'ABS period-specific Table 17 Australia index t/t-4','2019_2020_derivation':'ABS period-specific archived release reported headline YoY','2018_derivation':'ABS archived 6401.0 table annual change column'},'route_counts':rc,'unique_source_hashes':34,'semantic_rowset_sha256':digest(rows,SEMANTIC_KEYS),'strict_rules':{'official_publisher_only':True,'period_specific_release_artifact_required':True,'publication_timestamp_required':True,'current_revised_history_forbidden':True,'revised_history_fallback_used':False},'generated_at_utc':datetime.now(timezone.utc).isoformat()}
    Path(a.evidence).write_text(json.dumps(ev,indent=2)+'\n',encoding='utf-8');print(json.dumps(ev,indent=2))
if __name__=='__main__':main()
