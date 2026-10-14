#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('logger',HERE/'forward/log_core_decision_v1.py')
logger=importlib.util.module_from_spec(spec); spec.loader.exec_module(logger)

def check(condition, message):
    if not condition: raise AssertionError(message)

def main():
    original=logger.DECISIONS
    test_store=HERE/'forward'/'.test_CORE_DECISION_SNAPSHOTS_V1.jsonl'
    if test_store.exists(): test_store.unlink()
    try:
        logger.DECISIONS=test_store
        rows=logger.make_rows(logger.parse_cutoff('2026-10-14T23:59:59+02:00'),'smoke-20261014')
        check(len(rows)==28,'exactly 28 canonical pair snapshots required')
        forbidden={'forward_returns','outcome','gross_return','net_return','cost_bps'}
        check(all(not (forbidden & set(r)) for r in rows),'decision rows must contain no forward outcome')
        check(all(r['snapshot_sha256']==logger.digest({k:v for k,v in r.items() if k!='snapshot_sha256'}) for r in rows),'snapshot hash must be byte stable')
        first=logger.append_rows(rows,False); second=logger.append_rows(rows,False)
        check(first['written']==28 and second['written']==0 and second['duplicates_skipped']==28,'rerun must be idempotent')
        saved=[json.loads(x) for x in logger.DECISIONS.read_text(encoding='utf-8').splitlines()]
        check(len(saved)==28,'append-only store must retain exact initial batch')
        check(all(v in (True,False) for r in saved for v in r['withheld_flags'].values()),'WITHHELD flags are explicit')
    finally:
        if test_store.exists(): test_store.unlink()
        logger.DECISIONS=original
    print(json.dumps({'status':'PASS','tests':['byte_stability','idempotence','pit_withhold','no_forward_outcomes']}))

if __name__=='__main__': main()
