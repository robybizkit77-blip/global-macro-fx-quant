#!/usr/bin/env python3
import json, math, statistics
from pathlib import Path

SRC=Path('validation/JPY_RATES_TRANSMISSION_V1_2026-10-07.json')
REPLAY=Path('validation/JPY_REACTION_FUNCTION_REPLAY_V1_2026-10-06.json')
OUT=Path('validation/JPY_RATES_TRANSMISSION_OOS_V1_2026-10-07.json')

def stats(vals):
    vals=[x for x in vals if x is not None]
    if not vals:return {'n':0,'hit_rate':None,'mean':None,'median':None}
    return {'n':len(vals),'hit_rate':sum(x>0 for x in vals)/len(vals),'mean':sum(vals)/len(vals),'median':statistics.median(vals)}

def main():
    src=json.loads(SRC.read_text()); rep=json.loads(REPLAY.read_text())
    samples=rep['directional_samples']
    start=math.floor(len(samples)*0.4)
    oos_dates={x['checkpoint'] for x in samples[start:]}
    rows=[r for r in src['paired_events'] if r['checkpoint'] in oos_dates]
    assert len(rows)==rep['walkforward']['pooled_oos_event_count']==29
    analysis={}
    for key in ('jpy2y_state_5obs','jpy2y_state_20obs','diff_state_5obs','diff_state_20obs'):
        analysis[key]={}
        for st in ('CONFIRM','DIVERGE','FLAT'):
            analysis[key][st]=stats([r['signed_20d'] for r in rows if r.get(key)==st and r.get('signed_20d') is not None])
    out={
      'schema':'GMFQ_JPY_RATES_TRANSMISSION_OOS_V1','status':'PASS_DIAGNOSTIC_NOT_PROMOTED','created_at':'2026-10-07',
      'source_transmission':str(SRC),'source_replay':str(REPLAY),'oos_definition':'same chronological pooled OOS cohort as frozen JPY reaction replay; first 40% excluded',
      'oos_events':len(rows),'analysis_20d_fx_outcome_oos':analysis,
      'interpretation_guardrail':'diagnostic attribution only; no selection/tuning from result',
      'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False
    }
    OUT.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))
if __name__=='__main__': main()
