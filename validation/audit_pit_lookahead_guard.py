#!/usr/bin/env python3
import json, re, calendar
from pathlib import Path
from datetime import date

OUT=Path('validation/PIT_LOOKAHEAD_GUARD_AUDIT_2026-10-03.json')
REPLAY=Path('validation/build_pit_macro_replay_v1.py')

def load(p): return json.loads(Path(p).read_text())
def d(s): return date.fromisoformat(s)
def period_end(p):
    if not p: return None
    if re.fullmatch(r'\d{4}-\d{2}',p):
        y,m=map(int,p.split('-')); return date(y,m,calendar.monthrange(y,m)[1])
    m=re.fullmatch(r'(\d{4})-Q([1-4])',p)
    if m:
        y=int(m.group(1)); q=int(m.group(2)); mm=q*3
        return date(y,mm,calendar.monthrange(y,mm)[1])
    return None

def inspect_rows(name, rows, relkey, obskeys):
    missing=[]; pre_period=[]; inversions=[]; prev=None; parsed=0
    for i,r in enumerate(rows):
        rel=r.get(relkey)
        obs=next((r.get(k) for k in obskeys if r.get(k)),None)
        if not rel:
            missing.append(i); continue
        rd=d(rel); parsed+=1
        pe=period_end(obs)
        if pe and rd < pe:
            pre_period.append({'index':i,'observation':obs,'release_date':rel,'period_end':pe.isoformat()})
        if prev and rd < prev:
            inversions.append({'index':i,'release_date':rel,'previous_release_date':prev.isoformat()})
        prev=rd
    return {'series':name,'rows':len(rows),'release_dates_parsed':parsed,'missing_release_date_count':len(missing),'release_before_observation_period_end_count':len(pre_period),'release_date_order_inversions':len(inversions),'examples':{'missing_release_date_indexes':missing[:5],'release_before_period_end':pre_period[:5],'date_inversions':inversions[:5]},'pass':not missing and not pre_period and not inversions}

checks=[]
# USD eligible
ind=load('validation/pit_batch/fed_g17/FED_G17_INDPRO_PIT_BATCH_READY_V1_2026-10-02.json')['rows']
checks.append(inspect_rows('USD/US_INDPRO_history_value',ind,'release_date',['observation_month','reference_month','period']))
bea=load('validation/pit_batch/bea/BEA_PIO_PIT_BATCH_V1_2026-10-03.json')['rows']
pi=[r for r in bea if r.get('personal_income_first_release_mom_pct') is not None]
checks.append(inspect_rows('USD/US_PI_history_PI',pi,'release_date',['observation_month','reference_month','period']))
new=load('validation/pit_batch/census/CENSUS_M3_NEWORDER_PIT_BATCH_V1_2026-10-03.json')['rows']
new=[r for r in new if r.get('neworder_first_release_millions_sa') is not None]
checks.append(inspect_rows('USD/US_NEWORDER_history_NEWORDER',new,'release_date',['observation_month','reference_month','period']))

# EUR eligible
eur=load('validation/pit_batch/eurostat/EUROSTAT_PIT_READY_V1_2026-10-02.json')['series']
checks.append(inspect_rows('EUR/EA_IP_history_value',eur['EA_IP_history_value']['rows'],'first_release_date',['observation_month','reference_month','period']))
checks.append(inspect_rows('EUR/EA_UNEMP_history_value',eur['EA_UNEMP_history_value']['rows'],'first_release_date',['observation_month','reference_month','period']))
emp=load('validation/pit_batch/eurostat/archive/EUR_EMPLOYMENT_DATED_RELEASE_CRAWL_V1_2026-10-02.json')['rows']
checks.append(inspect_rows('EUR/EA_EMPLOYMENT_history_value',emp,'release_date',['reference_quarter','observation_quarter','period']))

# CAD reuse guard: every forward-filled source checkpoint must be <= aggregate checkpoint.
cad=load('validation/PIT_SIGNAL_SENSITIVITY_CA_MACRO_FULL_2020_2026_V1_2026-10-02.json')
cad_bad=[]; missing_latest=[]
for i,r in enumerate(cad.get('comparisons',[])):
    cp=r.get('checkpoint'); g=r.get('latest_growth_checkpoint'); l=r.get('latest_labour_checkpoint')
    if not cp or not g or not l:
        missing_latest.append(i); continue
    if d(g)>d(cp) or d(l)>d(cp):
        cad_bad.append({'index':i,'checkpoint':cp,'latest_growth_checkpoint':g,'latest_labour_checkpoint':l})
checks.append({'series':'CAD/Macro Core aggregate','rows':len(cad.get('comparisons',[])),'missing_latest_source_checkpoint_count':len(missing_latest),'future_source_checkpoint_count':len(cad_bad),'examples':{'missing':missing_latest[:5],'future':cad_bad[:5]},'pass':not missing_latest and not cad_bad})

# Static replay-code guard: USD/EUR value retrieval must be gated on release_date <= checkpoint.
text=REPLAY.read_text()
static={
 'vals_asof_release_gate_present': "r['release_date']<=cp" in text.replace(' ',''),
 'checkpoints_derived_from_release_date': "r['release_date']" in text and "cps=sorted" in text,
 'cad_reuses_validated_release_checkpoint_artifact': 'PIT_SIGNAL_SENSITIVITY_CA_MACRO_FULL_2020_2026_V1_2026-10-02.json' in text,
 'no_observation_date_as_asof_filter_found': not bool(re.search(r"observation_(?:month|quarter).*<=\s*cp|reference_(?:month|quarter).*<=\s*cp",text)),
}
static['pass']=all(static.values())

hard_failures=[]
for c in checks:
    if not c.get('pass'): hard_failures.append(c['series'])
if not static['pass']: hard_failures.append('replay_static_gate')

report={
 'schema':'GMFQ_PIT_LOOKAHEAD_GUARD_AUDIT_V1',
 'created_at':'2026-10-03',
 'engine_ref':'engine-freeze-v1-2026-10-02',
 'rules_fingerprint':'3356baf0',
 'scope':{'eligible_series':{
   'USD':['US_INDPRO_history_value','US_PI_history_PI','US_NEWORDER_history_NEWORDER'],
   'EUR':['EA_IP_history_value','EA_UNEMP_history_value','EA_EMPLOYMENT_history_value'],
   'CAD':['CAD GDP','CAD Retail','CAD Employment','CAD Unemployment']
 }},
 'series_checks':checks,
 'replay_static_guard':static,
 'hard_failures':hard_failures,
 'passed':len(hard_failures)==0,
 'decision':'PASS_NO_LOOKAHEAD_DETECTED' if not hard_failures else 'FAIL_LOOKAHEAD_GUARD',
 'guardrails':[
  'Availability is controlled by official release/first-release date, never by observation month/quarter.',
  'A series cannot vote at checkpoint cp unless its release date is <= cp.',
  'CAD forward-filled block state may only come from a latest official source checkpoint <= aggregate checkpoint.',
  'Any missing or unprovable release timing is a hard failure, not an assumed lag.'
 ],
 'limitations':[
  'This audit verifies date gating and chronology for the currently eligible PIT series only; withheld series remain excluded.',
  'It does not validate intraday release timestamps; checkpoints are daily-date resolution.',
  'CAD underlying first-release source identity/values were already validated in the canonical CAD PIT artifacts; this guard tests their aggregate checkpoint chronology.'
 ],
 'no_model_change':True
}
OUT.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':report['passed'],'hard_failures':hard_failures,'series':[{c['series']:c['pass']} for c in checks],'static':static},indent=2))
