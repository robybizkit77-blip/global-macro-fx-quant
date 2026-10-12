#!/usr/bin/env python3
import datetime as dt
import json
from pathlib import Path

REGISTRY = Path('validation/FRESHNESS_REGISTRY_V1_2026-10-12.json')
D_PATH = Path('live_data/sections/D.json')
RATES_META = Path('live_data/sections/RATES_AUDIT_METADATA.json')
MACRO_REGISTRY = Path('validation/macro/MACRO_SOURCE_REGISTRY_2026-10-08.json')
LIQ_PATH = Path('live_data/sections/NATIVE_LIQ_DATA.json')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def parse_date(value):
    return dt.date.fromisoformat(value) if value else None


def main():
    reg = load(REGISTRY)
    d = load(D_PATH)
    rates = load(RATES_META)
    macro = load(MACRO_REGISTRY)
    today = parse_date(reg['as_of'])

    pairs = d.get('pairs', [])
    pair_dates = sorted({p.get('price_asof') for p in pairs if p.get('price_asof')})
    latest_pair = max(pair_dates) if pair_dates else None
    price_age = (today - parse_date(latest_pair)).days if latest_pair else None

    lanes = {
        'PRICE': {
            'state': 'BLOCKED_STALE_NO_UPDATER',
            'runtime_as_of': d.get('asOf'),
            'latest_pair_as_of': latest_pair,
            'age_days': price_age,
            'updater': 'MISSING_DEDICATED_WORKFLOW',
            'publication_eligible': False,
        },
        'RATES': {
            'state': 'OBSERVATION_PIPELINE_READY',
            'audit_date': rates.get('audit_date'),
            'withheld': (rates.get('audit_summary') or {}).get('withheld', []),
            'updater': 'rates-daily-operational.yml',
            'publication_eligible': False,
            'reason': 'candidate/dry-run exists; controlled apply not yet wired',
        },
        'MACRO': {
            'state': 'PIT_CONTRACT_READY_ORCHESTRATION_MISSING',
            'schema': macro.get('schema'),
            'updater': 'macro-single-series-pit-refresh-v1.yml',
            'publication_eligible': False,
            'reason': 'single-series PIT path exists; no general scheduled adapter orchestration yet',
        },
        'LIQUIDITY': {
            'state': 'BLOCKED_UPDATER_UNVERIFIED',
            'source_present': LIQ_PATH.exists(),
            'updater': 'UNVERIFIED',
            'publication_eligible': False,
        },
        'RISK': {
            'state': 'BLOCKED_UPDATER_UNVERIFIED',
            'updater': 'UNVERIFIED',
            'publication_eligible': False,
        },
        'REBUILD': {
            'state': 'READY_AFTER_INPUT_GATES',
            'validator': 'check_live_update_contract.py + rebuild_live_data_runtime.py --verify-only',
            'publication_eligible': False,
        },
    }

    blocking = [name for name, x in lanes.items() if x['state'].startswith('BLOCKED_')]
    receipt = {
        'schema': 'GMFQ_DAILY_DATA_ORCHESTRATOR_RECEIPT_V1',
        'registry_as_of': reg['as_of'],
        'status': 'BLOCKED_EXPECTED_GAPS_NO_PUBLICATION' if blocking else 'READY_FOR_CONTROLLED_APPLY',
        'blocking_lanes': blocking,
        'lanes': lanes,
        'promotion_performed': False,
        'live_data_published': False,
        'gh_pages_published': False,
        'automatic_publication': False,
    }

    if latest_pair and latest_pair > reg['as_of']:
        raise SystemExit('price runtime has future observation relative to registry')
    if len(pairs) != 28:
        raise SystemExit(f'expected 28 FX pairs, got {len(pairs)}')
    if receipt['status'] == 'READY_FOR_CONTROLLED_APPLY':
        raise SystemExit('unexpected ready state: V1 still has known missing updaters')

    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
