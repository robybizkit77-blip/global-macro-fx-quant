#!/usr/bin/env python3
import json
from datetime import date, datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CB=ROOT/'live_data/sections/NATIVE_CB_DATA.json'
MACRO=ROOT/'live_data/sections/MACRO_RELEASE_OFFICIAL_SEED_V1.json'
OUT=ROOT/'live_data/sections/CALENDAR_OPERATIONAL_VIEW.json'
ORDER=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']

def stable_write(core):
    old=None
    if OUT.exists():
        try: old=json.loads(OUT.read_text(encoding='utf-8'))
        except Exception: old=None
    old_core=dict(old or {}); old_core.pop('generated_at_utc',None)
    if old_core==core and old and old.get('generated_at_utc'):
        generated=old['generated_at_utc']; changed=False
    else:
        generated=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'); changed=True
    out=dict(core); out['generated_at_utc']=generated
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return changed

def main():
    cb=json.loads(CB.read_text(encoding='utf-8'))
    macro=json.loads(MACRO.read_text(encoding='utf-8'))
    today=date.today(); events=[]; cb_count=0; macro_count=0
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
        x=dict(e); x.update({'status':'UPCOMING','source_layer':'MACRO_RELEASE_OFFICIAL_SEED_V1','consensus_status':'NOT_PRESENT'})
        macro_count+=1; events.append(x)
    events.sort(key=lambda x:(x['date'],ORDER.index(x['ccy']) if x.get('ccy') in ORDER else 99,x.get('event_type','')))
    ccy_macro=sorted({e['ccy'] for e in events if e.get('source_layer')=='MACRO_RELEASE_OFFICIAL_SEED_V1'})
    core={'schema':'GMFQ_CALENDAR_OPERATIONAL_VIEW_V2','status':'ACTIVE_CB_PLUS_MACRO_OFFICIAL','coverage':{'g8_total':8,'cb_schedule_available':cb_count,'macro_ccy_coverage':len(ccy_macro),'upcoming_macro_events':macro_count,'upcoming_total_events':len(events)},'scope':{'central_bank_schedule':'ACTIVE_OFFICIAL','macro_release_schedule':'ACTIVE_OFFICIAL_VERIFIED_SEED','macro_release_currencies':ccy_macro,'consensus':'SEPARATE_SECONDARY_LAYER_NOT_PRESENT','core_score_impact':0},'events':events}
    changed=stable_write(core)
    print(json.dumps({'status':'PASS','changed':changed,'total_events':len(events),'macro_events':macro_count,'macro_ccy_coverage':len(ccy_macro),'output':str(OUT.relative_to(ROOT))}))

if __name__=='__main__': main()
