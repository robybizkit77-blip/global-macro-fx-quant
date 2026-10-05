#!/usr/bin/env python3
import csv, io, json, sys, urllib.request, zipfile
from datetime import datetime
from pathlib import Path

ECB_TMPL = 'https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.{series}?format=csvdata&startPeriod=2026-01-01'
BOE_ZIP = 'https://www.bankofengland.co.uk/-/media/boe/files/statistics/yield-curves/latest-yield-curve-data.zip'

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent':'GMFQ-Rates-Audit/1.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()

def ecb(series):
    raw = get(ECB_TMPL.format(series=series)).decode('utf-8-sig')
    rows = list(csv.DictReader(io.StringIO(raw)))
    vals=[]
    for r in rows:
        d=r.get('TIME_PERIOD') or r.get('TIME_PERIOD_START')
        v=r.get('OBS_VALUE')
        if d and v not in (None,''):
            try: vals.append((d,float(v)))
            except: pass
    if not vals: raise RuntimeError(f'ECB no observations for {series}')
    return max(vals, key=lambda x:x[0])

def boe():
    raw=get(BOE_ZIP)
    z=zipfile.ZipFile(io.BytesIO(raw))
    names=z.namelist()
    xlsx=[n for n in names if n.lower().endswith(('.xlsx','.xlsm'))]
    if not xlsx: raise RuntimeError('BoE ZIP contains no xlsx')
    import openpyxl
    candidates=[]
    for name in xlsx:
        wb=openpyxl.load_workbook(io.BytesIO(z.read(name)), read_only=True, data_only=True)
        for ws in wb.worksheets:
            rows=list(ws.iter_rows(values_only=True))
            if len(rows)<3: continue
            # Look for header row containing maturity points around 2 and 10 years.
            for hi,row in enumerate(rows[:25]):
                norm=[]
                for x in row:
                    try: norm.append(float(x))
                    except: norm.append(None)
                idx2=[i for i,x in enumerate(norm) if x is not None and abs(x-2.0)<1e-9]
                idx10=[i for i,x in enumerate(norm) if x is not None and abs(x-10.0)<1e-9]
                if not idx2 or not idx10: continue
                i2,i10=idx2[0],idx10[0]
                data=[]
                for rr in rows[hi+1:]:
                    if max(i2,i10)>=len(rr): continue
                    dv=rr[0] if rr else None
                    if isinstance(dv, datetime): d=dv.date().isoformat()
                    elif hasattr(dv,'isoformat'):
                        try: d=dv.isoformat()
                        except: continue
                    elif isinstance(dv,str):
                        parsed=None
                        for fmt in ('%d/%m/%Y','%d-%b-%Y','%Y-%m-%d','%d %b %Y'):
                            try: parsed=datetime.strptime(dv.strip(),fmt).date().isoformat(); break
                            except: pass
                        if not parsed: continue
                        d=parsed
                    else: continue
                    try: v2=float(rr[i2]); v10=float(rr[i10])
                    except: continue
                    data.append((d,v2,v10,name,ws.title))
                if data:
                    candidates.append(max(data,key=lambda x:x[0]))
    if not candidates:
        raise RuntimeError('Could not locate BoE nominal spot 2Y/10Y table')
    # prefer sheets whose names indicate nominal/government/spot
    ranked=sorted(candidates,key=lambda x:(sum(k in x[4].lower() for k in ('nominal','government','spot')),x[0]),reverse=True)
    return ranked[0], names

def main():
    rates=json.loads(Path('live_data/sections/NATIVE_RATES_DATA.json').read_text())
    e2=ecb('SR_2Y'); e10=ecb('SR_10Y')
    if e2[0]!=e10[0]: raise RuntimeError(f'ECB same-day mismatch {e2[0]} vs {e10[0]}')
    b,names=boe()
    out={
      'EUR':{'official_date':e2[0],'2Y':e2[1],'10Y':e10[1],'current_date':rates['EUR']['date'],'current_2Y':rates['EUR']['2Y'],'current_10Y':rates['EUR']['10Y']},
      'GBP':{'official_date':b[0],'2Y':b[1],'10Y':b[2],'current_date':rates['GBP']['date'],'current_2Y':rates['GBP']['2Y'],'current_10Y':rates['GBP']['10Y'],'boe_file':b[3],'boe_sheet':b[4]},
      'boe_zip_entries':names
    }
    print(json.dumps(out,indent=2,ensure_ascii=False))
    Path('validation/rates_eur_gbp_audit_output.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')

if __name__=='__main__': main()
