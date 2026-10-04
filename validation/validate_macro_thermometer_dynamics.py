from pathlib import Path
import json, math

ROOT=Path('.')
data=json.loads((ROOT/'live_data/sections/MACRO_THERMOMETER_DATA.json').read_text(encoding='utf-8'))

def direction(h):
    a=[float(x) for x in h if isinstance(x,(int,float))]
    if len(a)<2: return 'WITHHELD'
    d=a[-1]-a[-2]
    if abs(d)<1e-12: return 'STABILE'
    return 'SALE' if d>0 else 'SCENDE'

def acceleration(h):
    a=[float(x) for x in h if isinstance(x,(int,float))]
    if len(a)<3: return 'WITHHELD'
    d1=a[-1]-a[-2]; d0=a[-2]-a[-3]
    dd=d1-d0
    if abs(dd)<1e-12: return 'STABILE'
    return 'ACCELERA' if dd>0 else 'RALLENTA'

rows=[]
for c in ['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']:
    for k in ['inflation','labour']:
        x=data['currencies'][c][k]
        pred_d=direction(x.get('history',[])); pred_a=acceleration(x.get('history',[]))
        rows.append({'currency':c,'key':k,'actual_direction':x.get('direction'),'pred_direction':pred_d,'direction_match':x.get('direction')==pred_d,'actual_acceleration':x.get('acceleration'),'pred_acceleration':pred_a,'acceleration_match':x.get('acceleration')==pred_a})
out={'schema':'GMFQ_MACRO_THERMOMETER_DYNAMICS_VALIDATION_V1','rows':rows,'direction_matches':sum(r['direction_match'] for r in rows),'acceleration_matches':sum(r['acceleration_match'] for r in rows),'total':len(rows)}
out['status']='PASS' if out['direction_matches']==len(rows) and out['acceleration_matches']==len(rows) else 'FAIL'
(ROOT/'validation/MACRO_THERMOMETER_DYNAMICS_VALIDATION_2026-10-04.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out,indent=2))
if out['status']!='PASS': raise SystemExit(1)
