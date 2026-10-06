import csv, io, json, re, urllib.request
from html import unescape
from pathlib import Path

AWE_PAGE = 'https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/earningsandworkinghours/datasets/averageweeklyearnings/current'
SERV_PAGE = 'https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7nn/mm23'
OUTDIR = Path('history/pit_v1')
AUDIT = Path('validation/GBP_ONS_REACTION_BRIDGES_MATERIALIZATION_2026-10-06.json')
AWE_ID = 'K54L'  # Whole Economy SA regular pay excluding arrears
SERV_ID = 'D7NN' # CPI annual rate: Services
START_YEAR = 2018
UA = {'User-Agent':'Mozilla/5.0 GMFQ-PIT-audit/1.0'}

def get(url):
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=45) as r:
        return r.read()

def abs_ons(href):
    href=unescape(href)
    if href.startswith('http'): return href
    return 'https://www.ons.gov.uk'+href

def previous_csv_links(page_bytes, filename_hint=None):
    html=page_bytes.decode('utf-8','ignore')
    # Capture href plus nearby row text so the official superseded timestamp remains the PIT availability anchor.
    rows=re.findall(r'<tr[^>]*>(.*?)</tr>',html,flags=re.I|re.S)
    out=[]
    for row in rows:
        hrefs=re.findall(r'href=["\']([^"\']+\.csv[^"\']*)["\']',row,flags=re.I)
        if not hrefs: continue
        text=re.sub(r'<[^>]+>',' ',row)
        text=re.sub(r'\s+',' ',unescape(text)).strip()
        m=re.search(r'(\d{1,2}\s+[A-Za-z]+\s+20\d{2})(?:\s+(\d{2}:\d{2}))?',text)
        if not m: continue
        dt=m.group(1)+((' '+m.group(2)) if m.group(2) else '')
        href=hrefs[0]
        if '/previous/' not in href: continue
        if filename_hint and filename_hint.lower() not in href.lower(): continue
        year=int(re.search(r'20\d{2}',dt).group())
        if year < START_YEAR: continue
        out.append((dt,abs_ons(href)))
    # Oldest to newest; duplicate corrections remain separate vintages.
    return list(reversed(out))

def parse_ons_csv_for_series(blob, series_id):
    text=blob.decode('utf-8-sig','ignore')
    rows=list(csv.reader(io.StringIO(text)))
    target=None
    for r in rows:
        if any(c.strip().upper()==series_id.upper() for c in r):
            target=r; break
    if target is None:
        raise ValueError(f'{series_id} not found')
    # EMP/MM23 bulk CSVs are wide. Find a header row with period labels matching target width.
    header=None
    for r in rows[:80]:
        if len(r)==len(target) and sum(bool(re.match(r'^(?:20\d{2}\s+)?(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|Q[1-4]|20\d{2})',c.strip().upper())) for c in r)>=8:
            header=r
    if header is None:
        # Fallback: bulk format often has metadata columns followed by time columns; use row immediately preceding target if aligned.
        idx=rows.index(target)
        for r in reversed(rows[:idx]):
            if len(r)==len(target):
                header=r; break
    if header is None: raise ValueError('aligned header not found')
    pairs=[]
    for h,v in zip(header,target):
        h=h.strip(); v=v.strip()
        if not h or not v: continue
        try: x=float(v.replace(',',''))
        except: continue
        if re.search(r'20\d{2}',h) and (re.search(r'JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC',h,re.I) or re.match(r'^20\d{2}\s*[A-Za-z]{3}$',h)):
            pairs.append((h,x))
    return pairs

def latest_monthly(pairs):
    return pairs[-1] if pairs else None

def month_key(label):
    m=re.search(r'(20\d{2}).*?(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)',label.upper())
    if not m:
        m=re.search(r'(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC).*?(20\d{2})',label.upper())
        if not m:return None
        mon,yr=m.group(1),m.group(2)
    else: yr,mon=m.group(1),m.group(2)
    mm={'JAN':1,'FEB':2,'MAR':3,'APR':4,'MAY':5,'JUN':6,'JUL':7,'AUG':8,'SEP':9,'OCT':10,'NOV':11,'DEC':12}[mon]
    return f'{yr}-{mm:02d}'

def materialize_awe():
    links=previous_csv_links(get(AWE_PAGE), 'emp.csv')
    obs=[]; errors=[]
    for available,url in links:
        try:
            pairs=parse_ons_csv_for_series(get(url),AWE_ID)
            series={month_key(k):v for k,v in pairs if month_key(k)}
            months=sorted(series)
            if not months: raise ValueError('no monthly observations')
            ref=months[-1]; x=series[ref]
            y0=str(int(ref[:4])-1)+ref[4:]
            yoy=None if y0 not in series else 100*(x/series[y0]-1)
            obs.append({'available_at':available,'reference_month':ref,'index_value':x,'yoy_pct':yoy,'series_id':AWE_ID,'source_url':url})
        except Exception as e: errors.append({'available_at':available,'url':url,'error':str(e)[:200]})
    return obs,errors,len(links)

def materialize_services():
    # Time-series page has direct previous-version CSV links. Use exact D7NN series files only.
    html=get(SERV_PAGE).decode('utf-8','ignore')
    rows=re.findall(r'<tr[^>]*>(.*?)</tr>',html,flags=re.I|re.S)
    links=[]
    for row in rows:
        hrefs=re.findall(r'href=["\']([^"\']+\.csv[^"\']*)["\']',row,flags=re.I)
        if not hrefs: continue
        text=re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',unescape(row))).strip()
        m=re.search(r'(\d{1,2}\s+[A-Za-z]+\s+20\d{2})(?:\s+(\d{2}:\d{2}))?',text)
        if not m: continue
        year=int(re.search(r'20\d{2}',m.group(1)).group())
        if year<START_YEAR: continue
        href=hrefs[0]
        if '/previous/' not in href: continue
        links.append((m.group(1)+((' '+m.group(2)) if m.group(2) else ''),abs_ons(href)))
    links=list(reversed(links))
    obs=[]; errors=[]
    for available,url in links:
        try:
            pairs=parse_ons_csv_for_series(get(url),SERV_ID)
            lm=latest_monthly([(month_key(k),v) for k,v in pairs if month_key(k)])
            if not lm: raise ValueError('no monthly D7NN observation')
            obs.append({'available_at':available,'reference_month':lm[0],'annual_rate_pct':lm[1],'series_id':SERV_ID,'source_url':url})
        except Exception as e: errors.append({'available_at':available,'url':url,'error':str(e)[:200]})
    return obs,errors,len(links)

def write_csv(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not rows:return
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def main():
    awe,aerr,an=materialize_awe(); serv,serr,sn=materialize_services()
    write_csv(OUTDIR/'GBP_AWE_K54L_CERTIFIED_VINTAGES_2018_2026.csv',awe)
    write_csv(OUTDIR/'GBP_CPI_SERVICES_D7NN_CERTIFIED_VINTAGES_2018_2026.csv',serv)
    status='PASS' if len(awe)>=20 and len(serv)>=20 else 'PARTIAL'
    audit={'schema':'GMFQ_GBP_ONS_REACTION_BRIDGES_V1','status':status,'created_at':'2026-10-06','awe':{'series':'K54L','links':an,'materialized':len(awe),'errors':aerr},'services':{'series':'D7NN','links':sn,'materialized':len(serv),'errors':serr},'guardrails':['official ONS previous versions only','no current-series retrofill','first-known vintage timestamps retained','no engine/live_data changes']}
    AUDIT.write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print(json.dumps(audit,indent=2))
    if status!='PASS': raise SystemExit(2)

if __name__=='__main__': main()
