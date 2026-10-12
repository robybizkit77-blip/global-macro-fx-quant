#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SECTIONS=ROOT/'live_data'/'sections'
PAYLOAD=ROOT/'payload'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    research=json.loads((SECTIONS/'RESEARCH_STATE.json').read_text())
    candidates=json.loads((SECTIONS/'RESEARCH_CANDIDATES.json').read_text())
    assert research['research_signal_state']=='WITHHELD'
    assert research['decision_weight']==0 and research['decision_signal_count']==0
    assert research['may_modify_pair_bias'] is False and research['may_modify_currency_score'] is False and research['may_modify_sizing'] is False
    assert candidates['mode']=='DISPLAY_ONLY_RESEARCH'
    assert candidates['governance']['decision_weight']==0 and candidates['governance']['bias_effect']==0 and candidates['governance']['ranking_effect']==0 and candidates['governance']['sizing_effect']==0
    assert len(candidates['candidates'])==3 and all(x['decision_weight']==0 for x in candidates['candidates'])
    runtime=b''.join((PAYLOAD/f'part-{i:02d}.txt').read_bytes() for i in range(16))
    macro=[]
    for fn in ('MACRO_THERMOMETER_DATA.json','MACRO_SERIES.json'):
        p=SECTIONS/fn; raw=p.read_bytes(); macro.append({'file':fn,'section_sha256':sha(p),'section_bytes':len(raw),'exact_occurrences_in_current_payload':runtime.count(raw)})
    assert all(x['exact_occurrences_in_current_payload']==0 for x in macro),macro
    out={'schema':'GMFQ_DASHBOARD_FULL_INTEGRATION_PREFLIGHT_V1','status':'READY_FOR_FULL_DASHBOARD_REBUILD_WITH_KNOWN_MACRO_RUNTIME_BLOCKER','research_governance':{'context_only_count':research['context_only_count'],'decision_weight':0,'production_authorized':False,'candidate_display_count':3},'known_runtime_blockers':[{'id':'LEGACY_MACRO_PAYLOAD_MAPPING','scope':['MACRO_THERMOMETER_DATA','MACRO_SERIES'],'finding':'Current canonical Macro section bytes occur zero times in the legacy assembled payload. In-place direct-section update is not safe.','resolution':'Rebuild the dashboard runtime from canonical section sources during the full dashboard integration rather than patching legacy offsets.'}],'macro_runtime_diagnostic':macro,'safe_next_action':'FULL_RUNTIME_REBUILD_FROM_CANONICAL_SECTIONS','changes_signal_rules':False,'changes_bias':False,'changes_sizing':False}
    Path('/tmp/dashboard-full-integration-preflight.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps(out,indent=2,sort_keys=True))
if __name__=='__main__': main()
