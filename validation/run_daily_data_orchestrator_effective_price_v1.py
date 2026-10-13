#!/usr/bin/env python3
from __future__ import annotations
import json,subprocess,sys
from pathlib import Path

BASE=Path('validation/run_daily_data_orchestrator_effective_v11.py')
PROOF=Path('validation/price/PRICE_ECB_CONTROLLED_APPLY_CONTRACT_V1_2026-10-13.json')

def main():
    p=subprocess.run([sys.executable,str(BASE)],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    if p.returncode:
        raise SystemExit(p.stdout)
    d=json.loads(p.stdout)
    proof=json.loads(PROOF.read_text(encoding='utf-8'))
    if proof.get('schema')!='GMFQ_PRICE_ECB_CONTROLLED_APPLY_CONTRACT_V1':
        raise SystemExit('invalid Price controlled-apply proof schema')
    if proof.get('controlled_apply_proven') is not True or proof.get('automation_ready') is not True:
        raise SystemExit('Price controlled apply is not proven')
    if proof.get('persistent_publication_enabled') is not False:
        raise SystemExit('Price persistent publication must remain explicitly withheld')
    if proof.get('runtime_mutated') is not False or proof.get('publication_performed') is not False:
        raise SystemExit('Price proof must not mutate tracked runtime or publish')
    pr=proof.get('proof') or {}
    if pr.get('exact_diff_scope')!=['payload/part-15.txt'] or pr.get('idempotent_second_apply') is not True:
        raise SystemExit('Price controlled-apply proof scope/idempotence drifted')
    if pr.get('candidate_as_of')!='2026-10-13':
        raise SystemExit('Price proof candidate date drifted')

    price=d['lanes']['PRICE']
    price.update({
        'state':'CONTROLLED_APPLY_PROVEN_PUBLICATION_WITHHELD',
        'controlled_apply_proven':True,
        'controlled_apply_contract':str(PROOF),
        'controlled_apply_workflow':pr['workflow'],
        'controlled_apply_run_id':pr['run_id'],
        'controlled_apply_target':'payload/part-15.txt',
        'exact_diff_scope':['payload/part-15.txt'],
        'idempotent_apply_proven':True,
        'automation_ready':True,
        'persistent_publication_enabled':False,
        'publication_eligible':False,
        'reason':'Official ECB fetch plus deterministic one-file controlled apply are proven and idempotent. Persistent publication remains explicitly withheld pending a separately authorized write workflow.'
    })
    d['blocking_lanes']=[name for name,x in d['lanes'].items() if x['state'].startswith('BLOCKED_')]
    d['status']='BLOCKED_EXPECTED_GAPS_NO_PUBLICATION' if d['blocking_lanes'] else 'READY_FOR_CONTROLLED_APPLY'
    d['effective_price_overlay_v1']={
        'schema':'GMFQ_DAILY_DATA_ORCHESTRATOR_EFFECTIVE_PRICE_OVERLAY_V1',
        'version':'2026-10-13-ecb-price-controlled-apply-proven',
        'price_controlled_apply_proven':True,
        'price_persistent_publication_enabled':False,
        'remaining_blocking_lanes':d['blocking_lanes'],
        'liquidity_ready':d['lanes']['LIQUIDITY']['automation_ready_subseries'],
        'liquidity_pending':d['lanes']['LIQUIDITY']['mapping_pending_subseries'],
        'runtime_mutated':False,
        'publication_performed':False
    }
    print(json.dumps(d,indent=2,ensure_ascii=False))

if __name__=='__main__':
    main()
