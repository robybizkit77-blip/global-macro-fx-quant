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
LIQ_POLICY_OVERRIDE = Path('validation/liquidity/LIQUIDITY_POLICY_OVERRIDE_EUR_M3_V1_2026-10-13.json')
EUR_EXCESS_COLLECTOR = Path('validation/fetch_ecb_eur_excess_liquidity_candidate.py')
USD_M2_COLLECTOR = Path('validation/fetch_fed_usd_m2_candidate.py')
GBP_BOE_COLLECTOR = Path('validation/fetch_boe_gbp_liquidity_candidates.py')
JPY_CREDIT_COLLECTOR = Path('validation/fetch_boj_jpy_bank_credit_candidate.py')
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
    liq_override = load(LIQ_POLICY_OVERRIDE)
    risk_policy = load(RISK_POLICY)
    today = parse_date(reg['as_of'])

    pairs = d.get('pairs', [])
    pair_dates = sorted({p.get('price_asof') for p in pairs if p.get('price_asof')})
    latest_pair = max(pair_dates) if pair_dates else None
    overlay_as_of = price_overlay_as_of()
    price_age = (today - parse_date(overlay_as_of)).days

    if liq_policy.get('status') != 'PARTIAL_POLICY_FAIL_CLOSED':
        raise SystemExit('Liquidity source policy must remain fail-closed until all subseries are exact-mapped and automation-ready')
    if liq_override.get('schema') != 'GMFQ_LIQUIDITY_POLICY_OVERRIDE_V1':
        raise SystemExit('Liquidity EUR M3 override schema mismatch')
    supersedes = liq_override.get('supersedes') or {}
    if supersedes.get('policy') != str(LIQ_POLICY) or supersedes.get('subseries') != 'EUR.money':
        raise SystemExit('Liquidity EUR M3 override does not target the expected base policy/subseries')
    effective_m3 = liq_override.get('effective_row') or {}
    if effective_m3.get('automation_ready') is not False:
        raise SystemExit('EUR.money must remain fail-closed until revision/vintage handling is explicit')
    if effective_m3.get('series_key') != 'BSI.M.U2.Y.V.M30.X.1.U2.2300.Z01.E':
        raise SystemExit('EUR.money effective series key must be the proven adjusted ECB M3 series')
    if effective_m3.get('collector_status') != 'WITHHELD_UNTIL_REVISION_AWARE_CONTRACT':
        raise SystemExit('EUR.money collector must remain withheld pending revision-aware contract')

    base_mapped = liq_policy.get('mapped') or {}
    liq_mapped = dict(base_mapped)
    liq_mapped['EUR.money'] = effective_m3
    liq_unresolved = liq_policy.get('unresolved') or []
    liq_cov = liq_policy.get('coverage') or {}
    liq_total = int(liq_cov.get('total_subseries', 0))
    liq_source_mapped = int(liq_cov.get('source_mapped_subseries', -1))
    liq_source_unresolved = int(liq_cov.get('unresolved_subseries', -1))
    liq_ready = sum(1 for row in liq_mapped.values() if row.get('automation_ready') is True)
    liq_pending = liq_source_mapped - liq_ready
    coverage_delta = liq_override.get('coverage_delta') or {}
    expected_ready = int(liq_cov.get('automation_ready_subseries', -1)) + int(coverage_delta.get('automation_ready_subseries', 0))
    expected_pending = int(liq_cov.get('mapping_pending_subseries', -1)) + int(coverage_delta.get('mapping_pending_subseries', 0))

    if liq_total != 26:
        raise SystemExit(f'Liquidity total coverage mismatch: {liq_total}')
    if len(liq_mapped) != liq_source_mapped or len(liq_unresolved) != liq_source_unresolved:
        raise SystemExit('Liquidity policy declared counts do not match effective mapped/unresolved objects')
    if liq_source_mapped + liq_source_unresolved != liq_total:
        raise SystemExit('Liquidity source-mapped + source-unresolved coverage must equal total')
    if liq_ready + liq_pending != liq_source_mapped:
        raise SystemExit('Liquidity automation-ready + mapping-pending must equal source-mapped')
    if liq_ready != expected_ready or liq_pending != expected_pending:
        raise SystemExit(
            f'Liquidity effective coverage mismatch after override: ready={liq_ready}/{expected_ready}, '
            f'pending={liq_pending}/{expected_pending}'
        )

    cad_m2pp = liq_mapped.get('CAD.money') or {}
    if cad_m2pp.get('candidate_pipeline_ready') is not True:
        raise SystemExit('CAD.money candidate collector must be live-tested before orchestrator marks candidate readiness')

    eur_excess = liq_mapped.get('EUR.liquidity') or {}
    if eur_excess.get('series_key') != 'ILM.D.U2.C.EXLIQ.U2.EUR' or eur_excess.get('automation_ready') is not True:
        raise SystemExit('EUR.liquidity source contract must remain exact and automation-ready')
    if not EUR_EXCESS_COLLECTOR.exists():
        raise SystemExit('EUR.liquidity candidate collector is missing')

    usd_m2 = liq_mapped.get('USD.liquidity') or {}
    if usd_m2.get('series_key') != 'H6/H6_M2/M2.M' or usd_m2.get('series_mapping_status') != 'EXACT_SERIES_KEY_RUNTIME_MATCH_CONFIRMED':
        raise SystemExit('USD.liquidity must retain the exact Fed H.6 M2 mapping')
    if not USD_M2_COLLECTOR.exists():
        raise SystemExit('USD.liquidity Fed H.6 candidate collector is missing')

    gbp_reserves = liq_mapped.get('GBP.liquidity') or {}
    gbp_credit = liq_mapped.get('GBP.credit') or {}
    if gbp_reserves.get('series_key') != 'RPWB56A' or gbp_reserves.get('series_mapping_status') != 'EXACT_SERIES_KEY_RUNTIME_MATCH_CONFIRMED':
        raise SystemExit('GBP.liquidity must retain exact BoE RPWB56A mapping')
    if gbp_credit.get('series_key') != 'LPMVTYI' or gbp_credit.get('series_mapping_status') != 'EXACT_SERIES_KEY_RUNTIME_MATCH_CONFIRMED':
        raise SystemExit('GBP.credit must retain exact BoE LPMVTYI mapping')
    if not GBP_BOE_COLLECTOR.exists():
        raise SystemExit('GBP BoE candidate collector is missing')

    jpy_credit = liq_mapped.get('JPY.credit') or {}
    if jpy_credit.get('candidate_pipeline_ready') is not True:
        raise SystemExit('JPY.credit candidate collector must be live-tested before orchestrator marks candidate readiness')
    if jpy_credit.get('database') != 'MD11' or jpy_credit.get('series_key') != 'DLCLAEDBLTTO':
        raise SystemExit('JPY.credit must retain exact BOJ MD11 / DLCLAEDBLTTO mapping')
    if jpy_credit.get('series_mapping_status') != 'EXACT_SERIES_KEY_RUNTIME_MATCH_CONFIRMED':
        raise SystemExit('JPY.credit runtime/source mapping must remain exact')
    if not JPY_CREDIT_COLLECTOR.exists():
        raise SystemExit('JPY.credit BOJ candidate collector is missing')

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
            'state': 'BLOCKED_SUBSERIES_POLICY_PARTIAL',
            'source_present': LIQ_PATH.exists(),
            'source_policy': str(LIQ_POLICY),
            'source_policy_override': str(LIQ_POLICY_OVERRIDE),
            'updater': 'PARTIAL_CANDIDATE_PIPELINES_ONLY',
            'inventory': 'audit_liquidity_subseries_v1.py',
            'inventory_ready': True,
            'verified_subseries': liq_ready,
            'unresolved_subseries': liq_total - liq_ready,
            'source_mapped_subseries': liq_source_mapped,
            'automation_ready_subseries': liq_ready,
            'mapping_pending_subseries': liq_pending,
            'source_unresolved_subseries': liq_source_unresolved,
            'total_subseries': liq_total,
            'cad_m2pp_candidate_pipeline_ready': True,
            'cad_m2pp_collector': cad_m2pp.get('collector'),
            'eur_excess_candidate_pipeline_ready': True,
            'eur_excess_collector': str(EUR_EXCESS_COLLECTOR),
            'usd_m2_candidate_pipeline_ready': True,
            'usd_m2_collector': str(USD_M2_COLLECTOR),
            'gbp_reserves_candidate_pipeline_ready': True,
            'gbp_credit_candidate_pipeline_ready': True,
            'gbp_boe_collector': str(GBP_BOE_COLLECTOR),
            'jpy_credit_candidate_pipeline_ready': True,
            'jpy_credit_collector': str(JPY_CREDIT_COLLECTOR),
            'jpy_credit_database': jpy_credit.get('database'),
            'jpy_credit_series_key': jpy_credit.get('series_key'),
            'eur_m3_effective_status': effective_m3.get('status'),
            'eur_m3_collector_status': effective_m3.get('collector_status'),
            'publication_eligible': False,
            'reason': f'{liq_source_mapped}/{liq_total} official source families are mapped, but only {liq_ready}/{liq_total} are currently automation-ready after fail-closing EUR M3 for revision/vintage handling; additional exact source collectors are candidate-only until controlled apply wiring exists',
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
