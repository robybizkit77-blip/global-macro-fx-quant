#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ADAPTER=ROOT/'validation/sources/chf_snb_official_core.py'
FIX={'inflation':ROOT/'validation/fixtures/chf_snb_cpi_contract.json','labour':ROOT/'validation/fixtures/chf_snb_unemployment_contract.json'}
LIVE=[ROOT/'live_data/sections/MACRO_SERIES.json',ROOT/'live_data/sections/MACRO_THERMOMETER_DATA.json']
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(*a):subprocess.run([sys.executable,*a],cwd=ROOT,check=True)
def check(dim,root):
 c=root/f'{dim}-candidate.json';a=root/f'{dim}-audit.json'
 run(str(ADAPTER),'--dimension',dim,'--fixture',str(FIX[dim]),'--output',str(c),'--audit-output',str(a));x=json.loads(c.read_text());u=json.loads(a.read_text())
 assert x['currency']=='CHF' and x['observation_date']=='2026-08-01';assert u['candidate_only'] is True and u['live_data_written'] is False and u['mode']=='fixture'
 if dim=='inflation':
  assert x['series_id']=='CH_CPI_HEADLINE_YOY' and x['macro_series_id']=='CH_CPI_HEADLINE_YOY_history_value' and x['frequency']=='M' and x['transformation']=='reported_yoy_rate'
  assert abs(float(x['value'])-0.8)<1e-12 and abs(float(u['raw_value'])-0.8072460486750788)<1e-12 and u['normalization']=='round_to_1_decimal_reported_rate'
  assert u['upstream_cube']=='plkopr' and u['upstream_series_label']=='Change from the corresponding month of the previous year in %'
 else:
  assert x['series_id']=='CH_UNEMP_RATE' and x['macro_series_id']=='CH_UNEMP_RATE_history_value' and x['frequency']=='M' and x['transformation']=='level'
  assert abs(float(x['value'])-3.13682671641221)<1e-12 and u['normalization']=='none'
  assert u['upstream_cube']=='amarbma' and u['upstream_series_label']=='Jobless rate - Seasonally adjusted'
 return {'dimension':dim,'value':x['value'],'series_id':x['series_id'],'macro_series_id':x['macro_series_id'],'fixture_contract':'PASS'}
def main():
 before={str(p):h(p) for p in LIVE}
 with tempfile.TemporaryDirectory(prefix='gmfq-chf-snb-') as td:r=[check('inflation',Path(td)),check('labour',Path(td))]
 assert before=={str(p):h(p) for p in LIVE}
 print(json.dumps({'status':'PASS','source':'SNB official API','scope':'deterministic adapter/parser contract; canonical builder compatibility is verified separately with current live SNB candidates in the workflow','results':r,'live_data_modified':False},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
