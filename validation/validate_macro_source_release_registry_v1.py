#!/usr/bin/env python3
from __future__ import annotations
import json, pathlib

ROOT=pathlib.Path(__file__).resolve().parents[1]
P=ROOT/'validation'/'MACRO_SOURCE_RELEASE_REGISTRY_V1_2026-10-07.json'
G8={'USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'}
DIMS={'inflation','labour'}

def main()->int:
    x=json.loads(P.read_text(encoding='utf-8'))
    fail=[]
    if x.get('schema')!='GMFQ_MACRO_SOURCE_RELEASE_REGISTRY_V1': fail.append('schema mismatch')
    rows=x.get('series') or []
    if len(rows)!=16: fail.append(f'expected 16 core series, got {len(rows)}')
    keys=[(r.get('currency'),r.get('dimension')) for r in rows]
    if len(keys)!=len(set(keys)): fail.append('duplicate currency/dimension entries')
    if {c for c,_ in keys}!=G8: fail.append('G8 currency set mismatch')
    if {d for _,d in keys}!=DIMS: fail.append('dimension set mismatch')
    for r in rows:
        tag=f"{r.get('currency')}/{r.get('dimension')}"
        for k in ('series_id','source','frequency','transformation','runtime_as_of'):
            if r.get(k) in (None,''): fail.append(f'{tag}: missing {k}')
        pit=r.get('historical_pit') or {}
        daily=r.get('daily_ingress') or {}
        if pit.get('counts_as_live_collector') is not False:
            fail.append(f'{tag}: historical PIT incorrectly counted as live collector')
        req=[r.get('runtime_valid') is True,
             daily.get('live_release_collector_present') is True,
             daily.get('freshness_rule_present') is True,
             daily.get('first_release_policy_present') is True,
             daily.get('candidate_builder_present') is True,
             daily.get('provenance_apply_gate_present') is True]
        if r.get('status')=='DAILY_READY' and not all(req):
            fail.append(f'{tag}: DAILY_READY without all readiness requirements')
        if r.get('status')!='DAILY_READY' and all(req):
            fail.append(f'{tag}: all readiness requirements true but not DAILY_READY')
    s=x.get('summary') or {}
    if s.get('core_series')!=16: fail.append('summary core_series mismatch')
    if s.get('daily_ready')!=sum(r.get('status')=='DAILY_READY' for r in rows): fail.append('summary daily_ready mismatch')
    contract=x.get('readiness_contract') or {}
    if contract.get('historical_pit_script_is_not_live_collector') is not True: fail.append('PIT/live collector separation missing')
    guards=x.get('guards') or {}
    for k in ('changes_engine_rules','changes_live_data','changes_oos_baseline','production_promotion','predictive_claim','schedule_enabled'):
        if guards.get(k) is not False: fail.append(f'guard {k} must be false')
    status='PASS' if not fail else 'FAIL'
    print(json.dumps({'status':status,'failures':fail,'summary':s},indent=2))
    return 0 if not fail else 2

if __name__=='__main__': raise SystemExit(main())
