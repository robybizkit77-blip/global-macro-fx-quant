#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = ROOT / 'validation' / 'cb_pricing' / 'CB_PRICING_SOURCE_STATUS_2026-10-08.json'
OIS = ROOT / 'live_data' / 'sections' / 'OIS_DATA.json'
G8 = ['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']
SOURCE_ALIASES = {
    'AUD': ['ASX'],
    'CAD': ['Montréal Exchange', 'Montreal Exchange'],
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
    if failures:
        print(json.dumps({'status':'FAIL','failures':failures},indent=2)); return 2

    registry=json.loads(REGISTRY.read_text())
    ois=json.loads(OIS.read_text())
    reg_ccy=registry.get('currencies') or {}
    live_ccy=ois.get('currencies') or {}

    if sorted(reg_ccy) != sorted(G8):
        failures.append(f'registry currency set mismatch: {sorted(reg_ccy)}')
    if sorted(live_ccy) != sorted(G8):
        failures.append(f'OIS currency set mismatch: {sorted(live_ccy)}')

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
    if governance.get('active_count') != len(active):
        failures.append('registry active_count mismatch')
    if governance.get('withheld_count') != len(withheld):
        failures.append('registry withheld_count mismatch')
    if governance.get('active') != active:
        failures.append('registry active list/order mismatch')
    if governance.get('withheld') != withheld:
        failures.append('registry withheld list/order mismatch')

    status='PASS' if not failures else 'FAIL'
    details['rows']=rows
    details['active']=active
    details['withheld']=withheld
    print(json.dumps({'status':status,'failures':failures,'details':details},indent=2))
    return 0 if not failures else 2


if __name__ == '__main__':
    sys.exit(main())
