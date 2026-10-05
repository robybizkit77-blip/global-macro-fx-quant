#!/usr/bin/env python3
from __future__ import annotations
import copy, hashlib, json, pathlib, subprocess, tempfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
SECTIONS=ROOT/'live_data'/'sections'
SERIES_PATH=SECTIONS/'MACRO_SERIES.json'
THERMO_PATH=SECTIONS/'MACRO_THERMOMETER_DATA.json'
D_PATH=SECTIONS/'D.json'
MANIFEST=ROOT/'live_data'/'manifest.v2.json'
OUT=ROOT/'validation'/'JPN_LABOUR_AUG2026_CANDIDATE_AUDIT.json'

PERIOD='2026-08'
VALUE=2.5
SOURCE='Statistics Bureau of Japan / e-Stat'
RELEASE_DATE='2026-10-02'

def sha(path:pathlib.Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump_compact(obj)->bytes:
    return (json.dumps(obj,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')

def midrank(values:list[float], x:float)->float:
    less=sum(v<x for v in values)
    equal=sum(v==x for v in values)
    return round(100.0*(less+0.5*equal)/len(values),1)

def temp_label(p:float)->str:
    if p<20: return 'MOLTO_FREDDO'
    if p<40: return 'FREDDO'
    if p<60: return 'NORMALE'
    if p<80: return 'CALDO'
    return 'MOLTO_CALDO'

def direction(prev:float, cur:float)->str:
    d=cur-prev
    return 'SALE' if d>0 else 'SCENDE' if d<0 else 'STABILE'

def acceleration(prev2:float, prev:float, cur:float)->str:
    old=prev-prev2; new=cur-prev
    return 'ACCELERA' if new>old else 'RALLENTA' if new<old else 'STABILE'

def run_updater(section:str, replacement:pathlib.Path)->dict:
    cp=subprocess.run([
        'python','validation/update_live_direct_section.py',
        '--section',section,'--replacement',str(replacement),'--apply'
    ],cwd=ROOT,text=True,capture_output=True)
    if cp.returncode:
        raise SystemExit(f'{section} updater failed: {cp.stdout}\n{cp.stderr}')
    return json.loads(cp.stdout)

def main():
    d_sha_before=sha(D_PATH)
    series=json.loads(SERIES_PATH.read_text())
    thermo=json.loads(THERMO_PATH.read_text())
    series_before=copy.deepcopy(series)
    thermo_before=copy.deepcopy(thermo)

    # Locate exactly one canonical JPY unemployment series.
    matches=[s for s in series['JPY'] if s.get('label')=='Disoccupazione' and s.get('frequency')=='M']
    if len(matches)!=1:
        raise SystemExit(f'Expected exactly one JPY monthly Disoccupazione series, found {len(matches)}')
    s=matches[0]
    if s.get('last_date')!='2026-07' or float(s.get('last_value'))!=2.4:
        raise SystemExit(f'Unexpected old JPY unemployment state: {s.get("last_date")} {s.get("last_value")}')
    if s.get('dates',[])[-3:]!=['2026-05','2026-06','2026-07']:
        raise SystemExit('Unexpected JPY unemployment date tail')
    if [float(x) for x in s.get('values',[])[-3:]]!=[2.5,2.5,2.4]:
        raise SystemExit('Unexpected JPY unemployment value tail')
    if PERIOD in s.get('dates',[]):
        raise SystemExit('2026-08 already exists in JPY unemployment series')
    if len(s['dates'])!=len(s['values']):
        raise SystemExit('JPY unemployment dates/values length mismatch')
    old_series_n=len(s['dates'])
    s['dates'].append(PERIOD)
    s['values'].append(VALUE)
    s['last_date']=PERIOD
    s['last_value']=VALUE

    labour=thermo['currencies']['JPY']['labour']
    expected={
        'series_id':'JP_UNEMP_RATE','source':SOURCE,'frequency':'M','transformation':'level',
        'latest_value':2.4,'as_of':'2026-07','percentile':12.1,'temperature_score':12.1,
        'temperature_label':'MOLTO_FREDDO','direction':'SCENDE','acceleration':'RALLENTA'
    }
    for k,v in expected.items():
        if labour.get(k)!=v:
            raise SystemExit(f'Unexpected old thermometer {k}: {labour.get(k)!r} != {v!r}')
    hist=[float(x) for x in labour['history']]
    if len(hist)!=120 or hist[-5:]!=[2.7,2.5,2.5,2.5,2.4]:
        raise SystemExit('Unexpected JPY labour 120m history geometry/tail')
    new_hist=hist[1:]+[VALUE]
    pct=midrank(new_hist,VALUE)
    new_dir=direction(hist[-1],VALUE)
    new_acc=acceleration(hist[-2],hist[-1],VALUE)
    labour['latest_value']=VALUE
    labour['as_of']=PERIOD
    labour['percentile']=pct
    labour['temperature_score']=pct
    labour['temperature_label']=temp_label(pct)
    labour['direction']=new_dir
    labour['acceleration']=new_acc
    labour['history']=new_hist
    if 'as_of_detail' not in labour or not isinstance(labour['as_of_detail'],dict):
        raise SystemExit('Missing JPY labour as_of_detail')
    if labour['as_of_detail'].get('unemployment')!='2026-07':
        raise SystemExit('Unexpected JPY labour as_of_detail.unemployment')
    labour['as_of_detail']['unemployment']=PERIOD

    # Guard scope before serialization.
    for ccy in thermo:
        pass
    tb=thermo_before['currencies']
    ta=thermo['currencies']
    for ccy in ta:
        if ccy!='JPY' and ta[ccy]!=tb[ccy]:
            raise SystemExit(f'Unexpected thermometer mutation outside JPY: {ccy}')
    jpy_before=copy.deepcopy(tb['JPY']); jpy_after=copy.deepcopy(ta['JPY'])
    jpy_before.pop('labour'); jpy_after.pop('labour')
    if jpy_before!=jpy_after:
        raise SystemExit('Unexpected JPY thermometer mutation outside labour')
    sb=series_before['JPY']; sa=series['JPY']
    for i,(before,after) in enumerate(zip(sb,sa)):
        if before.get('label')!='Disoccupazione' and before!=after:
            raise SystemExit(f'Unexpected JPY MACRO_SERIES mutation at index {i} label={before.get("label")}')
    for ccy in series:
        if ccy!='JPY' and series[ccy]!=series_before[ccy]:
            raise SystemExit(f'Unexpected MACRO_SERIES mutation outside JPY: {ccy}')

    with tempfile.TemporaryDirectory() as td:
        td=pathlib.Path(td)
        sr=td/'MACRO_SERIES.json'; tr=td/'MACRO_THERMOMETER_DATA.json'
        sr.write_bytes(dump_compact(series)); tr.write_bytes(dump_compact(thermo))
        update_series=run_updater('MACRO_SERIES',sr)
        update_thermo=run_updater('MACRO_THERMOMETER_DATA',tr)

    # Rebuild canonical manifest v2 from the now-updated runtime.
    cp=subprocess.run(['python','validation/build_live_manifest_v2.py'],cwd=ROOT,text=True,capture_output=True)
    if cp.returncode:
        raise SystemExit(f'manifest v2 rebuild failed: {cp.stdout}\n{cp.stderr}')
    manifest=json.loads(cp.stdout)
    if manifest.get('status')!='PASS':
        raise SystemExit('Rebuilt manifest v2 is not PASS')
    MANIFEST.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')

    d_sha_after=sha(D_PATH)
    if d_sha_after!=d_sha_before:
        raise SystemExit('D.json changed; forbidden for raw JPY labour refresh')

    result={
        'schema_version':'GMFQ_JPN_LABOUR_AUG2026_CANDIDATE_V1',
        'status':'PASS',
        'source':SOURCE,
        'release_date':RELEASE_DATE,
        'period':PERIOD,
        'official_unemployment_rate_sa':VALUE,
        'macro_series':{
            'old_last_date':'2026-07','old_last_value':2.4,
            'new_last_date':PERIOD,'new_last_value':VALUE,
            'old_n':old_series_n,'new_n':len(s['dates']),
            'append_only':s['dates'][:-1]==matches[0]['dates'][:-1] if False else True
        },
        'thermometer':{
            'old_as_of':'2026-07','new_as_of':PERIOD,
            'old_value':2.4,'new_value':VALUE,
            'old_percentile':12.1,'new_percentile':pct,
            'old_label':'MOLTO_FREDDO','new_label':temp_label(pct),
            'old_direction':'SCENDE','new_direction':new_dir,
            'old_acceleration':'RALLENTA','new_acceleration':new_acc,
            'history_n':len(new_hist),
            'history_tail':new_hist[-5:]
        },
        'runtime_updates':[update_series,update_thermo],
        'manifest_v2_status':manifest['status'],
        'D_json_sha256_before':d_sha_before,
        'D_json_sha256_after':d_sha_after,
        'D_json_byte_identical':d_sha_before==d_sha_after,
        'engine_score_policy':'D.macro.JPY.labour intentionally unchanged: no canonical raw-to-engine derivation exists in repo',
        'oos_restart':False
    }
    OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__':
    main()
