#!/usr/bin/env python3
import datetime as dt
import json
import re
from pathlib import Path

REGISTRY = Path('validation/FRESHNESS_REGISTRY_V1_2026-10-12.json')
D_PATH = Path('live_data/sections/D.json')
PRICE_RUNTIME = Path('payload/part-15.txt')
RATES_META = Path('live_data/sections/RATES_AUDIT_METADATA.json')
MACRO_REGISTRY = Path('validation/macro/MACRO_SOURCE_REGISTRY_2026-10-08.json')
LIQ_PATH = Path('live_data/sections/NATIVE_LIQ_DATA.json')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def parse_date(value):
    return dt.date.fromisoformat(value) if value else None


def price_overlay_as_of():
    text = PRICE_RUNTIME.read_text(encoding='utf-8')
    m = re.findall(r'<script id="gmfq-price-ecb-(\d{8})">', text)
    if len(m) != 1:
        raise SystemExit(f'expected exactly one ECB Price runtime overlay, got {len(m)}')
    return f'{m[0][0:4]}-{m[0][4:6]}-{m[0][6:8]}'


def main():
    reg = load(REGISTRY)
    d = load(D_PATH)
    rates = load(RATES_META)
    macro = load(MACRO_REGISTRY)
    today = parse_date(reg['as_of'])

    pairs = d.get('pairs', [])
    pair_dates = sorted({p.get('price_asof') for p in pairs if p.get('price_asof')})
    latest_pair = max(pair_dates) if pair_dates else None
    overlay_as_of = price_overlay_as_of()
    price_age = (today - parse_date(overlay_as_of)).days

    lanes = {
        'PRICE': {
            'state': 'BLOCKED_STALE_APPLY_NOT_WIRED',
            'runtime_overlay_as_of': overlay_as_of,
            'embedded_pair_as_of': latest_pair,
            'age_days': price_age,
            'updater': 'fetch_ecb_g8_price_candidate.py + apply_ecb_g8_price_candidate.py',
            'candidate_pipeline_ready': True,
            'publication_eligible': False,
            'reason': 'official ECB fetch and deterministic payload apply are available; controlled persistent apply is not yet wired',
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
            'state': 'PIT_CONTRACT_READY_RUNTIME_REPAIR_PROVEN',
            'schema': macro.get('schema'),
            'updater': 'macro-single-series-pit-refresh-v1.yml',
            'publication_eligible': False,
            'reason': 'single-series PIT path exists; detached runtime repair is deterministic but persistent apply is not yet wired',
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

    if overlay_as_of > reg['as_of']:
        raise SystemExit('price runtime overlay has future observation relative to registry')
    if len(pairs) != 28:
        raise SystemExit(f'expected 28 FX pairs, got {len(pairs)}')
    if receipt['status'] == 'READY_FOR_CONTROLLED_APPLY':
        raise SystemExit('unexpected ready state: V1 still has known missing updaters/apply gates')

    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
