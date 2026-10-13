#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = ROOT / 'validation' / 'cb_pricing' / 'CB_PRICING_SOURCE_STATUS_2026-10-08.json'
AUDIT = ROOT / 'validation' / 'cb_pricing' / 'OIS_G8_SOURCE_AUDIT_V2_2026-10-13.json'
OIS = ROOT / 'live_data' / 'sections' / 'OIS_DATA.json'
G8 = ['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']
SOURCE_ALIASES = {
    'AUD': ['ASX'],
    # Accept the ASCII stem too: historical runtime bytes can render the
    # accented exchange name differently, while source identity remains fixed.
    'CAD': ['Montr', 'Montreal Exchange'],
    'GBP': ['Bank of England'],
    'JPY': ['Tokyo Financial Exchange'],
}


def main() -> int:
    failures=[]
    details={}
    if not REGISTRY.exists():
        failures.append('missing canonical CB pricing source registry')
    if not OIS.exists():
        failures.append('missing OIS_DATA.json')
    if not AUDIT.exists():
        failures.append('missing OIS G8 source audit')
    if failures:
        print(json.dumps({'status':'FAIL','failures':failures},indent=2)); return 2

    registry=json.loads(REGISTRY.read_text())
    ois=json.loads(OIS.read_text())
    audit=json.loads(AUDIT.read_text())
    reg_ccy=registry.get('currencies') or {}
    live_ccy=ois.get('currencies') or {}

    if sorted(reg_ccy) != sorted(G8):
        failures.append(f'registry currency set mismatch: {sorted(reg_ccy)}')
    if sorted(live_ccy) != sorted(G8):
        failures.append(f'OIS currency set mismatch: {sorted(live_ccy)}')
    audit_ccy=audit.get('currencies') or {}
    if sorted(audit_ccy) != sorted(G8):
        failures.append(f'audit currency set mismatch: {sorted(audit_ccy)}')

    rows={}
    for ccy in G8:
        reg=reg_ccy.get(ccy) or {}
        live=live_ccy.get(ccy) or {}
        expected=reg.get('status')
        actual=live.get('status')
        row={'registry_status':expected,'runtime_status':actual,'source':live.get('source')}
        rows[ccy]=row

        if expected not in {'ACTIVE','WITHHELD'}:
            failures.append(f'{ccy}: invalid registry status {expected!r}')
            continue
        if actual != expected:
            failures.append(f'{ccy}: runtime status {actual!r} != registry {expected!r}')
        audited=audit_ccy.get(ccy) or {}
        if audited.get('status') != expected:
            failures.append(f'{ccy}: audit status {audited.get("status")!r} != registry {expected!r}')
        for field in ('source_identity','quotation_unit','tenor_mapping','historical_availability','pit_freshness','licensing_reproducibility','relative_signal_eligible'):
            if field not in audited:
                failures.append(f'{ccy}: audit missing {field}')
        if expected == 'ACTIVE' and audited.get('relative_signal_eligible') is not True:
            failures.append(f'{ccy}: ACTIVE audit must be relatively eligible')
        if expected == 'WITHHELD' and audited.get('relative_signal_eligible') is not False:
            failures.append(f'{ccy}: WITHHELD audit must not be relatively eligible')

        horizons=live.get('horizons') or {}
        validation=live.get('validation') or {}

        if expected == 'WITHHELD':
            if live.get('source') is not None:
                failures.append(f'{ccy}: WITHHELD must not expose source')
            if live.get('as_of') is not None or live.get('policy_rate') is not None:
                failures.append(f'{ccy}: WITHHELD must not expose as_of/policy_rate')
            for tenor in ('3m','6m','12m'):
                h=horizons.get(tenor) or {}
                for field in ('rate','change_1d_bp','change_1w_bp','policy_delta_bp'):
                    if h.get(field) is not None:
                        failures.append(f'{ccy}: WITHHELD {tenor}.{field} must be null')
            for flag in ('source_validated','asof_validated','meeting_path_validated','changes_validated'):
                if validation.get(flag) is not False:
                    failures.append(f'{ccy}: WITHHELD validation.{flag} must be false')
        else:
            source=str(live.get('source') or '')
            aliases=SOURCE_ALIASES.get(ccy, [str(reg.get('official_source') or '')])
            if not source or not any(a and a.lower() in source.lower() for a in aliases):
                failures.append(f'{ccy}: ACTIVE source not authorized by registry: {source!r}')
            if live.get('as_of') is None or live.get('policy_rate') is None:
                failures.append(f'{ccy}: ACTIVE missing as_of/policy_rate')
            if not live.get('meetings'):
                failures.append(f'{ccy}: ACTIVE missing mapped meeting path')
            for tenor in ('3m','6m','12m'):
                h=horizons.get(tenor) or {}
                for field in ('rate','change_1d_bp','change_1w_bp','policy_delta_bp'):
                    if h.get(field) is None:
                        failures.append(f'{ccy}: ACTIVE missing {tenor}.{field}')
            for flag in ('source_validated','asof_validated','meeting_path_validated','changes_validated'):
                if validation.get(flag) is not True:
                    failures.append(f'{ccy}: ACTIVE validation.{flag} must be true')

    governance=registry.get('governance') or {}
    active=[c for c in G8 if (reg_ccy.get(c) or {}).get('status')=='ACTIVE']
    withheld=[c for c in G8 if (reg_ccy.get(c) or {}).get('status')=='WITHHELD']
    declared_active=governance.get('active') or []
    declared_withheld=governance.get('withheld') or []

    if governance.get('active_count') != len(active):
        failures.append('registry active_count mismatch')
    if governance.get('withheld_count') != len(withheld):
        failures.append('registry withheld_count mismatch')
    if len(declared_active) != len(set(declared_active)) or set(declared_active) != set(active):
        failures.append('registry active membership mismatch')
    if len(declared_withheld) != len(set(declared_withheld)) or set(declared_withheld) != set(withheld):
        failures.append('registry withheld membership mismatch')
    result=audit.get('result') or {}
    if result.get('active') != active or result.get('withheld') != withheld:
        failures.append('audit result membership mismatch')
    if result.get('g8_fully_comparable') is not False or result.get('relative_pair_vote') is not False:
        failures.append('partial G8 audit must remain non-comparable and non-voting')

    status='PASS' if not failures else 'FAIL'
    details['rows']=rows
    details['active']=active
    details['withheld']=withheld
    print(json.dumps({'status':status,'failures':failures,'details':details},indent=2))
    return 0 if not failures else 2


if __name__ == '__main__':
    sys.exit(main())
