#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OIS = ROOT / 'live_data' / 'sections' / 'OIS_DATA.json'
CHECKER = ROOT / 'validation' / 'check_cb_pricing_source_registry.py'


def run_checker() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def require_pass(label: str) -> None:
    p = run_checker()
    if p.returncode != 0:
        raise SystemExit(f'{label}: expected PASS, got rc={p.returncode}\n{p.stdout}\n{p.stderr}')


def require_fail(label: str, expected_fragment: str) -> None:
    p = run_checker()
    combined = (p.stdout or '') + '\n' + (p.stderr or '')
    if p.returncode == 0:
        raise SystemExit(f'{label}: checker unexpectedly PASSED')
    if expected_fragment not in combined:
        raise SystemExit(
            f'{label}: checker failed, but missing expected evidence {expected_fragment!r}\n{combined}'
        )


def write_json(data: dict) -> None:
    OIS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def main() -> int:
    original_text = OIS.read_text()

    try:
        require_pass('baseline')

        # Attack 1: force a governance-WITHHELD currency to ACTIVE with superficially complete fields.
        case = json.loads(original_text)
        usd = case['currencies']['USD']
        usd['status'] = 'ACTIVE'
        usd['source'] = 'CME/CBOT synthetic negative-test mutation'
        usd['as_of'] = '2099-01-01'
        usd['policy_rate'] = 1.0
        usd['meetings'] = [{'date': '2099-01-01', 'label': 'NEGATIVE_TEST'}]
        for tenor in ('3m', '6m', '12m'):
            usd.setdefault('horizons', {}).setdefault(tenor, {})
            usd['horizons'][tenor].update({
                'rate': 1.0,
                'change_1d_bp': 0.0,
                'change_1w_bp': 0.0,
                'policy_delta_bp': 0.0,
            })
        usd['validation'] = {
            'source_validated': True,
            'asof_validated': True,
            'meeting_path_validated': True,
            'changes_validated': True,
        }
        write_json(case)
        require_fail('withheld_to_active', "USD: runtime status 'ACTIVE' != registry 'WITHHELD'")

        # Attack 2: keep an ACTIVE currency structurally valid but substitute an unauthorized source.
        case = json.loads(original_text)
        case['currencies']['AUD']['source'] = 'UNAUTHORIZED NEGATIVE TEST SOURCE'
        write_json(case)
        require_fail('unauthorized_source', 'AUD: ACTIVE source not authorized by registry')

        # Attack 3: remove one required weekly-change field from a legitimate ACTIVE currency.
        case = json.loads(original_text)
        case['currencies']['GBP']['horizons']['6m']['change_1w_bp'] = None
        write_json(case)
        require_fail('missing_change_field', 'GBP: ACTIVE missing 6m.change_1w_bp')

    finally:
        OIS.write_text(original_text)

    if OIS.read_text() != original_text:
        raise SystemExit('restore failed: OIS_DATA.json is not byte-identical to baseline')
    require_pass('post_restore')

    print(json.dumps({
        'status': 'PASS',
        'negative_cases': [
            'WITHHELD_USD_FORCED_ACTIVE_BLOCKED',
            'AUD_UNAUTHORIZED_SOURCE_BLOCKED',
            'GBP_MISSING_1W_CHANGE_BLOCKED',
        ],
        'runtime_restored_byte_identical': True,
    }, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
