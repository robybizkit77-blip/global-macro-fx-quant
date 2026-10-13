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
LIQ_POLICY = Path('validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json')
RISK_POLICY = Path('validation/risk/RISK_SOURCE_POLICY_V1_2026-10-12.json')


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
    liq_policy = load(LIQ_POLICY)
    risk_policy = load(RISK_POLICY)
    today = parse_date(reg['as_of'])

    pairs = d.get('pairs', [])
    pair_dates = sorted({p.get('price_asof') for p in pairs if p.get('price_asof')})
    latest_pair = max(pair_dates) if pair_dates else None
    overlay_as_of = price_overlay_as_of()
    price_age = (today - parse_date(overlay_as_of)).days

    if liq_policy.get('status') != 'PARTIAL_POLICY_FAIL_CLOSED':
        raise SystemExit('Liquidity source policy must remain fail-closed until all subseries are exact-mapped and automation-ready')
    liq_mapped = liq_policy.get('mapped') or {}
    liq_unresolved = liq_policy.get('unresolved') or []
    liq_cov = liq_policy.get('coverage') or {}
    liq_total = int(liq_cov.get('total_subseries', 0))
    liq_source_mapped = int(liq_cov.get('source_mapped_subseries', -1))
    liq_ready = int(liq_cov.get('automation_ready_subseries', -1))
    liq_pending = int(liq_cov.get('mapping_pending_subseries', -1))
    liq_unresolved_count = int(liq_cov.get('unresolved_subseries', -1))
    if liq_total != 26:
        raise SystemExit(f'Liquidity total coverage mismatch: {liq_total}')
    if len(liq_mapped) != liq_source_mapped or len(liq_unresolved) != liq_unresolved_count:
        raise SystemExit('Liquidity policy declared counts do not match mapped/unresolved objects')
    if liq_source_mapped + liq_unresolved_count != liq_total:
        raise SystemExit('Liquidity source-mapped + unresolved coverage must equal total')
    if liq_ready + liq_pending != liq_source_mapped:
        raise SystemExit('Liquidity automation-ready + mapping-pending must equal source-mapped')
    actual_ready = sum(1 for row in liq_mapped.values() if row.get('automation_ready') is True)
    if actual_ready != liq_ready:
        raise SystemExit(f'Liquidity automation-ready count mismatch: declared={liq_ready} actual={actual_ready}')

    vix_policy = risk_policy['gate_inputs']['VIX']
    brent_policy = risk_policy['gate_inputs']['Brent']
    if vix_policy['status'] != 'READY':
        raise SystemExit('Risk VIX source must be READY')
    if brent_policy['status'] != 'WITHHELD_OFFICIAL_SOURCE_TOO_SLOW_FOR_GATE':
        raise SystemExit('Risk Brent must remain fail-closed while official source lag exceeds the gate')

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
            'state': 'BLOCKED_SUBSERIES_EXACT_MAPPING_INCOMPLETE',
            'source_present': LIQ_PATH.exists(),
            'source_policy': str(LIQ_POLICY),
            'updater': 'UNVERIFIED',
            'inventory': 'audit_liquidity_subseries_v1.py',
            'inventory_ready': True,
            'source_mapped_subseries': liq_source_mapped,
            'automation_ready_subseries': liq_ready,
            'mapping_pending_subseries': liq_pending,
            'unresolved_subseries': liq_unresolved_count,
            'total_subseries': liq_total,
            'publication_eligible': False,
            'reason': 'official source families are mostly mapped, but provider discovery is not equivalent to an exact automation-ready series; exact variant/key and aggregation matching remain fail-closed',
        },
        'RISK': {
            'state': 'BLOCKED_BRENT_OFFICIAL_SOURCE_TOO_SLOW_FOR_GATE',
            'source_policy': str(RISK_POLICY),
            'vix_source_status': vix_policy['status'],
            'vix_updater': vix_policy['collector'],
            'vix_candidate_pipeline_ready': True,
            'brent_source_status': brent_policy['status'],
            'brent_updater': brent_policy['collector'],
            'brent_series_id': brent_policy.get('series_id'),
            'freshness_guard': 'Risk Freshness Audit V1 / GMFQ_RISK_FRESHNESS_GATE_SIM_V1',
            'guard_rule': 'VIX or Brent > 1 business day behind Price => WITHHELD; pair structural direction unchanged',
            'guard_proven': True,
            'publication_eligible': False,
            'reason': 'VIX is auditable and candidate-ready. Brent has an auditable primary EIA daily source, but that source can lag beyond the existing one-business-day gate; no proxy substitution and no gate weakening are allowed.',
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
