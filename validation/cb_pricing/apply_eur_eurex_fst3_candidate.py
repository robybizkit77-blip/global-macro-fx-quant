#!/usr/bin/env python3
"""Apply a validated EUR Eurex FST3 candidate to current checkout only."""
from __future__ import annotations
import argparse,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
OIS=ROOT/'live_data'/'sections'/'OIS_DATA.json'; NATIVE=ROOT/'live_data'/'sections'/'NATIVE_CB_DATA.json'; PAYLOAD=ROOT/'payload'/'part-00.txt'
OM=b'window.__GMFQ_DATA.OIS_DATA='; NM=b'window.__GMFQ_DATA.NATIVE_CB_DATA='

def extract(raw,marker):
    p=raw.find(marker)
    if p<0: raise SystemExit(f'missing marker {marker!r}')
    start=p+len(marker); text=raw[start:].decode('utf-8'); obj,n=json.JSONDecoder().raw_decode(text); end=start+len(text[:n].encode('utf-8')); cur=end
    while raw[cur:cur+1] in (b' ',b'\t',b'\r',b'\n'): cur+=1
    if raw[cur:cur+1]!=b';': raise SystemExit('runtime assignment missing semicolon')
    return obj,start,end

def replace(raw,marker,obj):
    _,s,e=extract(raw,marker); enc=json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode(); out=raw[:s]+enc+raw[e:]
    if extract(out,marker)[0]!=obj: raise SystemExit('runtime roundtrip mismatch')
    return out

def r4(x):return round(float(x),4)
def r1(x):return round(float(x),1)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--candidate',required=True,type=pathlib.Path); a=ap.parse_args(); c=json.loads(a.candidate.read_text(encoding='utf-8'))
    if c.get('schema')!='GMFQ_CB_PRICING_CANDIDATE_V1' or c.get('currency')!='EUR' or c.get('status') not in ('READY_FOR_DRY_RUN','READY_FOR_CONTROLLED_ACTIVATION_PROOF'): raise SystemExit('invalid EUR candidate')
    req=('source_validated','asof_validated','meeting_path_validated','policy_rate_validated','changes_validated','current_real','previous_real','week_real','no_interpolation','homogeneous_contracts')
    if not all(c.get('validation',{}).get(k) is True for k in req): raise SystemExit('EUR candidate validation incomplete')
    if c['status']=='READY_FOR_DRY_RUN' and c['validation'].get('source_registry_authorized') is not True: raise SystemExit('ACTIVE EUR candidate lacks registry authorization')
    if c['status']=='READY_FOR_CONTROLLED_ACTIVATION_PROOF' and c['validation'].get('controlled_activation_only') is not True: raise SystemExit('activation proof lacks explicit bootstrap authorization')
    o=json.loads(OIS.read_text(encoding='utf-8')); n=json.loads(NATIVE.read_text(encoding='utf-8')); bo=json.loads(json.dumps(o)); bn=json.loads(json.dumps(n)); h=c['horizons']; cmap=c['contract_mapping']
    e=o['currencies']['EUR']; e.update({'status':'ACTIVE','as_of':c['as_of'],'source':c['source'],'source_url':c['source_url'],'source_meta':{'official_public':True,'instrument':c['instrument'],'quotation':c['quotation'],'horizon_mapping':f"{cmap['3m']} / {cmap['6m']} / {cmap['12m']} direct Eurex quarterly buckets; no interpolation",'contract_mapping':cmap},'policy_rate':c['policy_rate'],'meetings':c['meeting_path'],'horizons':{k:{'rate':r4(h[k]['rate']),'change_1d_bp':r1(h[k]['change_1d_bp']),'change_1w_bp':r1(h[k]['change_1w_bp']),'policy_delta_bp':r1(h[k]['policy_delta_bp'])} for k in ('3m','6m','12m')},'cuts_hikes_priced':{f'{k}_bp':r1(h[k]['policy_delta_bp']) for k in ('3m','6m','12m')},'direction':c['direction'],'change_direction_1d':c['change_direction_1d'],'change_direction_1w':c['change_direction_1w'],'validation':{k:v for k,v in c['validation'].items() if k not in ('runtime_mutated','payload_mutated','controlled_activation_only','source_registry_authorized')},'provenance':{'method':c['provenance']['method'],'collector':c['provenance']['collector'],'request_urls':c['provenance']['request_urls'],'weekly_reference_rule':c['provenance']['weekly_reference_rule'],'policy_metadata':c['provenance']['policy_metadata'],'observations':c['observations']}})
    ng=n['EUR']; vals={k:r4(h[k]['rate']) for k in ('3m','6m','12m')}
    ng['pricing_tier']='COMPLETO_OFFICIAL_EUREX_ESTR_HISTORY'; ng['pricing_status']=f"Eurex official €STR futures: 3M {vals['3m']:.4f}%; 6M {vals['6m']:.4f}%; 12M {vals['12m']:.4f}%."; ng['market_3m']=f"{vals['3m']:.4f}%"; ng['market_6m']=f"{vals['6m']:.4f}%"; ng['market_12m']=f"{vals['12m']:.4f}%"; ng['market_pricing']={'as_of':c['as_of'],'instrument':c['instrument'],'quality':'COMPLETO_OFFICIAL_EUREX_ESTR_HISTORY','h3m':vals['3m'],'h6m':vals['6m'],'h12m':vals['12m'],'near_term':'Official Eurex FST3 settlements; current, 1D and official weekly-reference history validated.','source':c['source'],'source_url':c['source_url'],'note':c['provenance']['method'],'freshness_status':'CURRENT_VALIDATED'}
    co=[k for k in o['currencies'] if o['currencies'][k]!=bo['currencies'][k]]; cn=[k for k in n if n[k]!=bn[k]]
    if co not in ([],['EUR']) or cn not in ([],['EUR']): raise SystemExit(f'non-EUR semantic delta OIS={co} NATIVE={cn}')
    raw=PAYLOAD.read_bytes(); ro=extract(raw,OM)[0]; rn=extract(raw,NM)[0]
    if ro!=bo or rn!=bn: raise SystemExit('live sections and payload differ before apply')
    if not co and not cn:
        print(json.dumps({'status':'NO_CHANGE','scope':{'OIS':co,'NATIVE_CB':cn},'as_of':c['as_of'],'publication':False},indent=2)); return
    OIS.write_text(json.dumps(o,ensure_ascii=False,separators=(',',':')),encoding='utf-8'); NATIVE.write_text(json.dumps(n,ensure_ascii=False,separators=(',',':')),encoding='utf-8'); PAYLOAD.write_bytes(replace(replace(raw,OM,o),NM,n))
    print(json.dumps({'status':'PASS','scope':{'OIS':co,'NATIVE_CB':cn},'as_of':c['as_of'],'changed_payload_part':0,'publication':False},indent=2))
if __name__=='__main__': main()
