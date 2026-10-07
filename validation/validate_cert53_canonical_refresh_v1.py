#!/usr/bin/env python3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WRAPPER=ROOT/'validation'/'run_cert53_refresh_v1.py'
UPDATER=ROOT/'validation'/'update_live_direct_section.py'
MANIFEST_BUILDER=ROOT/'validation'/'build_live_manifest_v2.py'
CONTRACT=ROOT/'validation'/'check_live_update_contract.py'

fail=[]
for p in (WRAPPER,UPDATER,MANIFEST_BUILDER,CONTRACT):
    if not p.exists(): fail.append(f'missing {p.relative_to(ROOT)}')
text=WRAPPER.read_text() if WRAPPER.exists() else ''
required=[
    "--confirm-refresh-id",
    "rollback_on_post_apply_failure",
    "build_live_manifest_v2.py",
    "check_live_update_contract.py",
    "provenance refresh_id already exists",
    "PREFLIGHT_ONLY",
    "APPLIED_AND_VERIFIED",
    "ROLLED_BACK_AFTER_FAILURE"
]
for token in required:
    if token not in text: fail.append('wrapper missing token: '+token)
up=UPDATER.read_text() if UPDATER.exists() else ''
if "CERT53 --apply requires --provenance" not in up:
    fail.append('direct updater no longer enforces CERT53 provenance on apply')
if "provenance_target.exists()" not in up:
    fail.append('direct updater no longer refuses duplicate provenance refresh_id')
print('PASS CERT53 canonical refresh contract' if not fail else 'FAIL '+repr(fail))
raise SystemExit(0 if not fail else 2)
