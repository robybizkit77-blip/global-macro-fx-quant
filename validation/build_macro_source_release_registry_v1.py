#!/usr/bin/env python3
from __future__ import annotations
import json, pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
HEATMAP = ROOT/'live_data'/'sections'/'MACRO_THERMOMETER_DATA.json'
OUT = ROOT/'validation'/'MACRO_SOURCE_RELEASE_REGISTRY_V1_2026-10-07.json'
G8 = ['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']
DIMS = ['inflation','labour']

# IMPORTANT: these are historical/research PIT assets, not live collectors.
PIT_EVIDENCE = {
    ('AUD','inflation'): ('PASS_RESEARCH_PIT', 'validation/AUD_CPI_PIT_V1_2026-10-07.json'),
    ('AUD','labour'): ('PASS_RESEARCH_PIT', 'validation/AUD_UNEMPLOYMENT_PIT_V1_2026-10-07.json'),
    ('CHF','labour'): ('WITHHELD_SOURCE_ACCESS_GAP', 'validation/CHF_SECO_UNEMPLOYMENT_ACCESS_GAP_V1_2026-10-07.json'),
    ('NZD','inflation'): ('WITHHELD_SOURCE_ACCESS_GAP', None),
    ('NZD','labour'): ('WITHHELD_SOURCE_ACCESS_GAP', None),
}


def runtime_valid(row: dict) -> bool:
    v = row.get('validation') or {}
    return all(v.get(k) is True for k in ('source','history','latest','transformation')) and all(
        row.get(k) not in (None,'') for k in ('series_id','source','frequency','transformation','as_of')
    )


def main() -> int:
    h = json.loads(HEATMAP.read_text(encoding='utf-8'))
    currencies = h.get('currencies') or {}
    rows=[]
    for ccy in G8:
        block = currencies.get(ccy) or {}
        for dim in DIMS:
            src = block.get(dim) or {}
            pit_status, pit_artifact = PIT_EVIDENCE.get((ccy,dim), ('NOT_FORMALIZED_FOR_DAILY_INGRESS', None))
            collector_present = False  # no certified live release adapter has been registered yet
            freshness_rule_present = False
            first_release_policy = pit_status == 'PASS_RESEARCH_PIT'
            candidate_builder_present = (ROOT/'validation'/'build_macro_candidate.py').exists()
            provenance_apply_gate_present = False
            ready = all((runtime_valid(src), collector_present, freshness_rule_present,
                         first_release_policy, candidate_builder_present, provenance_apply_gate_present))
            status = 'DAILY_READY' if ready else ('WITHHELD_SOURCE_ACCESS_GAP' if pit_status=='WITHHELD_SOURCE_ACCESS_GAP' else 'SOURCE_ADAPTER_REQUIRED')
            rows.append({
                'currency': ccy,
                'dimension': dim,
                'series_id': src.get('series_id'),
                'source': src.get('source'),
                'frequency': src.get('frequency'),
                'transformation': src.get('transformation'),
                'runtime_as_of': src.get('as_of'),
                'runtime_valid': runtime_valid(src),
                'historical_pit': {
                    'status': pit_status,
                    'artifact': pit_artifact,
                    'counts_as_live_collector': False,
                },
                'daily_ingress': {
                    'live_release_collector_present': collector_present,
                    'freshness_rule_present': freshness_rule_present,
                    'first_release_policy_present': first_release_policy,
                    'candidate_builder_present': candidate_builder_present,
                    'provenance_apply_gate_present': provenance_apply_gate_present,
                },
                'status': status,
            })
    summary = {
        'core_series': len(rows),
        'runtime_valid': sum(r['runtime_valid'] for r in rows),
        'live_collectors': sum(r['daily_ingress']['live_release_collector_present'] for r in rows),
        'daily_ready': sum(r['status']=='DAILY_READY' for r in rows),
        'source_adapter_required': sum(r['status']=='SOURCE_ADAPTER_REQUIRED' for r in rows),
        'withheld_source_access_gap': sum(r['status']=='WITHHELD_SOURCE_ACCESS_GAP' for r in rows),
    }
    out={
        'schema':'GMFQ_MACRO_SOURCE_RELEASE_REGISTRY_V1',
        'created_at_utc': datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        'status':'RESEARCH_ONLY_UPSTREAM_INGRESS_NOT_DAILY_READY',
        'scope':'G8 core macro release ingestion: inflation + labour only',
        'source_of_runtime_metadata':'live_data/sections/MACRO_THERMOMETER_DATA.json',
        'candidate_builder':'validation/build_macro_candidate.py',
        'readiness_contract':{
            'daily_ready_requires':['runtime_valid','live_release_collector_present','freshness_rule_present','first_release_policy_present','candidate_builder_present','provenance_apply_gate_present'],
            'historical_pit_script_is_not_live_collector': True,
            'runtime_value_does_not_imply_ingress_readiness': True,
            'missing_is_not_neutral': True,
        },
        'summary':summary,
        'series':rows,
        'guards':{
            'changes_engine_rules':False,
            'changes_live_data':False,
            'changes_oos_baseline':False,
            'production_promotion':False,
            'predictive_claim':False,
            'schedule_enabled':False,
        }
    }
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','output':str(OUT.relative_to(ROOT)),'summary':summary},indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
