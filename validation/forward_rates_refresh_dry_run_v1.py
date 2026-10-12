#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,importlib,json,math
from datetime import date
from pathlib import Path

CCYS=('usd','eur','jpy','cad','aud')
MODULES={c:f'materialize_{c}_rates_temporal_pit_v1' for c in CCYS}
FIELDS=('observation_date','yield_2y','yield_10y','first_eligible_decision_date')

def load_base(path:Path):
    with path.open(newline='',encoding='utf-8-sig') as f: return list(csv.DictReader(f))

def same_num(a,b): return math.isclose(float(a),float(b),rel_tol=0.0,abs_tol=1e-12)

def configure(mod,c,target:date):
    mod.END_DATE=target
    if c=='eur':
        mod.TMPL=f'https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.{{series}}?format=csvdata&startPeriod=2018-01-01&endPeriod={target.isoformat()}'

def compare_prefix(c,base,new):
    by={r['observation_date']:r for r in new}
    for b in base:
        ds=b['observation_date']; n=by.get(ds)
        if n is None: raise RuntimeError(f'{c}: historical row disappeared {ds}')
        if not same_num(b['yield_2y'],n['yield_2y']) or not same_num(b['yield_10y'],n['yield_10y']):
            raise RuntimeError(f'{c}: historical yield drift {ds}: base=({b["yield_2y"]},{b["yield_10y"]}) new=({n["yield_2y"]},{n["yield_10y"]})')
        if b['first_eligible_decision_date'] != n['first_eligible_decision_date']:
            raise RuntimeError(f'{c}: PIT eligibility drift {ds}: {b["first_eligible_decision_date"]} != {n["first_eligible_decision_date"]}')
    base_last=base[-1]['observation_date']
    appended=[r for r in new if r['observation_date']>base_last]
    return base_last,appended

def write_rowset(path,rows):
    fields=['observation_date','yield_2y','yield_10y','first_eligible_decision_date','first_eligible_decision_point']
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows:
            w.writerow({k:r.get(k,'') for k in fields})

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base-dir',required=True,type=Path);ap.add_argument('--target-date',required=True);ap.add_argument('--output-dir',required=True,type=Path);a=ap.parse_args()
    target=date.fromisoformat(a.target_date)
    summary=[]
    for c in CCYS:
        mod=importlib.import_module(MODULES[c]);configure(mod,c,target)
        e=mod.materialize();rows=e['rows']
        base=load_base(a.base_dir/f'{c}_rates_2y_10y_temporal_pit_v1.csv')
        base_last,appended=compare_prefix(c,base,rows)
        if not appended: raise RuntimeError(f'{c}: no forward observations appended beyond {base_last}')
        if rows[-1]['observation_date']!=target.isoformat(): raise RuntimeError(f'{c}: target not reached last={rows[-1]["observation_date"]} target={target}')
        write_rowset(a.output_dir/f'{c}.csv',rows)
        summary.append({'currency':c.upper(),'base_last_observation':base_last,'new_last_observation':rows[-1]['observation_date'],'appended_rows':len(appended),'first_appended_observation':appended[0]['observation_date'],'last_appended_observation':appended[-1]['observation_date'],'last_appended_first_eligible':appended[-1]['first_eligible_decision_date'],'semantic_rowset_sha256':e['semantic_rowset_sha256'],'authority':e['authority'],'same_basis_2y_10y':e['same_basis_2y_10y'],'secondary_source_fallback_used':e['secondary_source_fallback_used']})
    out={'schema':'GMFQ_FORWARD_RATES_REFRESH_DRY_RUN_V1','status':'PASS_5_OF_5_FORWARD_EXTENSION','target_observation_date':target.isoformat(),'currencies':summary,'rates_green':5,'historical_prefix_unchanged':True,'repository_write_performed':False,'production_signal_authorized':False,'sizing_authorized':False,'shared_boundary_advanced':False}
    (a.output_dir/'result.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps(out,indent=2,sort_keys=True))
if __name__=='__main__': main()
