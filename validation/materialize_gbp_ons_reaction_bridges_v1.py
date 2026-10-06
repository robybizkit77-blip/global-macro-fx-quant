import csv, json, re, time, urllib.request
from html import unescape
from pathlib import Path

AWE_PREV='https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/timeseries/k54l/emp/previous'
SERV_PREV='https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7nn/mm23/previous'
AWE_BASE='https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/timeseries/k54l/emp/previous/'
SERV_BASE='https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7nn/mm23/previous/'
OUTDIR=Path('history/pit_v1')
AUDIT=Path('validation/GBP_ONS_REACTION_BRIDGES_MATERIALIZATION_2026-10-06.json')
START_YEAR=2018
UA={'User-Agent':'Mozilla/5.0 GMFQ-PIT-audit/1.0'}
MONTHS={'JAN':1,'FEB':2,'MAR':3,'APR':4,'MAY':5,'JUN':6,'JUL':7,'AUG':8,'SEP':9,'OCT':10,'NOV':11,'DEC':12}

def get(url,tries=5):
    delay=1.0
    for i in range(tries):
        try:
            req=urllib.request.Request(url,headers=UA)
            with urllib.request.urlopen(req,timeout=45) as r:return r.read().decode('utf-8','ignore')
        except Exception as e:
            if i==tries-1: raise
            time.sleep(delay); delay*=2

def version_ids(index_url):
    html=get(index_url)
    ids=[]
    for v in re.findall(r'/previous/(v\d+)',html,re.I):
        if v.lower() not in [x.lower() for x in ids]: ids.append(v)
    # pages list newest first; process chronologically
    return list(reversed(ids))

def stripped(html):
    x=re.sub(r'<script.*?</script>|<style.*?</style>',' ',html,flags=re.I|re.S)
    x=re.sub(r'<[^>]+>',' ',x)
    return re.sub(r'\s+',' ',unescape(x)).strip()

def release_date(text):
    # ONS page text: Release date: 10 September 2024
    m=re.search(r'Release date:\s*(\d{1,2}\s+[A-Za-z]+\s+20\d{2})',text,re.I)
    return m.group(1) if m else None

def monthly_pairs(text):
    # monthly table rows survive tag stripping as '2024 JAN 123.4'
    pat=r'(?<!\d)(20\d{2})\s+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+(-?\d+(?:\.\d+)?)'
    out=[]
    for y,m,v in re.findall(pat,text,re.I):out.append((f'{y}-{MONTHS[m.upper()]:02d}',float(v)))
    # dedupe while preserving latest page occurrence
    d={k:v for k,v in out}
    return sorted(d.items())

def one_series(index_url,base,kind):
    ids=version_ids(index_url); obs=[]; errors=[]
    for n,v in enumerate(ids):
        url=base+v
        try:
            html=get(url); text=stripped(html); rd=release_date(text)
            if not rd: raise ValueError('release date not found')
            year=int(re.search(r'20\d{2}',rd).group())
            if year<START_YEAR: continue
            pairs=monthly_pairs(text)
            if not pairs: raise ValueError('monthly table not found')
            ref,val=pairs[-1]
            if kind=='awe':
                d=dict(pairs); prev=f'{int(ref[:4])-1}{ref[4:]}'
                yoy=None if prev not in d else 100*(val/d[prev]-1)
                obs.append({'available_date':rd,'reference_month':ref,'index_value':val,'yoy_pct':yoy,'series_id':'K54L','source_url':url})
            else:
                obs.append({'available_date':rd,'reference_month':ref,'annual_rate_pct':val,'series_id':'D7NN','source_url':url})
        except Exception as e:errors.append({'version':v,'url':url,'error':str(e)[:180]})
        time.sleep(0.30)
    return obs,errors,len(ids)

def write_csv(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as f:
        if rows:
            w=csv.DictWriter(f,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)

def main():
    awe,aerr,an=one_series(AWE_PREV,AWE_BASE,'awe')
    serv,serr,sn=one_series(SERV_PREV,SERV_BASE,'services')
    write_csv(OUTDIR/'GBP_AWE_K54L_CERTIFIED_VINTAGES_2018_2026.csv',awe)
    write_csv(OUTDIR/'GBP_CPI_SERVICES_D7NN_CERTIFIED_VINTAGES_2018_2026.csv',serv)
    status='PASS' if len(awe)>=60 and len(serv)>=60 else 'PARTIAL'
    audit={'schema':'GMFQ_GBP_ONS_REACTION_BRIDGES_V1','status':status,'created_at':'2026-10-06','awe':{'series':'K54L','versions_seen':an,'materialized':len(awe),'errors':aerr[:20]},'services':{'series':'D7NN','versions_seen':sn,'materialized':len(serv),'errors':serr[:20]},'guardrails':['single-series ONS vintage pages only','official release dates from each vintage page','no current-series retrofill','fixed K54L wage definition predeclared','no engine/live_data changes']}
    AUDIT.write_text(json.dumps(audit,indent=2),encoding='utf-8');print(json.dumps(audit,indent=2))
    if status!='PASS': raise SystemExit(2)

if __name__=='__main__':main()
