#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, pathlib, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
PARTS=sorted((ROOT/'payload').glob('part-*.txt'))
SPECS={
 'V247_COT_STORIES':{
   'prefix':'window.__GMFQ_DATA.V247_COT_STORIES=',
   'section':ROOT/'live_data'/'sections'/'V247_COT_STORIES.json'
 },
 'RATES_AUDIT_METADATA':{
   'prefix':'window.__GMFQ_DATA.RATES_AUDIT_METADATA=',
   'section':ROOT/'live_data'/'sections'/'RATES_AUDIT_METADATA.json'
 }
}
CCY_COT={'EUR','GBP','JPY','CHF','AUD','NZD','CAD','USD'}
CCY_RATES={'USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'}

def validate_cot(d:dict)->None:
    if set(d)!=CCY_COT: raise ValueError('COT output must contain exactly 8 G8 currencies')
    req={'signal','today','w4','w1','why','funds','funds_detail','price','price_detail'}
    for c,x in d.items():
        if set(x)!=req: raise ValueError(f'{c}: invalid COT story fields')
        if x['price']!='WITHHELD': raise ValueError(f'{c}: price must remain WITHHELD without separately validated price input')
        if 'open interest' in x['funds_detail'].lower(): raise ValueError(f'{c}: orphan open interest must not be injected')
        if x['signal'] not in {'EXTREME LONG','EXTREME SHORT','NEUTRALE'}: raise ValueError(f'{c}: invalid signal')

def validate_rates(d:dict)->None:
    if d.get('schema')!='GMFQ_RATES_AUDIT_METADATA_V1': raise ValueError('Invalid rates metadata schema')
    exp=d.get('expected_rates',{}); rates=d.get('rates',{})
    if set(exp)!=CCY_RATES or set(rates)!=CCY_RATES: raise ValueError('Rates metadata must contain exactly 8 G8 currencies')
    for c in CCY_RATES:
        if rates[c].get('current_as_of')!=exp[c]: raise ValueError(f'{c}: current_as_of != expected_rates')
        if not rates[c].get('status') or not rates[c].get('action') or not rates[c].get('reason'): raise ValueError(f'{c}: incomplete rates metadata')

def locate(parts:list[str],prefix:str):
    runtime=''.join(parts)
    positions=[]; at=0
    while True:
        p=runtime.find(prefix,at)
        if p<0: break
        positions.append(p); at=p+1
    if len(positions)!=1: raise ValueError(f'Expected exactly one assignment prefix, found {len(positions)}: {prefix}')
    p=positions[0]; json_start=p+len(prefix)
    obj,used=json.JSONDecoder().raw_decode(runtime[json_start:])
    json_end=json_start+used
    if json_end>=len(runtime) or runtime[json_end]!=';': raise ValueError('Derived assignment missing trailing semicolon')
    end=json_end
    boundaries=[]; off=0
    for i,t in enumerate(parts):
        boundaries.append((off,off+len(t),i)); off+=len(t)
    containing=[i for lo,hi,i in boundaries if p>=lo and end<hi]
    if len(containing)!=1: raise ValueError('Derived assignment spans payload parts; refusing unsafe replacement')
    i=containing[0]; lo=boundaries[i][0]
    return obj,i,p-lo,end-lo

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--cot')
    ap.add_argument('--rates')
    ap.add_argument('--apply',action='store_true')
    a=ap.parse_args()
    requested=[]
    if a.cot: requested.append(('V247_COT_STORIES',pathlib.Path(a.cot)))
    if a.rates: requested.append(('RATES_AUDIT_METADATA',pathlib.Path(a.rates)))
    if not requested: raise SystemExit('Provide --cot and/or --rates')
    part_text=[p.read_text() for p in PARTS]
    changes=[]
    section_changes=[]
    for key,path in requested:
        new=json.loads(path.read_text())
        validate_cot(new) if key=='V247_COT_STORIES' else validate_rates(new)
        current,part_idx,start,end=locate(part_text,SPECS[key]['prefix'])
        payload=json.dumps(new,separators=(',',':'),ensure_ascii=False)
        prefix=SPECS[key]['prefix']
        replacement=prefix+payload
        old_fragment=part_text[part_idx][start:end]
        if not old_fragment.startswith(prefix): raise ValueError(f'{key}: assignment anchor mismatch')
        part_text[part_idx]=part_text[part_idx][:start]+replacement+part_text[part_idx][end:]
        changes.append({'section':key,'part':part_idx,'runtime_changed':current!=new,'old_json_bytes':len(json.dumps(current,separators=(',',':'),ensure_ascii=False).encode()),'new_json_bytes':len(payload.encode())})
        section_changes.append((SPECS[key]['section'],new))
    changed_parts=sorted({x['part'] for x in changes if x['runtime_changed']})
    if a.apply:
        for i in changed_parts: PARTS[i].write_text(part_text[i])
        for path,new in section_changes: path.write_text(json.dumps(new,separators=(',',':'),ensure_ascii=False)+'\n')
    print(json.dumps({'status':'PASS','apply':a.apply,'changes':changes,'changed_payload_parts':changed_parts,'policy':{'cot_orphan_open_interest':'OMITTED_NOT_INFERRED','price_confirmation':'WITHHELD_UNLESS_SEPARATELY_VALIDATED'}},indent=2,ensure_ascii=False))
    return 0

if __name__=='__main__': sys.exit(main())
