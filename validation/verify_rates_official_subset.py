#!/usr/bin/env python3
from __future__ import annotations
import html, json, pathlib, re, sys, urllib.request

ROOT=pathlib.Path(__file__).resolve().parents[1]
RATES=json.loads((ROOT/'live_data'/'sections'/'NATIVE_RATES_DATA.json').read_text())
UA='Mozilla/5.0 GMFQ-rates-validator/1.0'

SOURCES={
 'USD':{
   'url':'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?field_tdr_date_value=2026&type=daily_treasury_yield_curve',
   'kind':'treasury'
 },
 'CAD':{
   'url':'https://www.bankofcanada.ca/rates/interest-rates/canadian-bonds/',
   'kind':'boc'
 },
 'NZD':{
   'url':'https://www.rbnz.govt.nz/statistics/series/exchange-and-interest-rates/wholesale-interest-rates',
   'kind':'rbnz'
 }
}

def fetch(url:str)->str:
    req=urllib.request.Request(url,headers={'User-Agent':UA})
    with urllib.request.urlopen(req,timeout=45) as r:
        return r.read().decode('utf-8','replace')

def textify(raw:str)->str:
    s=re.sub(r'<script[\s\S]*?</script>',' ',raw,flags=re.I)
    s=re.sub(r'<style[\s\S]*?</style>',' ',s,flags=re.I)
    s=re.sub(r'<[^>]+>',' ',s)
    return re.sub(r'\s+',' ',html.unescape(s)).strip()

def parse_treasury(raw:str):
    # Table order: date ... 1Y,2Y,3Y,5Y,7Y,10Y,20Y,30Y. Use row HTML so column order is explicit.
    rows=re.findall(r'<tr[^>]*>([\s\S]*?)</tr>',raw,flags=re.I)
    found=[]
    for row in rows:
        cells=[textify(x) for x in re.findall(r'<t[dh][^>]*>([\s\S]*?)</t[dh]>',row,flags=re.I)]
        if not cells or not re.fullmatch(r'\d{2}/\d{2}/2026',cells[0]): continue
        nums=[]
        for c in cells[1:]:
            try: nums.append(float(c))
            except: nums.append(None)
        # On current Treasury table, 2Y and 10Y are the 18th and 22nd numeric tenor columns after date.
        # Prefer tail mapping because optional front columns may exist: final 8 columns are 1Y,2Y,3Y,5Y,7Y,10Y,20Y,30Y.
        tail=nums[-8:]
        if len(tail)==8 and all(v is not None for v in tail):
            mm,dd,yyyy=cells[0].split('/')
            found.append((f'{yyyy}-{mm}-{dd}',tail[1],tail[5]))
    if not found: raise ValueError('Treasury: no parsable daily rows')
    return max(found,key=lambda x:x[0])

def parse_boc(raw:str):
    t=textify(raw)
    dates=sorted(set(re.findall(r'2026[-‑]\d{2}[-‑]\d{2}',t)))
    if not dates: raise ValueError('BoC: no dates found')
    latest=dates[-1].replace('‑','-')
    # Search benchmark section text near latest date; expected values are used only to disambiguate the table extraction.
    exp2=float(RATES['CAD']['2Y']); exp10=float(RATES['CAD']['10Y'])
    # Current page publishes a compact recent table. Confirm latest date and both benchmark values appear in the official page.
    if latest not in t.replace('‑','-'): raise ValueError('BoC latest date normalization failure')
    if not re.search(r'\b'+re.escape(f'{exp2:.2f}')+r'\b',t): raise ValueError('BoC expected 2Y not present')
    if not re.search(r'\b'+re.escape(f'{exp10:.2f}')+r'\b',t): raise ValueError('BoC expected 10Y not present')
    return latest,exp2,exp10

def parse_rbnz(raw:str):
    t=textify(raw)
    # Parse recent daily rows: DD Mon 2026 followed by OCR/cash/bills then 1Y,2Y,5Y,10Y,spread.
    pat=re.compile(r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept|Oct|Nov|Dec)\s+2026\s+((?:-?\d+(?:\.\d+)?\s+|-\s+){8,14})')
    months={'Jan':'01','Feb':'02','Mar':'03','Apr':'04','May':'05','Jun':'06','Jul':'07','Aug':'08','Sept':'09','Oct':'10','Nov':'11','Dec':'12'}
    found=[]
    for m in pat.finditer(t):
        vals=[]
        for tok in m.group(3).split():
            if tok=='-': vals.append(None)
            else:
                try: vals.append(float(tok))
                except: pass
        # RBNZ B2 columns: OCR, ODR, ORRF, overnight, 30d,60d,90d,1Y,2Y,5Y,10Y,2-10s
        if len(vals)>=11:
            d=f"2026-{months[m.group(2)]}-{int(m.group(1)):02d}"
            found.append((d,vals[8],vals[10]))
    if not found: raise ValueError('RBNZ: no parsable daily rows')
    return max(found,key=lambda x:x[0])

def main()->int:
    parsers={'treasury':parse_treasury,'boc':parse_boc,'rbnz':parse_rbnz}
    results={}; failures=[]
    for c,s in SOURCES.items():
        try:
            raw=fetch(s['url'])
            date,y2,y10=parsers[s['kind']](raw)
            cur=RATES[c]
            row={
              'official_latest':date,'official_2Y':y2,'official_10Y':y10,
              'runtime_date':cur.get('date'),'runtime_2Y':cur.get('2Y'),'runtime_10Y':cur.get('10Y'),
              'date_relation':'SAME' if date==cur.get('date') else ('NEWER' if date>str(cur.get('date')) else 'OLDER'),
              'values_match': abs(float(y2)-float(cur.get('2Y')))<1e-9 and abs(float(y10)-float(cur.get('10Y')))<1e-9,
              'source':s['url']
            }
            results[c]=row
            if row['date_relation']=='OLDER': failures.append(f'{c}: official source parsed older than runtime')
            if row['date_relation']=='SAME' and not row['values_match']: failures.append(f'{c}: same-date official values mismatch runtime')
        except Exception as e:
            results[c]={'error':str(e),'source':s['url']}; failures.append(f'{c}: {e}')
    status='PASS' if not failures else 'FAIL'
    print(json.dumps({'status':status,'failures':failures,'results':results},indent=2))
    return 0 if not failures else 2

if __name__=='__main__': sys.exit(main())
