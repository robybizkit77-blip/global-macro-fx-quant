#!/usr/bin/env python3
"""Read-only discovery of official annual CFTC Legacy Futures Only history.

This proves transport + schema + G8 contract-code coverage only. It does NOT
assign historical publication availability and therefore does not certify the
rows for walk-forward/backtest use.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import pathlib
import urllib.request
import zipfile
from datetime import datetime

YEARS=range(2018,2027)
CODES={
    'EUR':'099741','GBP':'096742','JPY':'097741','CHF':'092741',
    'AUD':'232741','NZD':'112741','CAD':'090741','USD':'098662',
}
BASE='https://www.cftc.gov/files/dea/history/deacot{year}.zip'
UA='global-macro-fx-quant/cot-legacy-full-history-discovery-v1'

# Official CFTC Legacy comma-delimited variable positions (1-indexed docs):
# 3 report date YYYY-MM-DD, 4 contract market code, 8 OI,
# 9 noncommercial long, 10 noncommercial short.
IDX={'report_date':2,'code':3,'open_interest':7,'long':8,'short':9}


def sha(raw:bytes)->str:
    return hashlib.sha256(raw).hexdigest()


def fetch(url:str)->bytes:
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/zip,*/*;q=0.8'})
    with urllib.request.urlopen(req,timeout=90) as r:
        raw=r.read()
        if r.status!=200: raise RuntimeError(f'HTTP {r.status}: {url}')
        return raw


def norm_code(value:str)->str:
    return value.strip().strip('"').strip()


def parse_int(value:str)->int:
    return int(value.strip().replace(',',''))


def parse_zip(year:int, raw:bytes)->dict:
    if not raw.startswith(b'PK'):
        raise RuntimeError(f'{year}: response is not ZIP')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        files=[n for n in z.namelist() if not n.endswith('/')]
        if len(files)!=1:
            raise RuntimeError(f'{year}: expected exactly one annual data member, got {files}')
        member=files[0]
        payload=z.read(member)
    text=payload.decode('latin-1')
    reader=csv.reader(io.StringIO(text))
    rows=[]
    widths=set()
    for rawrow in reader:
        if not rawrow: continue
        widths.add(len(rawrow))
        if len(rawrow)<=IDX['short']:
            raise RuntimeError(f'{year}: row too short: {len(rawrow)}')
        code=norm_code(rawrow[IDX['code']])
        if code not in CODES.values(): continue
        report_date=rawrow[IDX['report_date']].strip().strip('"')
        try:
            report_date=datetime.strptime(report_date,'%Y-%m-%d').date().isoformat()
        except ValueError as exc:
            raise RuntimeError(f'{year}: bad report date {report_date!r} for {code}') from exc
        oi=parse_int(rawrow[IDX['open_interest']])
        longv=parse_int(rawrow[IDX['long']])
        shortv=parse_int(rawrow[IDX['short']])
        if oi<=0 or longv<0 or shortv<0:
            raise RuntimeError(f'{year}: invalid position values for {code}/{report_date}')
        rows.append({
            'report_date':report_date,'code':code,'open_interest':oi,
            'noncommercial_long':longv,'noncommercial_short':shortv,
            'noncommercial_net':longv-shortv,
        })
    by_code={code:[] for code in CODES.values()}
    for row in rows: by_code[row['code']].append(row)
    currencies={}
    reverse={v:k for k,v in CODES.items()}
    for code, vals in by_code.items():
        vals=sorted(vals,key=lambda r:r['report_date'])
        dates=[r['report_date'] for r in vals]
        if not vals:
            raise RuntimeError(f'{year}: target code {code} missing')
        if len(dates)!=len(set(dates)):
            raise RuntimeError(f'{year}: duplicate report dates for {code}')
        if any(d[:4] != str(year) for d in dates):
            raise RuntimeError(f'{year}: out-of-year report date for {code}: {dates[0]}..{dates[-1]}')
        currencies[reverse[code]]={
            'code':code,'observations':len(vals),'start_date':dates[0],'end_date':dates[-1],
            'semantic_sha256':sha(json.dumps(vals,sort_keys=True,separators=(',',':')).encode()),
        }
    semantic_rows=sorted(rows,key=lambda r:(r['report_date'],r['code']))
    return {
        'year':year,
        'member':member,
        'zip_sha256':sha(raw),
        'member_sha256':sha(payload),
        'bytes':len(raw),
        'member_bytes':len(payload),
        'row_widths':sorted(widths),
        'target_rows':len(rows),
        'currencies':currencies,
        'semantic_sha256':sha(json.dumps(semantic_rows,sort_keys=True,separators=(',',':')).encode()),
    }


def run_once()->dict:
    annual=[]
    for year in YEARS:
        url=BASE.format(year=year)
        annual.append({'source_url':url,**parse_zip(year,fetch(url))})
    return {
        'schema':'GMFQ_COT_LEGACY_FULL_HISTORY_DISCOVERY_V1',
        'status':'DISCOVERY_PASS',
        'authority':'U.S. Commodity Futures Trading Commission (CFTC)',
        'report':'Legacy Commitments of Traders - Futures Only',
        'participant_class':'Non-Commercial',
        'years':[2018,2019,2020,2021,2022,2023,2024,2025,2026],
        'currency_codes':CODES,
        'annual':annual,
        'invariants':{
            'official_cftc_domain_only':True,
            'legacy_futures_only_annual_archives':True,
            'official_variable_positions_used':True,
            'all_eight_codes_required_each_year':True,
            'duplicate_report_dates_forbidden':True,
            'publication_availability_assigned':False,
            'historical_backtest_certified':False,
            'production_write':False,
        },
    }


def semantic_view(d:dict)->dict:
    return {
        'schema':d['schema'],'status':d['status'],'authority':d['authority'],'report':d['report'],
        'participant_class':d['participant_class'],'years':d['years'],'currency_codes':d['currency_codes'],
        'annual':[
            {
                'year':x['year'],'member':x['member'],'member_sha256':x['member_sha256'],
                'row_widths':x['row_widths'],'target_rows':x['target_rows'],
                'currencies':x['currencies'],'semantic_sha256':x['semantic_sha256'],
            } for x in d['annual']
        ],
        'invariants':d['invariants'],
    }


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=pathlib.Path); args=ap.parse_args()
    d=run_once()
    d['semantic_discovery_sha256']=sha(json.dumps(semantic_view(d),sort_keys=True,separators=(',',':')).encode())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({
        'status':d['status'],'years':d['years'],
        'annual':[{k:x[k] for k in ('year','member','target_rows','row_widths','semantic_sha256')} for x in d['annual']],
        'semantic_discovery_sha256':d['semantic_discovery_sha256'],
    },indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
