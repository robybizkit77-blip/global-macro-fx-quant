#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'validation/price/PRICE_ECB_CONTROLLED_APPLY_CONTRACT_V1_2026-10-13.json'


def main():
    d = json.loads(CONTRACT.read_text(encoding='utf-8'))
    if d.get('schema') != 'GMFQ_PRICE_ECB_CONTROLLED_APPLY_CONTRACT_V1':
        raise SystemExit('unexpected Price contract schema')
    if d.get('controlled_apply_proven') is not True or d.get('automation_ready') is not True:
        raise SystemExit('Price controlled apply not certified')
    if d.get('persistent_publication_enabled') is not False:
        raise SystemExit('Price publication guard drift')
    if d.get('runtime_mutated') is not False or d.get('publication_performed') is not False:
        raise SystemExit('Price proof must remain non-mutating/non-publishing')
    p = d.get('proof') or {}
    if p.get('exact_diff_scope') != ['payload/part-15.txt']:
        raise SystemExit(f'Price diff scope drift: {p.get("exact_diff_scope")}')
    if p.get('idempotent_second_apply') is not True or p.get('tracked_runtime_restored') is not True:
        raise SystemExit('Price idempotence/restore proof drift')
    if p.get('candidate_as_of') != '2026-10-13':
        raise SystemExit('Price certified candidate date drift')
    receipt = {
        'schema': 'GMFQ_PRICE_CONTROLLED_APPLY_RECEIPT_V1',
        'status': 'CONTROLLED_APPLY_PROVEN_PUBLICATION_WITHHELD',
        'source': 'ECB euro foreign exchange reference rates',
        'currency_count': 8,
        'derived_pair_count': 28,
        'exact_diff_scope': ['payload/part-15.txt'],
        'idempotent_apply_proven': True,
        'runtime_mutated': False,
        'publication_performed': False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
