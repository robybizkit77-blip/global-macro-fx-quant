#!/usr/bin/env python3
import json
from datetime import date, datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'live_data/sections/NATIVE_CB_DATA.json'
OUT=ROOT/'live_data/sections/CALENDAR_OPERATIONAL_VIEW.json'

ORDER=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']

def main():
    data=json.loads(SRC.read_text(encoding='utf-8'))
    today=date.today()
    events=[]
    for ccy in ORDER:
        row=data.get(ccy) or {}
        raw=row.get('next_meeting')
        if not raw:
            continue
        try:
            d=date.fromisoformat(raw)
        except ValueError:
            continue
        events.append({
            'date':raw,
            'ccy':ccy,
            'event_type':'CENTRAL_BANK_DECISION',
            'title':f"{row.get('bank',ccy)} · decisione di politica monetaria",
            'bank':row.get('full_name') or row.get('bank'),
            'current_rate':row.get('rate'),
            'stance':row.get('stance'),
            'status':'UPCOMING' if d>=today else 'PAST',
            'source_layer':'NATIVE_CB_DATA',
            'quality':'OFFICIAL_SCHEDULE_FROM_CERTIFIED_CB_LAYER'
        })
    events.sort(key=lambda x:(x['date'], ORDER.index(x['ccy'])))
    future=[e for e in events if e['status']=='UPCOMING']
    out={
        'schema':'GMFQ_CALENDAR_OPERATIONAL_VIEW_V1',
        'status':'ACTIVE_CB_OFFICIAL_ONLY',
        'generated_at_utc':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        'coverage':{'g8_total':8,'cb_schedule_available':len(events),'upcoming_cb_events':len(future)},
        'scope':{
            'central_bank_schedule':'ACTIVE_OFFICIAL',
            'macro_release_schedule':'PENDING_SEPARATE_OFFICIAL_FEED',
            'consensus':'NOT_INCLUDED_IN_V1'
        },
        'events':future
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','events':len(future),'output':str(OUT.relative_to(ROOT))}))

if __name__=='__main__':
    main()
