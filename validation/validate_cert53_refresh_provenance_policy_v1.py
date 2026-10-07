#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
UPD=ROOT/'validation/update_live_direct_section.py'
TPL=ROOT/'validation/CERT53_REFRESH_PROVENANCE_TEMPLATE_V1_2026-10-07.json'
AUD=ROOT/'validation/CERT53_PROVENANCE_AUDIT_V1_2026-10-07.json'

text=UPD.read_text(encoding='utf-8')
tpl=json.loads(TPL.read_text(encoding='utf-8'))
aud=json.loads(AUD.read_text(encoding='utf-8'))

assert tpl['schema']=='GMFQ_CERT53_REFRESH_PROVENANCE_V1'
assert tpl['status']=='TEMPLATE_NOT_A_REFRESH_RECORD'
assert tpl['section']=='CERT53'
assert aud['status']=='PARTIAL_PROVENANCE'
assert aud['assessment']['fully_autonomous_claim_allowed'] is False
for needle in [
    "CERT53 --apply requires --provenance; untraceable refresh refused",
    "candidate_sha256 does not match replacement bytes",
    "CERT53 replacement must contain exactly 28 pairs",
    "provenance refresh_id already exists",
    "source_metadata_checked",
    "manual_review_required",
]:
    assert needle in text, f'missing policy guard: {needle}'
print('PASS CERT53 future refresh provenance policy enforced; historical lineage remains PARTIAL')
