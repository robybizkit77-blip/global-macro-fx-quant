#!/usr/bin/env python3
import json
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from refresh_macro_consensus_secondary_v1 import series_compatible

ROOT=Path(__file__).resolve().parents[1]
CB=ROOT/'live_data/sections/NATIVE_CB_DATA.json'
MACRO=ROOT/'live_data/sections/MACRO_RELEASE_OFFICIAL_SEED_V1.json'
CONSENSUS=ROOT/'live_data/sections/MACRO_CONSENSUS_SECONDARY_V1.json'
OUT=ROOT/'live_data/sections/CALENDAR_OPERATIONAL_VIEW.json'
ORDER=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']

def stable_write(core, now=None):
    """Preserve content vintage while recording a separate successful daily check.

    The check stamp is refreshed at most once per Rome calendar date if the
    source content is identical, avoiding repeated commits and publication
    churn. No unchanged market signal is presented as newly generated.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("aware UTC check instant required")
    now = now.astimezone(timezone.utc)
    now_str = now.isoformat().replace('+00:00', 'Z')
    prior = None
    if OUT.exists():
        try:
            prior = json.loads(OUT.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            prior = None
    prior_core = dict(prior or {})
    prior_core.pop('generated_at_utc', None)
    prior_core.pop('last_checked_at_utc', None)
    content_changed = prior_core != core or not (prior or {}).get('generated_at_utc')
    generated = now_str if content_changed else prior['generated_at_utc']
    prev_check = (prior or {}).get('last_checked_at_utc')
    try:
        parsed = datetime.fromisoformat(prev_check.replace('Z', '+00:00'))
        prior_checked_today = (
            parsed.tzinfo is not None
            and parsed.astimezone(ZoneInfo('Europe/Rome')).date()
            == now.astimezone(ZoneInfo('Europe/Rome')).date()
            and parsed <= now
        )
    except (AttributeError, TypeError, ValueError):
        prior_checked_today = False
    checked = prev_check if (not content_changed and prior_checked_today) else now_str
    out = dict(core)
    out['generated_at_utc'] = generated
    out['last_checked_at_utc'] = checked
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return content_changed

def main():
    cb=json.loads(CB.read_text(encoding='utf-8'))
    macro=json.loads(MACRO.read_text(encoding='utf-8'))
    consensus=json.loads(CONSENSUS.read_text(encoding='utf-8')) if CONSENSUS.exists() else {'status':'MISSING','events':[]}
    cmap={r.get('event_key'):r for r in consensus.get('events',[]) if r.get('event_key')}
    today=date.today(); events=[]; cb_count=0; macro_count=0; consensus_available=0; previous_only=0
    for ccy in ORDER:
        row=cb.get(ccy) or {}; raw=row.get('next_meeting')
        if raw:
            try: d=date.fromisoformat(raw)
            except ValueError: d=None
            if d and d>=today:
                cb_count+=1
                events.append({'date':raw,'ccy':ccy,'event_type':'CENTRAL_BANK_DECISION','title':f"{row.get('bank',ccy)} · decisione di politica monetaria",'bank':row.get('full_name') or row.get('bank'),'current_rate':row.get('rate'),'stance':row.get('stance'),'status':'UPCOMING','source_layer':'NATIVE_CB_DATA','quality':'OFFICIAL_SCHEDULE_FROM_CERTIFIED_CB_LAYER','importance':'HIGH','consensus_status':'NOT_APPLICABLE'})
    for e in macro.get('events',[]):
        try: d=date.fromisoformat(e['date'])
        except Exception: continue
        if d<today: continue
        key='|'.join([str(e.get('ccy','')),str(e.get('date','')),str(e.get('event_type','')),str(e.get('title',''))])
        c=cmap.get(key)
        # The persisted secondary JSON may predate an improved matcher.
        # Revalidate its original provider indicator when publishing, so a
        # national or unrelated same-day statistic cannot leak into Pages.
        if c and not series_compatible(e, {'event':c.get('provider_event')}):
            c=None
        cstatus=(c or {}).get('status','NOT_PRESENT')
        if cstatus=='AVAILABLE': consensus_available+=1
        elif cstatus=='PREVIOUS_ONLY': previous_only+=1
        x=dict(e); x.update({'status':'UPCOMING','source_layer':'MACRO_RELEASE_OFFICIAL_SEED_V1','consensus_status':cstatus})
        if c:
            x.update({'consensus':c.get('consensus'),'previous':c.get('previous'),'consensus_unit':c.get('unit'),
                      'consensus_provider':c.get('provider'),'consensus_confidence':c.get('confidence_grade'),
                      'consensus_provider_last_update':c.get('provider_last_update'),'consensus_official_date_overridden':False})
        macro_count+=1; events.append(x)
    events.sort(key=lambda x:(x['date'],ORDER.index(x['ccy']) if x.get('ccy') in ORDER else 99,x.get('event_type','')))
    ccy_macro=sorted({e['ccy'] for e in events if e.get('source_layer')=='MACRO_RELEASE_OFFICIAL_SEED_V1'})
    if consensus_available:
        consensus_scope='SECONDARY_ACTIVE_PARTIAL'
    elif previous_only:
        consensus_scope='SECONDARY_PREVIOUS_ONLY'
    elif consensus.get('provider'):
        consensus_scope='SECONDARY_PROVIDER_READY_NO_VALUES'
    else:
        consensus_scope='SEPARATE_SECONDARY_LAYER_NOT_PRESENT'
    core={'schema':'GMFQ_CALENDAR_OPERATIONAL_VIEW_V3','status':'ACTIVE_CB_PLUS_MACRO_OFFICIAL_WITH_SECONDARY_CONTEXT',
          'coverage':{'g8_total':8,'cb_schedule_available':cb_count,'macro_ccy_coverage':len(ccy_macro),
                      'upcoming_macro_events':macro_count,'upcoming_total_events':len(events),
                      'consensus_available_events':consensus_available,'previous_only_events':previous_only},
          'scope':{'central_bank_schedule':'ACTIVE_OFFICIAL','macro_release_schedule':'ACTIVE_OFFICIAL_VERIFIED_SEED',
                   'macro_release_currencies':ccy_macro,'consensus':consensus_scope,
                   'consensus_provider':consensus.get('provider'),'consensus_context_only':True,
                   'consensus_never_changes_official_date':True,'core_score_impact':0},'events':events}
    changed=stable_write(core)
    print(json.dumps({'status':'PASS','changed':changed,'total_events':len(events),'macro_events':macro_count,
                      'macro_ccy_coverage':len(ccy_macro),'consensus_available':consensus_available,
                      'previous_only':previous_only,'output':str(OUT.relative_to(ROOT))}))

if __name__=='__main__': main()
