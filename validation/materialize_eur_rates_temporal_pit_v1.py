#!/usr/bin/env python3
"""Read-only materializer for ECB EUR 2Y/10Y temporal-PIT history."""
from __future__ import annotations
import argparse,csv,hashlib,io,json
from datetime import date,timedelta
from pathlib import Path
from urllib.request import Request,urlopen

START_DATE=date(2018,1,1)
END_DATE=date(2026,10,6)
UA='global-macro-fx-quant/eur-rates-temporal-pit-v1'
TMPL='https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.{series}?format=csvdata&startPeriod=2018-01-01&endPeriod=2026-10-06'
SERIES={'2Y':'SR_2Y','10Y':'SR_10Y'}

def fetch(series:str)->tuple[bytes,str]:
    url=TMPL.format(series=series)
    req=Request(url,headers={'User-Agent':UA,'Accept':'text/csv,*/*;q=0.1'})
    with urlopen(req,timeout=60) as r:
        raw=r.read()
        if len(raw)<1000: raise ValueError(f'ECB CSV unexpectedly small for {series}: {len(raw)} bytes')
        return raw,url

def parse(raw:bytes,label:str)->dict[str,float]:
    rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    out={}
    for r in rows:
        ds=(r.get('TIME_PERIOD') or r.get('TIME_PERIOD_START') or '').strip()
        vs=(r.get('OBS_VALUE') or '').strip()
        if not ds or not vs: continue
        d=date.fromisoformat(ds[:10])
        if d<START_DATE or d>END_DATE: continue
        v=float(vs)
        if not (-5.0<v<25.0): raise ValueError(f'ECB implausible {label} yield {d}: {v}')
        if ds in out: raise ValueError(f'ECB duplicate {label} date {ds}')
        out[d.isoformat()]=v
    if not out: raise ValueError(f'ECB no usable {label} observations')
    return out

def semantic_hash(rows):
    fields=('currency','observation_date','yield_2y','yield_10y','source_basis','first_eligible_decision_date')
    payload=[{k:r[k] for k in fields} for r in rows]
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def materialize():
    raw2,url2=fetch(SERIES['2Y']); raw10,url10=fetch(SERIES['10Y'])
    p2=parse(raw2,'2Y'); p10=parse(raw10,'10Y')
    if set(p2)!=set(p10):
        only2=sorted(set(p2)-set(p10))[:10]; only10=sorted(set(p10)-set(p2))[:10]
        raise ValueError(f'ECB same-basis date mismatch only2={only2} only10={only10}')
    dates=sorted(p2)
    if not dates or not dates[0].startswith('2018-'): raise ValueError('ECB history does not begin in 2018')
    if dates[-1]!=END_DATE.isoformat(): raise ValueError(f'ECB history does not reach pinned end date {END_DATE}: last={dates[-1]}')
    rows=[]
    for ds in dates:
        obs=date.fromisoformat(ds)
        rows.append({'currency':'EUR','observation_date':ds,'yield_2y':p2[ds],'yield_10y':p10[ds],
                     'curve_bp':round((p10[ds]-p2[ds])*100,6),'source_authority':'European Central Bank',
                     'source_family':'ECB AAA Svensson spot curve','source_url_2y':url2,'source_url_10y':url10,
                     'source_basis':'official_same_basis_ecb_aaa_svensson_spot_curve',
                     'publication_timestamp_verified':False,
                     'availability_rule':'decision_date_strictly_after_observation_date_without_verified_publication_timestamp',
                     'first_eligible_decision_date':(obs+timedelta(days=1)).isoformat(),
                     'pit_status':'TEMPORAL_PIT_CONSERVATIVE_DATE_ONLY'})
    return {'schema':'GMFQ_EUR_RATES_TEMPORAL_PIT_EVIDENCE_V1_RUNTIME','status':'PASS','target':'EUR.rates_2y_10y',
            'evidence_class':'TEMPORAL_PIT_OFFICIAL_MARKET_HISTORY','authority':'European Central Bank',
            'source':'ECB AAA Svensson spot curve, SR_2Y and SR_10Y','coverage':{'start_date':dates[0],'end_date':dates[-1],'observations':len(rows)},
            'temporal_rule':{'exact_publication_timestamp_verified':False,'same_day_use_allowed':False,'eligibility':'decision_date > observation_date','reason':'No independently verified official publication timestamp is attached to each historical daily row; use conservative next-decision-point availability.'},
            'source_hashes':{'SR_2Y':hashlib.sha256(raw2).hexdigest(),'SR_10Y':hashlib.sha256(raw10).hexdigest()},
            'semantic_rowset_sha256':semantic_hash(rows),'same_basis_2y_10y':True,'secondary_source_fallback_used':False,
            'changes_live_data':False,'changes_engine_rules':False,'rows':rows}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args()
    e=materialize(); a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(e,indent=2)+'\n')
    print(json.dumps({k:v for k,v in e.items() if k!='rows'},indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
