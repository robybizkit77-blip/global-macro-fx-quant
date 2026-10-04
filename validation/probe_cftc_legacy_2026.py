from pathlib import Path
import urllib.request,zipfile,io,csv,json,re
URL='https://www.cftc.gov/files/dea/history/deacot2026.zip'
CODES={'EUR':'099741','GBP':'096742','JPY':'097741','CHF':'092741','AUD':'232741','NZD':'112741','CAD':'090741','USD':'098662'}
req=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0 GMFQ/1.0'})
raw=urllib.request.urlopen(req,timeout=45).read()
z=zipfile.ZipFile(io.BytesIO(raw))
member=next((n for n in z.namelist() if n.lower().endswith(('.txt','.csv'))),z.namelist()[0])
text=z.read(member).decode('utf-8-sig',errors='replace')
reader=csv.DictReader(io.StringIO(text))
headers=reader.fieldnames or []
rows=list(reader)

def norm(s): return re.sub(r'[^a-z0-9]+','_',str(s).lower()).strip('_')
nh={norm(h):h for h in headers}
def pick(*cands):
    for c in cands:
        if c in nh:return nh[c]
    for c in cands:
        for k,h in nh.items():
            if c in k:return h
    return None
code_col=pick('cftc_contract_market_code','contract_market_code','cftc_contract_market_code_quotes')
date_col=pick('as_of_date_in_form_yyyy_mm_dd','report_date_as_yyyy_mm_dd','as_of_date_in_form_yyyymmdd','report_date')
long_col=pick('noncomm_positions_long_all','noncommercial_positions_long_all','noncomm_positions_long')
short_col=pick('noncomm_positions_short_all','noncommercial_positions_short_all','noncomm_positions_short')
oi_col=pick('open_interest_all','open_interest')
if not all([code_col,date_col,long_col,short_col,oi_col]):
    raise RuntimeError('Required columns not resolved: '+json.dumps({'code':code_col,'date':date_col,'long':long_col,'short':short_col,'oi':oi_col,'headers':headers}))
out={'schema':'GMFQ_CFTC_LEGACY_SOURCE_PROBE_V1','source':URL,'member':member,'resolved_columns':{'code':code_col,'date':date_col,'long':long_col,'short':short_col,'open_interest':oi_col},'headers':headers,'currencies':{}}
for ccy,code in CODES.items():
    rr=[r for r in rows if str(r.get(code_col,'')).strip().replace('"','')==code]
    rr.sort(key=lambda r:str(r.get(date_col,'')))
    if not rr: raise RuntimeError(f'No rows for {ccy} {code}')
    r=rr[-1]
    out['currencies'][ccy]={'code':code,'rows':len(rr),'latest_date':r.get(date_col),'long':r.get(long_col),'short':r.get(short_col),'open_interest':r.get(oi_col)}
Path('validation/COT_REFRESH_SOURCE_PROBE_2026-10-04.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out['currencies'],ensure_ascii=False))
