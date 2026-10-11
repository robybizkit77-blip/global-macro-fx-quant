#!/usr/bin/env python3
"""Result-blind canonical adapter for PR #123 macro inputs.

This adapter performs only schema normalization. It does not transform the
economic meaning of a source value, interpolate observations, impute missing
releases, or inspect any conditional-backtest outcome.

Canonical CSV columns:
  reference_period,release_date,value,availability_status

Rules are explicit per certified source stream. JPY inflation derives
reference_period as YYYY-MM from the source observation_date only; all other
period labels and numeric values are copied directly from certified source
rows. Certified release dates are normalized mechanically to ISO YYYY-MM-DD so
temporal comparisons use one canonical representation. Official unavailable
rows remain null.
"""
from __future__ import annotations

import argparse,csv,datetime as dt,hashlib,json,pathlib

STREAMS={
  'EUR_INFLATION': {'period':'reference_month','value':'headline_hicp_yoy_pct'},
  'EUR_LABOUR': {'period':'reference_month','value':'unemployment_rate_pct'},
  'JPY_INFLATION': {'period':'observation_date','value':'value','period_transform':'month_from_date'},
  'JPY_LABOUR': {'period':'reference_month','value':'unemployment_rate_sa_pct'},
  'CAD_INFLATION': {'period':'reference_month','value':'cpi_yoy_full_precision'},
  'CAD_LABOUR': {'period':'reference_month','value':'unemployment_rate_sa'},
  'AUD_INFLATION': {'period':'reference_quarter','value':'cpi_yoy'},
  'AUD_LABOUR': {'period':'reference_month','value':'unemployment_rate_sa'},
  'USD_INFLATION': {'period':'reference_month','value':'cpi_yoy'},
  'USD_LABOUR': {'period':'reference_month','value':'unemployment_rate'},
}
UNAVAILABLE={'UNAVAILABLE_OFFICIAL_NOT_PUBLISHED','NOT_PUBLISHED_OFFICIAL'}
AVAILABLE={'AVAILABLE_STRICT_PIT','PUBLISHED','CERTIFIED'}


def ref_period(raw:str,transform:str|None)->str:
    x=raw.strip()
    if not x: raise ValueError('missing reference period')
    if transform=='month_from_date':
        if len(x)<7 or x[4]!='-': raise ValueError(f'invalid observation date {x!r}')
        return x[:7]
    return x


def release_date_iso(raw:str)->str:
    """Normalize certified date spelling only; never infer a missing date."""
    x=raw.strip()
    if not x: raise ValueError('missing release date')
    token=x[:10]
    for fmt in ('%Y-%m-%d','%d/%m/%Y'):
        try:
            return dt.datetime.strptime(token,fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f'unsupported certified release date format {raw!r}')


def adapt(stream:str,source:pathlib.Path)->dict:
    if stream not in STREAMS: raise ValueError(f'unsupported stream {stream}')
    cfg=STREAMS[stream]
    rows=[]
    with source.open(newline='',encoding='utf-8-sig') as f:
        rd=csv.DictReader(f)
        fields=set(rd.fieldnames or [])
        required={cfg['period'],cfg['value']}
        if 'release_date' not in fields and 'first_eligible_decision_date' not in fields and 'eligible_date' not in fields:
            raise ValueError(f'{stream}: no certified release/eligibility field')
        if not required.issubset(fields):
            raise ValueError(f'{stream}: missing fields {sorted(required-fields)}')
        for i,r in enumerate(rd,1):
            status=(r.get('availability_status') or '').strip()
            val=(r.get(cfg['value']) or '').strip()
            rel=(r.get('release_date') or r.get('first_eligible_decision_date') or r.get('eligible_date') or '').strip()
            period_raw=(r.get(cfg['period']) or '').strip()

            if status in UNAVAILABLE:
                # An unavailable release is preserved only when it carries no
                # usable value and no release date. The reference period is
                # still required so coverage remains explicit.
                if val or rel:
                    raise ValueError(f'{stream} row {i}: unavailable row contains value/date')
                period=ref_period(period_raw,cfg.get('period_transform'))
                rows.append({'reference_period':period,'release_date':'','value':'','availability_status':'UNAVAILABLE_OFFICIAL_NOT_PUBLISHED'})
                continue

            if not rel: raise ValueError(f'{stream} row {i}: missing release eligibility')
            if not val: raise ValueError(f'{stream} row {i}: missing value')
            period=ref_period(period_raw,cfg.get('period_transform'))
            try: numeric=float(val)
            except ValueError as e: raise ValueError(f'{stream} row {i}: nonnumeric value {val!r}') from e
            rows.append({'reference_period':period,'release_date':release_date_iso(rel),'value':format(numeric,'.15g'),'availability_status':'AVAILABLE_STRICT_PIT'})

    if not rows: raise ValueError(f'{stream}: empty input')
    # Never reorder source chronology silently. Certified files are expected to
    # be in release order; duplicate reference periods would make change
    # semantics ambiguous and fail closed.
    periods=[r['reference_period'] for r in rows]
    if len(periods)!=len(set(periods)):
        raise ValueError(f'{stream}: duplicate reference periods')
    semantic_sha=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'schema':'GMFQ_G4USD_MACRO_INPUT_ADAPTER_V1','stream':stream,'rows':rows,'semantic_sha256':semantic_sha,
            'policy':{'economic_transform':False,'interpolation':False,'imputation':False,'result_blind':True}}


def write_csv(out:dict,path:pathlib.Path)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as f:
        wr=csv.DictWriter(f,fieldnames=['reference_period','release_date','value','availability_status'])
        wr.writeheader(); wr.writerows(out['rows'])


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--stream',required=True,choices=sorted(STREAMS)); ap.add_argument('--source',required=True,type=pathlib.Path); ap.add_argument('--output',required=True,type=pathlib.Path); ap.add_argument('--receipt',type=pathlib.Path)
    a=ap.parse_args(); out=adapt(a.stream,a.source); write_csv(out,a.output)
    if a.receipt:
        a.receipt.parent.mkdir(parents=True,exist_ok=True); a.receipt.write_text(json.dumps({k:v for k,v in out.items() if k!='rows'},indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k!='rows'},indent=2,sort_keys=True))

if __name__=='__main__': main()