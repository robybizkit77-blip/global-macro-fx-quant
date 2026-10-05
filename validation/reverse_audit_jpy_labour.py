#!/usr/bin/env python3
import json
from pathlib import Path

series = json.loads(Path('live_data/sections/MACRO_SERIES.json').read_text())['JPY']
thermo = json.loads(Path('live_data/sections/MACRO_THERMOMETER_DATA.json').read_text())['currencies']['JPY']['labour']

summary=[]
for i,s in enumerate(series):
    summary.append({
        'index':i,
        'name':s.get('name'),
        'label':s.get('label'),
        'series_id':s.get('series_id'),
        'source':s.get('source'),
        'frequency':s.get('frequency'),
        'transformation':s.get('transformation'),
        'last_date':s.get('last_date'),
        'last_value':s.get('last_value'),
        'n_dates':len(s.get('dates',[])),
        'n_values':len(s.get('values',[])),
    })

hist=thermo['history']
x=thermo['latest_value']
less=sum(v < x for v in hist)
le=sum(v <= x for v in hist)
eq=sum(v == x for v in hist)
n=len(hist)
methods={
    'strict_less_pct':100*less/n,
    'less_equal_pct':100*le/n,
    'midrank_pct':100*(less+0.5*eq)/n,
    'strict_less_over_n_minus_1':100*less/(n-1) if n>1 else None,
    'midrank_over_n_minus_1':100*(less+0.5*eq)/(n-1) if n>1 else None,
}
report={
    'schema_version':'GMFQ_JPY_LABOUR_REVERSE_AUDIT_V1',
    'series_summary':summary,
    'thermometer':{
        'latest_value':x,
        'as_of':thermo.get('as_of'),
        'stored_percentile':thermo.get('percentile'),
        'direction':thermo.get('direction'),
        'acceleration':thermo.get('acceleration'),
        'history_n':n,
        'last5':hist[-5:],
        'rank_counts':{'less':less,'equal':eq,'less_equal':le},
        'candidate_percentile_methods':methods,
    }
}
print(json.dumps(report, indent=2, ensure_ascii=False))
Path('validation/JPN_LABOUR_REVERSE_AUDIT_2026-10-05.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
