#!/usr/bin/env python3
from __future__ import annotations
import copy, json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'validation'))
from build_macro_candidate import apply_candidate
BEFORE='0467d03f500dbaaf640bc653466457c5962e88b5'
AFTER='f1bb0f6256277f092f0d540a9c34d63dc7ddbd60'
SERIES='live_data/sections/MACRO_SERIES.json'
HEAT='live_data/sections/MACRO_THERMOMETER_DATA.json'
def gj(ref,path): return json.loads(subprocess.check_output(['git','show',f'{ref}:{path}'],text=True))
def main():
 b=gj(BEFORE,SERIES); a=gj(AFTER,SERIES); bh=gj(BEFORE,HEAT); ah=gj(AFTER,HEAT)
 bm={r.get('id'):r for r in b['JPY']}; am={r.get('id'):r for r in a['JPY']}
 ids=[k for k in sorted(set(bm)|set(am)) if bm.get(k)!=am.get(k)]
 if len(ids)!=1: raise SystemExit(f'Expected one changed JPY series, got {ids}')
 sid=ids[0]; ar=am[sid]; h=ah['currencies']['JPY']['labour']
 c={'currency':'JPY','dimension':'labour','macro_series_id':sid,'observation_date':ar['last_date'],'value':ar['last_value'],'source':h['source'],'series_id':h['series_id'],'frequency':h['frequency'],'transformation':h['transformation']}
 if ar.get('unit') is not None: c['unit']=ar['unit']
 rs=copy.deepcopy(b); rh=copy.deepcopy(bh); summary=apply_candidate(rs,rh,c)
 out={'status':'PASS' if rs==a and rh==ah else 'FAIL','macro_series_exact_match':rs==a,'heatmap_exact_match':rh==ah,'candidate':c,'builder_summary':summary,'live_data_written':False,'engine_rules_changed':False}
 print(json.dumps(out,ensure_ascii=False,indent=2)); return 0 if out['status']=='PASS' else 1
if __name__=='__main__': raise SystemExit(main())
