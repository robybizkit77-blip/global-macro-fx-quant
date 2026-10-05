#!/usr/bin/env python3
import json, math
from pathlib import Path

p=Path('live_data/sections/MACRO_THERMOMETER_DATA.json')
data=json.loads(p.read_text())
rows=[]
for ccy,c in data['currencies'].items():
    for dim in ('inflation','labour'):
        s=c[dim]
        h=s.get('history',[])
        if len(h)<3: continue
        a,b,x=h[-3],h[-2],h[-1]
        d1=x-b; d0=b-a
        candidates={
            'direction_last_delta': 'SALE' if d1>0 else 'SCENDE' if d1<0 else 'STABILE',
            'accel_signed_delta_change': 'ACCELERA' if d1>d0 else 'RALLENTA' if d1<d0 else 'STABILE',
            'accel_abs_delta_change': 'ACCELERA' if abs(d1)>abs(d0) else 'RALLENTA' if abs(d1)<abs(d0) else 'STABILE',
            'accel_same_direction_magnitude': (
                'STABILE' if d1==d0 else
                'ACCELERA' if d1*d0>=0 and abs(d1)>abs(d0) else
                'RALLENTA' if d1*d0>=0 and abs(d1)<abs(d0) else
                'ACCELERA' if d1!=0 and d0==0 else
                'RALLENTA'
            )
        }
        rows.append({
            'ccy':ccy,'dimension':dim,'frequency':s.get('frequency'),'history_n':len(h),
            'last3':[a,b,x],'d_prev':d0,'d_last':d1,
            'stored_direction':s.get('direction'),'stored_acceleration':s.get('acceleration'),
            'candidates':candidates,
            'matches':{k:(v==s.get('direction') if k=='direction_last_delta' else v==s.get('acceleration')) for k,v in candidates.items()}
        })

summary={}
for key in ['direction_last_delta','accel_signed_delta_change','accel_abs_delta_change','accel_same_direction_magnitude']:
    summary[key]={'matches':sum(r['matches'][key] for r in rows),'total':len(rows)}

report={'schema_version':'GMFQ_MACRO_THERMOMETER_DYNAMICS_REVERSE_AUDIT_V1','summary':summary,'rows':rows,
        'history_lengths':sorted(set((r['frequency'],r['history_n']) for r in rows))}
Path('validation/MACRO_THERMOMETER_DYNAMICS_REVERSE_AUDIT_2026-10-05.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(report,indent=2,ensure_ascii=False))
