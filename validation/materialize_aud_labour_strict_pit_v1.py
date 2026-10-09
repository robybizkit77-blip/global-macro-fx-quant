#!/usr/bin/env python3
import argparse,csv,hashlib,html,json,re,time
from datetime import datetime,timezone
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen

UA='Mozilla/5.0 (compatible; global-macro-fx-quant/1.0)'
MON3=['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']
MONFULL=['January','February','March','April','May','June','July','August','September','October','November','December']
START=(2018,1);END=(2026,8)
ROW_KEYS=['reference_month','unemployment_rate_sa','release_date','release_time','timezone','source_url','sha256','era','pit_status']
SEMANTIC_KEYS=['reference_month','unemployment_rate_sa','release_date','release_time','timezone','source_url','era','pit_status']

def months():
    y,m=START
    while (y,m)<=END:
        yield y,m;m+=1
        if m==13:y+=1;m=1

def get(url):
    req=Request(url,headers={'User-Agent':UA,'Accept-Language':'en-AU,en;q=0.9'})
    with urlopen(req,timeout=40) as r:return r.read(),r.headers.get('Content-Type',''),r.geturl()

def textify(raw):
    s=raw.decode('utf-8',errors='replace');s=re.sub(r'<script\b.*?</script>',' ',s,flags=re.I|re.S);s=re.sub(r'<style\b.*?</style>',' ',s,flags=re.I|re.S);s=html.unescape(re.sub(r'<[^>]+>',' ',s));return re.sub(r'\s+',' ',s).strip()

def valid_identity(text,y,m):
    return 'Labour Force' in text and re.search(rf'\b(?:{MON3[m-1]}|{MONFULL[m-1]})\s+{y}\b',text,flags=re.I) is not None

def stamp(text):
    x=re.search(r'Release date and time\s+(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d{2}\s*(?:am|pm))\s*([A-Z]{3,5})',text,flags=re.I)
    if x:return x.group(1),re.sub(r'\s+','',x.group(2)).lower(),x.group(3).upper()
    x=re.search(r'Released at\s+(\d{1,2}:\d{2})\s*(AM|PM)\s*\(CANBERRA TIME\)\s*(\d{1,2}/\d{1,2}/\d{4})',text,flags=re.I)
    if x:return x.group(3),x.group(1)+x.group(2).lower(),'CANBERRA_TIME'
    x=re.search(r'(\d{1,2}\s+[A-Z][a-z]+\s+\d{4}).{0,200}?Embargo:\s*(\d{1,2}:\d{2})\s*(am|pm)\s*\(Canberra Time\)',text,flags=re.I|re.S)
    if x:return x.group(1),x.group(2)+x.group(3).lower(),'CANBERRA_TIME'
    return None

def sa_rate(text,y,m):
    full=MONFULL[m-1]
    for p in [
      r'seasonally adjusted unemployment rate.{0,260}?\b(?:to|at|was|of)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:%|per cent)',
      rf'In seasonally adjusted terms, in {full} {y}.{{0,1000}}?unemployment rate.{{0,180}}?\b(?:to|at|was)?\s*([0-9]+(?:\.[0-9]+)?)\s*%',
      rf'seasonally adjusted estimates for {full} {y}.{{0,1200}}?unemployment rate.{{0,180}}?\b(?:to|at|was)?\s*([0-9]+(?:\.[0-9]+)?)\s*%',
    ]:
        q=re.search(p,text,flags=re.I|re.S)
        if q:return float(q.group(1))
    for marker in [f'In seasonally adjusted terms, in {full} {y}',f'Seasonally adjusted estimates for {full} {y}','SEASONALLY ADJUSTED ESTIMATES','Key statistics - Seasonally adjusted','Seasonally Adjusted']:
        pos=text.lower().find(marker.lower())
        if pos<0:continue
        win=text[pos:pos+4200]
        for p in [
          r'unemployment rate.{0,220}?\b(?:remained steady at|remained at|was steady at|was unchanged at|increased to|decreased to|rose to|fell to|to|at|was)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:%|per cent)',
          r'Unemployment rate\s*\(%\).{0,300}?([0-9]+(?:\.[0-9]+)?)\s+([0-9]+(?:\.[0-9]+)?)',
          r'Unemployment rate.{0,180}?([0-9]+(?:\.[0-9]+)?)\s*%',
        ]:
            q=re.search(p,win,flags=re.I|re.S)
            if q:return float(q.group(2) if q.lastindex and q.lastindex>=2 else q.group(1))
    return None

def candidates(y,m):
    mon=MON3[m-1];full=MONFULL[m-1]
    out=[('MODERN_RELEASE',f'https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia/{mon}-{y}')]
    for token in (full,full[:3].title(),mon):out.append(('AUSSTATS_MEDIA',f'https://www.abs.gov.au/ausstats/abs%40.nsf/lookup/6202.0Media%20Release1{token}%20{y}'))
    for n in range(1,12):
        for token in (full,full[:3].title(),mon):
            out.append(('AUSSTATS_MAIN',f'https://www.abs.gov.au/ausstats/abs%40.nsf/Lookup/6202.0Main%20Features{n}{token}%20{y}'))
            out.append(('AUSSTATS_MAIN_PLUS',f'https://www.abs.gov.au/AUSSTATS/abs%40.nsf/Lookup/6202.0Main%2BFeatures{n}{token}%20{y}'))
    seen=set();z=[]
    for a in out:
        if a[1] not in seen:seen.add(a[1]);z.append(a)
    return z

def one(y,m):
    ref=f'{y:04d}-{m:02d}'
    for era,url in candidates(y,m):
        try:raw,ct,final=get(url)
        except (HTTPError,URLError,TimeoutError,ValueError):continue
        text=textify(raw)
        if not valid_identity(text,y,m):continue
        rate=sa_rate(text,y,m);ts=stamp(text)
        if rate is None or ts is None:continue
        rd,rt,tz=ts
        return {'reference_month':ref,'unemployment_rate_sa':rate,'release_date':rd,'release_time':rt,'timezone':tz,'source_url':url,'sha256':hashlib.sha256(raw).hexdigest(),'era':era,'pit_status':'STRICT_FIRST_RELEASE','content_type':ct,'bytes':len(raw),'final_url':final}
    raise ValueError(f'no strict period-specific ABS source for {ref}')

def digest(rows,keys):
    canon=[{k:r[k] for k in keys} for r in rows]
    blob=json.dumps(canon,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    return hashlib.sha256(blob).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--csv',required=True);ap.add_argument('--evidence',required=True);args=ap.parse_args()
    rows=[]
    for i,(y,m) in enumerate(months(),1):
        r=one(y,m);rows.append(r);print(f'[{i:03d}/104] {r["reference_month"]} {r["unemployment_rate_sa"]}',flush=True);time.sleep(.03)
    hashes=[r['sha256'] for r in rows]
    assert len(rows)==104 and rows[0]['reference_month']=='2018-01' and rows[-1]['reference_month']=='2026-08'
    assert len(set(hashes))==104 and all(r['pit_status']=='STRICT_FIRST_RELEASE' for r in rows)
    with open(args.csv,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=ROW_KEYS,lineterminator='\n');w.writeheader();w.writerows({k:r[k] for k in ROW_KEYS} for r in rows)
    era_counts={}
    for r in rows:era_counts[r['era']]=era_counts.get(r['era'],0)+1
    evidence={'schema':'GMFQ_AUD_LABOUR_STRICT_PIT_EVIDENCE_V1_RUNTIME','status':'PASS','target':'AUD.labour','evidence_class':'STRICT_DIRECT_ARCHIVAL_PIT','authority':'Australian Bureau of Statistics','coverage':{'start':'2018-01','end':'2026-08','expected_months':104,'materialized_months':104},'series_contract':{'series_id':'AU_UNEMP_RATE','frequency':'M','transformation':'level','seasonal_adjustment':'seasonally adjusted'},'route_counts':era_counts,'unique_source_hashes':len(set(hashes)),'semantic_rowset_sha256':digest(rows,SEMANTIC_KEYS),'raw_fetch_rowset_sha256':digest(rows,ROW_KEYS),'strict_rules':{'official_publisher_only':True,'period_specific_release_artifact_required':True,'publication_timestamp_required':True,'sha256_required':True,'raw_page_hash_is_fetch_evidence_not_stable_identity':True,'current_revised_history_forbidden':True,'revised_history_fallback_used':False},'generated_at_utc':datetime.now(timezone.utc).isoformat()}
    with open(args.evidence,'w',encoding='utf-8') as f:json.dump(evidence,f,indent=2);f.write('\n')
    print(json.dumps({k:evidence[k] for k in ['status','coverage','route_counts','unique_source_hashes','semantic_rowset_sha256','raw_fetch_rowset_sha256']},indent=2))
if __name__=='__main__':main()
