#!/usr/bin/env python3
from __future__ import annotations
import json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXPECTED={1:(13,13),2:(14,12),3:(15,11),4:(16,10),5:(17,9),6:(18,8),7:(19,7),8:(20,6),9:(21,5),10:(22,4),11:(23,3)}

def run_json(path:Path):
 p=subprocess.run([sys.executable,str(path)],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 if p.returncode:
  raise SystemExit(f'{path.name} failed\n{p.stdout}')
 try:return json.loads(p.stdout)
 except Exception as e: raise SystemExit(f'{path.name} returned invalid JSON: {e}\n{p.stdout}')

def assert_no_publish(d,label):
 for k in ('promotion_performed','live_data_published','gh_pages_published','automatic_publication','publication_performed','runtime_mutated'):
  if k in d and d[k] not in (False,None): raise SystemExit(f'{label}: unsafe {k}={d[k]!r}')

def main():
 general=run_json(ROOT/'validation/run_daily_data_orchestrator_v1.py')
 if general.get('schema')!='GMFQ_DAILY_DATA_ORCHESTRATOR_RECEIPT_V1': raise SystemExit('General schema drift')
 if general.get('status')!='BLOCKED_EXPECTED_GAPS_NO_PUBLICATION': raise SystemExit(f'General status drift: {general.get("status")}')
 gl=general['lanes']['LIQUIDITY']
 if (gl.get('automation_ready_subseries'),gl.get('mapping_pending_subseries'),gl.get('total_subseries'))!=(10,16,26): raise SystemExit(f'General liquidity base drift: {gl}')
 assert_no_publish(general,'General')

 chain=[]
 prev=(10,16)
 final=None
 for n,(ready,pending) in EXPECTED.items():
  d=run_json(ROOT/f'validation/run_daily_data_orchestrator_effective_v{n}.py')
  liq=d['lanes']['LIQUIDITY']
  got=(liq.get('automation_ready_subseries'),liq.get('mapping_pending_subseries'))
  if got!=(ready,pending): raise SystemExit(f'V{n} coverage drift: {got} != {(ready,pending)}')
  if liq.get('verified_subseries')!=ready or liq.get('unresolved_subseries')!=pending or liq.get('total_subseries')!=26: raise SystemExit(f'V{n} accounting drift: {liq}')
  if ready!=prev[0]+(3 if n==1 else 1) or pending!=prev[1]-(3 if n==1 else 1): raise SystemExit(f'V{n} expected monotonic delta broken')
  overlays=[(k,v) for k,v in d.items() if k.startswith('effective_liquidity_overlay') and isinstance(v,dict)]
  if not overlays: raise SystemExit(f'V{n} overlay missing')
  latest=max(overlays,key=lambda kv: int(kv[0].rsplit('v',1)[-1]) if kv[0].rsplit('v',1)[-1].isdigit() else 1)[1]
  if latest.get('ready')!=ready or latest.get('pending')!=pending or latest.get('total')!=26: raise SystemExit(f'V{n} latest overlay drift: {latest}')
  if latest.get('runtime_mutated') is not False or latest.get('publication_performed') is not False: raise SystemExit(f'V{n} unsafe overlay: {latest}')
  assert_no_publish(d,f'V{n}')
  chain.append({'version':n,'ready':ready,'pending':pending,'total':26,'status':'PASS'})
  prev=(ready,pending); final=d

 o11=final.get('effective_liquidity_overlay_v11') or {}
 if o11.get('remaining_fail_closed')!=['CHF.liquidity','CHF.credit','JPY.liquidity']:
  raise SystemExit(f'V11 remaining blockers drift: {o11}')
 out={
  'schema':'GMFQ_DAILY_DATA_ORCHESTRATOR_LIQUIDITY_CHAIN_CERTIFICATION_V1',
  'head_sha':os.environ.get('GITHUB_SHA'),
  'general':{'status':'PASS','base_ready':10,'base_pending':16,'total':26},
  'chain':chain,
  'final':{'ready':23,'pending':3,'total':26,'remaining_fail_closed':['CHF.liquidity','CHF.credit','JPY.liquidity']},
  'runtime_mutated':False,
  'publication_performed':False,
 }
 print(json.dumps(out,indent=2))
if __name__=='__main__': main()
