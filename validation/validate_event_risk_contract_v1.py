import json
from pathlib import Path
R=Path(__file__).resolve().parent
contract=json.loads((R/'EVENT_RISK_COMPACT_CONTRACT_V1_2026-10-07.json').read_text())
ready=json.loads((R/'EVENT_RISK_SOURCE_READINESS_V1_2026-10-07.json').read_text())
assert contract['schema']=='GMFQ_EVENT_RISK_COMPACT_CONTRACT_V1'
assert contract['status']=='RESEARCH_ONLY_CONTRACT_NOT_PROMOTED'
req=set(contract['required_source_fields'])
for k in ['event_id','currency','event_name','scheduled_at','previous','consensus','actual','source','source_asof']:
    assert k in req
assert contract['display_policy']['max_events_global']<=8
assert contract['display_policy']['max_events_per_currency']<=2
assert contract['display_policy']['hide_low_impact'] is True
assert contract['display_policy']['do_not_infer_missing_consensus'] is True
assert contract['display_policy']['do_not_use_stale_schedule'] is True
assert ready['schema']=='GMFQ_EVENT_RISK_SOURCE_READINESS_V1'
assert ready['status']=='WITHHELD_EVENT_SOURCE'
state=ready['current_repo_state']
assert state['canonical_event_feed_present'] is False
assert ready['ui_state']['show_fake_or_stale_events'] is False
for key in ['changes_engine_rules','changes_live_data','changes_oos_baseline','production_promotion','fills_missing_events']:
    assert ready['guards'][key] is False
print('PASS', ready['status'])
