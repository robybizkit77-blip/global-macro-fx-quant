#!/usr/bin/env python3
import json
import re
import subprocess
from pathlib import Path

CERT = Path('live_data/sections/CERT53.json')
OUT = Path('validation/CERT53_MACRO_ANCHOR_PROVENANCE_AUDIT_V1_2026-10-07.json')


def sh(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()


def tracked_files():
    return sh('git','ls-files').splitlines()


def is_writer(text: str) -> bool:
    mentions = ('CERT53.json' in text or 'fundamental_anchor_macro' in text)
    write_patterns = [
        r'write_text\s*\(', r'write_bytes\s*\(', r'json\.dump\s*\(',
        r'open\s*\([^\n]{0,160}["\']w["\']', r'Path\([^\n]{0,160}CERT53[^\n]{0,160}\)\.write',
    ]
    return mentions and any(re.search(p, text) for p in write_patterns)


def main():
    cert = json.loads(CERT.read_text())
    pairs_obj = cert.get('pairs', {})
    if isinstance(pairs_obj, list):
        pair_count = len(pairs_obj)
    else:
        pair_count = len(pairs_obj.keys())

    candidates = []
    references = []
    for name in tracked_files():
        p = Path(name)
        if not p.is_file() or p == CERT or p == OUT:
            continue
        if p.suffix.lower() not in {'.py','.yml','.yaml','.js','.json','.md','.txt','.html'}:
            continue
        try:
            text = p.read_text(errors='ignore')
        except Exception:
            continue
        if 'CERT53' in text or 'fundamental_anchor_macro' in text:
            references.append(name)
            if is_writer(text):
                candidates.append(name)

    try:
        log = sh('git','log','--follow','--format=%H|%aI|%s','--',str(CERT)).splitlines()
    except subprocess.CalledProcessError:
        log = []

    governance = cert.get('governance', {})
    meta = cert.get('meta', {}) if isinstance(cert.get('meta'), dict) else {}
    certified_at = cert.get('certified_at') or governance.get('certified_at') or meta.get('certified_at')
    certification_state = cert.get('certification_state') or governance.get('certification_state') or meta.get('certification_state')

    # A writer candidate is not automatically a valid regenerator. For this V1 audit,
    # absence of any repository writer is sufficient to classify the section as a static snapshot.
    status = 'REGENERATOR_CANDIDATE_FOUND_REQUIRES_REVIEW' if candidates else 'STATIC_CERTIFIED_SNAPSHOT_NO_REGENERATOR_FOUND'

    out = {
        'schema': 'GMFQ_CERT53_MACRO_ANCHOR_PROVENANCE_AUDIT_V1',
        'status': status,
        'source_file': str(CERT),
        'pair_count': pair_count,
        'certification_state': certification_state,
        'certified_at': certified_at,
        'git_history': log,
        'repository_references': sorted(references),
        'writer_candidates': sorted(candidates),
        'writer_candidate_count': len(candidates),
        'frozen_engine_architecture': {
            'canonical_pair_macro_source': 'compare canonical currency Macro states',
            'legacy_pair_macro_override_allowed': False,
            'note': 'Frozen runtime explicitly prevents legacy relative pair Macro readings from overriding the canonical currency engine.'
        },
        'interpretation': {
            'does_not_claim_cert53_wrong': True,
            'claim': 'CERT53 can be a certified historical/current snapshot while still lacking a reproducible live regenerator.',
            'macro_ingest_apply': 'BLOCKED_UNTIL_CURRENT_CANONICAL_CURRENCY_MACRO_REGENERATION_EXISTS',
            'next_required_artifact': 'CURRENT_CANONICAL_CURRENCY_MACRO_REGENERATION_CONTRACT_V1'
        },
        'guards': {
            'changes_engine_rules': False,
            'changes_live_data': False,
            'changes_oos_baseline': False,
            'production_promotion': False,
            'predictive_claim': False
        }
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({
        'status': status,
        'pair_count': pair_count,
        'writer_candidates': candidates,
        'history_entries': len(log)
    }, ensure_ascii=False))

if __name__ == '__main__':
    main()
