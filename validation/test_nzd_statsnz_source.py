#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ADAPTER=ROOT/'validation/sources/nzd_statsnz_core.py';BUILDER=ROOT/'validation/build_macro_candidate.py'
FIX={'inflation':ROOT/'validation/fixtures/nzd_statsnz_cpi_contract.json','labour':ROOT/'validation/fixtures/nzd_statsnz_unemployment_contract.json'}
LIVE=[ROOT/'live_data/sections/MACRO_SERIES.json',ROOT/'live_data/sections/MACRO_THERMOMETER_DATA.json']
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(*a):subprocess.run([sys.executable,*a],cwd=ROOT,check=True)
def check(dim,root):
 c=root/f'{dim}-candidate.json';a=root/f'{dim}-audit.json';b=root/f'{dim}-built'
 run(str(ADAPTER),'--dimension',dim,'--fixture',str(FIX[dim]),'--output',str(c),'--audit-output',str(a));x=json.loads(c.read_text());u=json.loads(a.read_text())
 assert x['currency']=='NZD' and x['source']=='Stats NZ' and x['observation_date']=='2026-06-01';assert u['candidate_only'] is True and u['live_data_written'] is False
 if dim=='inflation': assert x['series_id']=='NZ_CPI_HEADLINE_YOY' and x['macro_series_id']=='NZ_CPI_HEADLINE_YOY_history_value' and x['frequency']=='Q' and x['transformation']=='reported_yoy_rate' and abs(float(x['value'])-4.1)<1e-12
 else: assert x['series_id']=='NZ_UNEMP_RATE' and x['macro_series_id']=='NZ_UNEMP_RATE_history_value' and x['frequency']=='Q' and x['transformation']=='level' and abs(float(x['value'])-5.6)<1e-12
 run(str(BUILDER),'--candidate',str(c),'--output-dir',str(b));s=json.loads((b/'summary.json').read_text());assert s['status']=='PASS' and s['live_data_modified'] is False and s['observation_date']==x['observation_date'];return {'dimension':dim,'value':x['value'],'series_action':s['series_action']}
def main():
 before={str(p):h(p) for p in LIVE}
 with tempfile.TemporaryDirectory(prefix='gmfq-nzd-statsnz-') as td:r=[check('inflation',Path(td)),check('labour',Path(td))]
 assert before=={str(p):h(p) for p in LIVE};print(json.dumps({'status':'PASS','source':'Stats NZ','results':r,'live_data_modified':False},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
