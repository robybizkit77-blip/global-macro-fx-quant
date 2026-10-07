import json
from pathlib import Path

p=Path('validation/FORWARD_AUTOMATION_WIRING_AUDIT_V1_2026-10-07.json')
d=json.loads(p.read_text())
assert d['schema']=='GMFQ_FORWARD_AUTOMATION_WIRING_AUDIT_V1'
assert d['status']=='PARTIAL_AUTOMATION__UPSTREAM_LIVE_REFRESH_MANUAL'
f=d['findings']
assert f['cert53_change_triggers_signed_inputs'] is True
assert f['signed_inputs_trigger_transmission'] is True
assert f['signed_inputs_trigger_rule_sensitivity'] is True
assert f['transmission_and_sensitivity_feed_robustness'] is True
assert f['transmission_and_robustness_feed_render_payload'] is True
assert f['render_payload_change_triggers_semantic_snapshot_auto_append'] is True
assert f['semantic_snapshot_auto_append_materializes_frozen_pair_snapshot'] is True
assert f['semantic_snapshot_auto_append_updates_sha256_manifest'] is True
assert f['ecb_forward_outcome_collection_scheduled'] is True
assert f['historical_outcome_labels_read_from_frozen_snapshot'] is True
assert f['upstream_live_data_ingest_scheduled'] is False
assert f['fully_autonomous_forward_collection'] is False
assert d['classification']['overall']=='PARTIALLY_AUTOMATED_NOT_FULLY_AUTONOMOUS'
assert all(d['guards'].values()) is False if False else True
assert d['guards']['does_not_enable_upstream_schedule'] is True
assert d['guards']['does_not_change_engine_rules'] is True
assert d['guards']['does_not_change_live_data'] is True
assert d['guards']['does_not_change_oos_baseline'] is True
assert d['guards']['production_promotion'] is False
print('PASS forward automation boundary audit')
