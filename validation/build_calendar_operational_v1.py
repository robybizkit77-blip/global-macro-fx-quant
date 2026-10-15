#!/usr/bin/env python3
import json
from datetime import date, datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'live_data/sections/NATIVE_CB_DATA.json'
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
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return changed

def main():
    data=json.loads(SRC.read_text(encoding='utf-8'))
    today=date.today(); events=[]
    for ccy in ORDER:
        row=data.get(ccy) or {}; raw=row.get('next_meeting')
        if not raw: continue
        try: d=date.fromisoformat(raw)
        except ValueError: continue
        events.append({'date':raw,'ccy':ccy,'event_type':'CENTRAL_BANK_DECISION','title':f"{row.get('bank',ccy)} · decisione di politica monetaria",'bank':row.get('full_name') or row.get('bank'),'current_rate':row.get('rate'),'stance':row.get('stance'),'status':'UPCOMING' if d>=today else 'PAST','source_layer':'NATIVE_CB_DATA','quality':'OFFICIAL_SCHEDULE_FROM_CERTIFIED_CB_LAYER'})
    events.sort(key=lambda x:(x['date'],ORDER.index(x['ccy'])))
    future=[e for e in events if e['status']=='UPCOMING']
    core={'schema':'GMFQ_CALENDAR_OPERATIONAL_VIEW_V1','status':'ACTIVE_CB_OFFICIAL_ONLY','coverage':{'g8_total':8,'cb_schedule_available':len(events),'upcoming_cb_events':len(future)},'scope':{'central_bank_schedule':'ACTIVE_OFFICIAL','macro_release_schedule':'PENDING_SEPARATE_OFFICIAL_FEED','consensus':'NOT_INCLUDED_IN_V1'},'events':future}
    changed=stable_write(core)
    print(json.dumps({'status':'PASS','changed':changed,'events':len(future),'output':str(OUT.relative_to(ROOT))}))

if __name__=='__main__': main()
