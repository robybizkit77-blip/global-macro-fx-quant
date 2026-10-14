#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def run(cmd, cwd: Path) -> str:
    p = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if p.returncode:
        raise SystemExit(f"command failed ({' '.join(cmd)}):\n{p.stdout}")
    return p.stdout.strip()


def exists(root: Path, rel: str) -> bool:
    return (root / rel).exists()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--main-dir', required=True)
    ap.add_argument('--certified-dir', required=True)
    ap.add_argument('--out')
    args = ap.parse_args()

    main_dir = Path(args.main_dir).resolve()
    cert_dir = Path(args.certified_dir).resolve()

    main_sha = run(['git', 'rev-parse', 'HEAD'], main_dir)
    certified_sha = run(['git', 'rev-parse', 'HEAD'], cert_dir)

    final_gate_path = cert_dir / 'validation' / 'run_daily_data_orchestrator_final_gate_v1.py'
    if not final_gate_path.exists():
        raise SystemExit('certified stack is missing run_daily_data_orchestrator_final_gate_v1.py')

    gate_raw = run(['python3', 'validation/run_daily_data_orchestrator_final_gate_v1.py'], cert_dir)
    gate = json.loads(gate_raw)

    if gate.get('schema') != 'GMFQ_DAILY_DATA_ORCHESTRATOR_FINAL_GATE_RECEIPT_V1':
        raise SystemExit(f'unexpected certified gate schema: {gate.get("schema")}')
    if gate.get('operational_state') != 'READY_WITH_DOCUMENTED_EXPECTED_GAPS':
        raise SystemExit(f'certified stack no longer has expected operational state: {gate}')
    if gate.get('publishable') is not False or gate.get('publication_state') != 'WITHHELD':
        raise SystemExit('certified stack publication guard drifted')

    liq = (gate.get('lane_receipts') or {}).get('LIQUIDITY') or {}
    if (liq.get('ready_subseries'), liq.get('withheld_subseries'), liq.get('total_subseries')) != (23, 3, 26):
        raise SystemExit(f'certified liquidity state drifted: {liq}')

    blockers = gate.get('exact_blockers') or []
    blocker_keys = [(x.get('lane'), x.get('key')) for x in blockers]
    expected = [
        ('LIQUIDITY', 'CHF.liquidity'),
        ('LIQUIDITY', 'CHF.credit'),
        ('LIQUIDITY', 'JPY.liquidity'),
        ('RISK', 'Brent'),
    ]
    if blocker_keys != expected:
        raise SystemExit(f'certified blocker set drifted: {blocker_keys}')

    critical = [
        'validation/run_daily_data_orchestrator_final_gate_v1.py',
        'validation/run_daily_data_orchestrator_effective_price_v1.py',
        'validation/risk/BRENT_SOURCE_FRESHNESS_RESOLUTION_2026-10-13.json',
        'validation/risk/RISK_SOURCE_POLICY_V1_2026-10-12.json',
        'validation/check_risk_brent_hard_blocker_v1.py',
        'validation/liquidity/CHF_CREDIT_PROVENANCE_RESOLUTION_2026-10-13.json',
        'validation/liquidity/CHF_SIGHT_DEPOSITS_PROVENANCE_RESOLUTION_2026-10-13.json',
        'validation/liquidity/JPY_RESERVE_PROVENANCE_RESOLUTION_2026-10-13.json',
        'validation/liquidity/LIQUIDITY_SOURCE_POLICY_V1_2026-10-12.json',
        'validation/price/PRICE_ECB_CONTROLLED_APPLY_CONTRACT_V1_2026-10-13.json',
        '.github/workflows/risk-brent-hard-blocker-contract-v1.yml',
        '.github/workflows/dashboard-finalization-audit-v1.yml',
    ]
    main_presence = {p: exists(main_dir, p) for p in critical}
    certified_presence = {p: exists(cert_dir, p) for p in critical}
    if not all(certified_presence.values()):
        missing = [p for p, ok in certified_presence.items() if not ok]
        raise SystemExit(f'critical artifacts missing from certified stack: {missing}')

    missing_on_main = [p for p, ok in main_presence.items() if not ok]

    receipt = {
        'schema': 'GMFQ_MAIN_CERTIFIED_STACK_RECONCILIATION_V1',
        'main_sha': main_sha,
        'certified_stack_sha': certified_sha,
        'certified_gate': {
            'operational_state': gate['operational_state'],
            'publication_state': gate['publication_state'],
            'ready_lanes': gate.get('ready_lanes'),
            'withheld_lanes': gate.get('withheld_lanes'),
            'liquidity': liq,
            'exact_blockers': blockers,
        },
        'main_materialization': {
            'critical_artifact_count': len(critical),
            'present_count': sum(main_presence.values()),
            'missing_count': len(missing_on_main),
            'missing_on_main': missing_on_main,
            'presence': main_presence,
        },
        'reconciliation_state': 'CERTIFIED_STATE_AHEAD_OF_MAIN' if missing_on_main else 'MAIN_CONTAINS_CERTIFIED_CRITICAL_ARTIFACTS',
        'promotion_required': bool(missing_on_main),
        'safe_next_action': 'PROMOTE_CERTIFIED_CRITICAL_ARTIFACTS_IN_CLEAN_SCOPED_PRS' if missing_on_main else 'RUN_GLOBAL_GATE_ON_MAIN',
        'runtime_mutated': False,
        'publication_performed': False,
    }

    text = json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True) + '\n'
    if args.out:
        Path(args.out).write_text(text, encoding='utf-8')
    print(text, end='')


if __name__ == '__main__':
    main()
