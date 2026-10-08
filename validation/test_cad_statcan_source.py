#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ADAPTER=ROOT/'validation/sources/cad_statcan_core.py'
BUILDER=ROOT/'validation/build_macro_candidate.py'
FIX={'inflation':ROOT/'validation/fixtures/cad_statcan_cpi_contract.csv','labour':ROOT/'validation/fixtures/cad_statcan_unemployment_contract.csv'}
LIVE=[ROOT/'live_data/sections/MACRO_SERIES.json',ROOT/'live_data/sections/MACRO_THERMOMETER_DATA.json']
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(*a):subprocess.run([sys.executable,*a],cwd=ROOT,check=True)
def check(dim,root):
 c=root/f'{dim}-candidate.json';a=root/f'{dim}-audit.json';b=root/f'{dim}-built'
 run(str(ADAPTER),'--dimension',dim,'--fixture',str(FIX[dim]),'--output',str(c),'--audit-output',str(a))
 cj=json.loads(c.read_text());aj=json.loads(a.read_text())
 assert cj['currency']=='CAD' and cj['dimension']==dim and cj['source']=='Statistics Canada',cj
 assert cj['frequency']=='M' and cj['macro_series_id'],cj
 assert aj['candidate_only'] is True and aj['live_data_written'] is False and aj['mode']=='fixture',aj
 if dim=='inflation':
  assert cj['transformation']=='reported_yoy_rate',cj
  assert cj['observation_date']=='2026-08-01' and abs(float(cj['value'])-2.9)<1e-12,cj
 else:
  assert cj['transformation']=='level',cj
  assert cj['observation_date']=='2026-08-01' and abs(float(cj['value'])-7.0)<1e-12,cj
 run(str(BUILDER),'--candidate',str(c),'--output-dir',str(b))
 s=json.loads((b/'summary.json').read_text());assert s['status']=='PASS' and s['live_data_modified'] is False,s
 assert s['currency']=='CAD' and s['dimension']==dim,s
 return {'dimension':dim,'series_id':cj['series_id'],'macro_series_id':cj['macro_series_id'],'observation_date':cj['observation_date'],'value':cj['value']}
def main():
 before={str(p):digest(p) for p in LIVE}
 with tempfile.TemporaryDirectory(prefix='gmfq-cad-statcan-') as td:
  r=[check('inflation',Path(td)),check('labour',Path(td))]
 after={str(p):digest(p) for p in LIVE};assert before==after,(before,after)
 print(json.dumps({'status':'PASS','source':'Statistics Canada','results':r,'live_data_modified':False},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
