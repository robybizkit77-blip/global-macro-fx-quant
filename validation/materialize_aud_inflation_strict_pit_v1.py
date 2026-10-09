#!/usr/bin/env python3
import argparse,csv,hashlib,json,re,sys,time
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from validation.sources.aud_abs_core import fetch_bytes,text_from_html,parse_table17_quarterly_yoy

MONTHS={3:'mar',6:'jun',9:'sep',12:'dec'}
START=(2018,3);END=(2026,6)
ROW_KEYS=['reference_quarter','cpi_yoy','release_date','release_time','timezone','release_url','table17_url','table17_sha256','pit_status']
SEMANTIC_KEYS=['reference_quarter','cpi_yoy','release_date','release_time','timezone','pit_status']

def quarters():
    y,m=START
    while (y,m)<=END:
        yield y,m
        m+=3
        if m>12:y+=1;m=3

def release_url(y,m):
    return f'https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/{MONTHS[m]}-{y}'

def stamp(text):
    patterns=[
      r'Release date and time\s+(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d{2}\s*(?:am|pm))\s*([A-Z]{3,5})',
      r'Released\s+(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d{2}\s*(?:am|pm))\s*\(?([A-Z]{3,5}|Canberra Time)\)?',
      r'Released at\s+(\d{1,2}:\d{2})\s*(AM|PM)\s*\(CANBERRA TIME\)\s*(\d{1,2}/\d{1,2}/\d{4})',
      r'(\d{1,2}\s+[A-Z][a-z]+\s+\d{4}).{0,200}?Embargo:\s*(\d{1,2}:\d{2})\s*(am|pm)\s*\(Canberra Time\)',
    ]
    x=re.search(patterns[0],text,flags=re.I)
    if x:return x.group(1),re.sub(r'\s+','',x.group(2)).lower(),x.group(3).upper()
    x=re.search(patterns[1],text,flags=re.I)
    if x:return x.group(1),re.sub(r'\s+','',x.group(2)).lower(),x.group(3).upper().replace(' ','_')
    x=re.search(patterns[2],text,flags=re.I)
    if x:return x.group(3),x.group(1)+x.group(2).lower(),'CANBERRA_TIME'
    x=re.search(patterns[3],text,flags=re.I|re.S)
    if x:return x.group(1),x.group(2)+x.group(3).lower(),'CANBERRA_TIME'
    raise ValueError('explicit ABS release timestamp not found')

def digest(rows,keys):
    canon=[{k:r[k] for k in keys} for r in rows]
    return hashlib.sha256(json.dumps(canon,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def one(y,m):
    rel=release_url(y,m);table=rel+'/6401017.xlsx'
    page=text_from_html(fetch_bytes(rel).decode('utf-8',errors='replace'))
    if 'Consumer Price Index' not in page:raise ValueError(f'CPI identity not established {y}-{m:02d}')
    rd,rt,tz=stamp(page)
    wb=fetch_bytes(table)
    date,value,audit=parse_table17_quarterly_yoy(wb,y,m)
    if date!=f'{y:04d}-{m:02d}':raise ValueError('quarter identity mismatch')
    return {'reference_quarter':date,'cpi_yoy':value,'release_date':rd,'release_time':rt,'timezone':tz,'release_url':rel,'table17_url':table,'table17_sha256':hashlib.sha256(wb).hexdigest(),'pit_status':'STRICT_FIRST_RELEASE','audit':audit}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--csv',required=True);ap.add_argument('--evidence',required=True);a=ap.parse_args()
    rows=[]
    for i,(y,m) in enumerate(quarters(),1):
        r=one(y,m);rows.append(r);print(f'[{i:02d}/34] {r["reference_quarter"]} {r["cpi_yoy"]}',flush=True);time.sleep(.03)
    assert len(rows)==34 and rows[0]['reference_quarter']=='2018-03' and rows[-1]['reference_quarter']=='2026-06'
    assert len({r['table17_sha256'] for r in rows})==34
    with open(a.csv,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=ROW_KEYS,lineterminator='\n');w.writeheader();w.writerows({k:r[k] for k in ROW_KEYS} for r in rows)
    ev={'schema':'GMFQ_AUD_INFLATION_STRICT_PIT_EVIDENCE_V1_RUNTIME','status':'PASS','target':'AUD.inflation','evidence_class':'STRICT_DIRECT_ARCHIVAL_PIT','authority':'Australian Bureau of Statistics','coverage':{'start':'2018-03','end':'2026-06','expected_quarters':34,'materialized_quarters':34},'series_contract':{'series_id':'AU_CPI_HEADLINE_Q_YOY','frequency':'Q','transformation':'reported_yoy_rate','derivation':'ABS Table 17 Australia index t/t-4'},'unique_table17_hashes':34,'semantic_rowset_sha256':digest(rows,SEMANTIC_KEYS),'strict_rules':{'official_publisher_only':True,'period_specific_release_page_required':True,'period_specific_table17_required':True,'publication_timestamp_required':True,'current_revised_history_forbidden':True,'revised_history_fallback_used':False},'generated_at_utc':datetime.now(timezone.utc).isoformat()}
    Path(a.evidence).write_text(json.dumps(ev,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(ev,indent=2))
if __name__=='__main__':main()
