#!/usr/bin/env python3
# Full read-only archival discovery: 104 monthly AUD labour first-release candidates.
import hashlib, html, json, re, time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

UA="Mozilla/5.0 (compatible; global-macro-fx-quant/1.0)"
MON3=['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']
MONFULL=['January','February','March','April','May','June','July','August','September','October','November','December']
START=(2018,1); END=(2026,8)

def months():
    y,m=START
    while (y,m)<=END:
        yield y,m
        m+=1
        if m==13:y+=1;m=1

def get(url):
    req=Request(url,headers={'User-Agent':UA,'Accept-Language':'en-AU,en;q=0.9'})
    with urlopen(req,timeout=40) as r:return r.read(),r.headers.get('Content-Type',''),r.geturl()

def textify(raw):
    s=raw.decode('utf-8',errors='replace');s=re.sub(r'<script\b.*?</script>',' ',s,flags=re.I|re.S);s=re.sub(r'<style\b.*?</style>',' ',s,flags=re.I|re.S);s=html.unescape(re.sub(r'<[^>]+>',' ',s));return re.sub(r'\s+',' ',s).strip()

def valid_identity(text,y,m):
    if 'Labour Force' not in text:return False
    return re.search(rf'\b(?:{MON3[m-1]}|{MONFULL[m-1]})\s+{y}\b',text,flags=re.I) is not None

def stamp(text):
    x=re.search(r'Release date and time\s+(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d{2}\s*(?:am|pm))\s*([A-Z]{3,5})',text,flags=re.I)
    if x:return x.group(1),re.sub(r'\s+','',x.group(2)).lower(),x.group(3).upper(),'modern_explicit'
    x=re.search(r'Released at\s+(\d{1,2}:\d{2})\s*(AM|PM)\s*\(CANBERRA TIME\)\s*(\d{1,2}/\d{1,2}/\d{4})',text,flags=re.I)
    if x:return x.group(3),x.group(1)+x.group(2).lower(),'CANBERRA_TIME','legacy_explicit'
    x=re.search(r'(\d{1,2}\s+[A-Z][a-z]+\s+\d{4}).{0,200}?Embargo:\s*(\d{1,2}:\d{2})\s*(am|pm)\s*\(Canberra Time\)',text,flags=re.I|re.S)
    if x:return x.group(1),x.group(2)+x.group(3).lower(),'CANBERRA_TIME','legacy_embargo'
    return None

def sa_rate(text,y,m):
    full=MONFULL[m-1]
    pats=[
      r'seasonally adjusted unemployment rate.{0,260}?\b(?:to|at|was|of)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:%|per cent)',
      rf'In seasonally adjusted terms, in {full} {y}.{{0,1000}}?unemployment rate.{{0,180}}?\b(?:to|at|was)?\s*([0-9]+(?:\.[0-9]+)?)\s*%',
      rf'seasonally adjusted estimates for {full} {y}.{{0,1200}}?unemployment rate.{{0,180}}?\b(?:to|at|was)?\s*([0-9]+(?:\.[0-9]+)?)\s*%',
    ]
    for p in pats:
        q=re.search(p,text,flags=re.I|re.S)
        if q:return float(q.group(1))
    markers=[f'In seasonally adjusted terms, in {full} {y}',f'Seasonally adjusted estimates for {full} {y}','SEASONALLY ADJUSTED ESTIMATES','Key statistics - Seasonally adjusted','Seasonally Adjusted']
    for marker in markers:
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
    mon=MON3[m-1]; full=MONFULL[m-1]
    out=[('MODERN_RELEASE',f'https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia/{mon}-{y}')]
    # Legacy AUSSTATS accepted both abbreviated and full English month tokens depending on vintage.
    for token in (full,full[:3].title(),mon):
        out.append(('AUSSTATS_MEDIA',f'https://www.abs.gov.au/ausstats/abs%40.nsf/lookup/6202.0Media%20Release1{token}%20{y}'))
    for n in range(1,12):
        for token in (full,full[:3].title(),mon):
            out.append(('AUSSTATS_MAIN',f'https://www.abs.gov.au/ausstats/abs%40.nsf/Lookup/6202.0Main%20Features{n}{token}%20{y}'))
            out.append(('AUSSTATS_MAIN_PLUS',f'https://www.abs.gov.au/AUSSTATS/abs%40.nsf/Lookup/6202.0Main%2BFeatures{n}{token}%20{y}'))
    seen=set(); z=[]
    for a in out:
        if a[1] not in seen:seen.add(a[1]);z.append(a)
    return z

def one(y,m):
    ref=f'{y:04d}-{m:02d}'; tried=[]
    for era,url in candidates(y,m):
        try:
            raw,ct,final=get(url)
        except (HTTPError,URLError,TimeoutError,ValueError) as e:
            tried.append({'url':url,'error':type(e).__name__});continue
        text=textify(raw)
        if not valid_identity(text,y,m):
            tried.append({'url':url,'error':'IDENTITY'});continue
        rate=sa_rate(text,y,m); ts=stamp(text)
        if rate is None:
            tried.append({'url':url,'error':'NO_SA_RATE'});continue
        if ts is None:
            tried.append({'url':url,'error':'NO_TIMESTAMP'});continue
        rd,rt,tz,tsrc=ts
        return {'reference_month':ref,'era':era,'source_url':url,'final_url':final,'content_type':ct,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'unemployment_rate_sa':rate,'release_date':rd,'release_time':rt,'timezone':tz,'timestamp_source':tsrc,'pit_status':'STRICT_FIRST_RELEASE'}
    return {'reference_month':ref,'error':'NO_STRICT_SOURCE','tried':tried}

def main():
    rows=[]
    for i,(y,m) in enumerate(months(),1):
        r=one(y,m);rows.append(r);print(f"[{i:03d}/104] {r['reference_month']} {'OK '+str(r.get('unemployment_rate_sa')) if 'error' not in r else 'FAIL'}",flush=True)
        time.sleep(0.03)
    failures=[r for r in rows if 'error' in r]
    hashes=[r['sha256'] for r in rows if 'sha256' in r]
    out={'schema':'GMFQ_AUD_LABOUR_FULL_ARCHIVE_PROBE_V1','checked_at_utc':datetime.now(timezone.utc).isoformat(),'authority':'Australian Bureau of Statistics','route_class':'OFFICIAL_DIRECT_PERIOD_SPECIFIC_ARCHIVE','expected_months':104,'resolved_months':104-len(failures),'failure_count':len(failures),'unique_source_hashes':len(set(hashes)),'era_counts':{},'failures':failures,'rows':rows,'status':'PASS' if not failures else 'FAIL'}
    for r in rows:
        if 'era' in r:out['era_counts'][r['era']]=out['era_counts'].get(r['era'],0)+1
    open('/tmp/aud-labour-full-archive-probe.json','w').write(json.dumps(out,indent=2))
    print(json.dumps({k:out[k] for k in ['expected_months','resolved_months','failure_count','unique_source_hashes','era_counts','status']},indent=2))
    if failures:raise SystemExit(1)
if __name__=='__main__':main()
