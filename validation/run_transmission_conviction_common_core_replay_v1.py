#!/usr/bin/env python3
from __future__ import annotations
import csv, io, json, math, statistics, urllib.request
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'validation/TRANSMISSION_CONVICTION_COMMON_CORE_REPLAY_V1_2026-10-07.json'
ENGINE='ff52198a75cc67f7dae96fc2bbf65623f170791c'
FP='3356baf0'
PIN='e9862cba3f748da121e34d12f8eb64144568d46c'
BASE=f'https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/{PIN}/'
JPY_BRANCH='research-jpy-rates-transmission-v1-2026-10-07'
JPY_BASE=f'https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/{JPY_BRANCH}/'
CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']

def get_text(url):
    req=urllib.request.Request(url,headers={'User-Agent':'GMFQ-research'})
    with urllib.request.urlopen(req,timeout=60) as r:return r.read().decode('utf-8-sig')
def get_json(url):return json.loads(get_text(url))
def sign(x):return 1 if x>0 else -1 if x<0 else 0

def load_fx():
    rows=list(csv.DictReader(io.StringIO(get_text(BASE+'history/pit_v1/FX_G8_DAILY_ECB_2016_2026.csv'))))
    for r in rows:r['_d']=date.fromisoformat(r['date'])
    return rows
FX=load_fx(); FXD=[r['_d'] for r in FX]

def next_idx(dt):
    for i,d in enumerate(FXD):
        if d>dt:return i
    return None

def idx_on_or_after(dt):
    for i,d in enumerate(FXD):
        if d>=dt:return i
    return None

def pairret(c,o,i0,i1):
    a=c+o;b=o+c
    if a in FX[i0] and FX[i0].get(a) and FX[i1].get(a):return math.log(float(FX[i1][a])/float(FX[i0][a]))
    if b in FX[i0] and FX[i0].get(b) and FX[i1].get(b):return -math.log(float(FX[i1][b])/float(FX[i0][b]))
    raise KeyError((c,o,FX[i0]['date'],FX[i1]['date']))

def basket(c,i0,i1):return sum(pairret(c,o,i0,i1) for o in CCYS if o!=c)/7

def summarize(vals):
    vals=[x for x in vals if x is not None]
    if not vals:return {'n':0,'hit_rate':None,'mean':None,'median':None}
    return {'n':len(vals),'hit_rate':sum(x>0 for x in vals)/len(vals),'mean':sum(vals)/len(vals),'median':statistics.median(vals)}

def classify(macro,front,price):
    aligned=sum(x==macro for x in (front,price) if x!=0)
    divergent=sum(x==-macro for x in (front,price) if x!=0)
    neutral=sum(x==0 for x in (front,price))
    if aligned==2 and divergent==0:return 'MEDIUM'
    return 'LOW'

def price_dir(currency,macro,checkpoint,entry_date):
    i0=next_idx(date.fromisoformat(checkpoint)); i1=idx_on_or_after(date.fromisoformat(entry_date))
    if i0 is None or i1 is None or i1<=i0:return 0,None
    raw=basket(currency,i0,i1)
    return sign(raw),macro*raw

def from_usd():
    src=get_json(BASE+'validation/USD_FED_REACTION_STATE_V1_2026-10-06.json')
    out=[]
    for r in src['rows']:
        m=int(r.get('joint_direction',0))
        if m not in (-1,1) or r.get('usd_basket_20d') is None:continue
        p,_=price_dir('USD',m,r['checkpoint'],r['fx_entry_date'])
        f=int(r['rates_direction'])
        out.append({'currency':'USD','checkpoint':r['checkpoint'],'macro_direction':m,'front_end_direction':f,'price_direction':p,'conviction':classify(m,f,p),'signed_20d':m*float(r['usd_basket_20d'])})
    return out

def from_gbp():
    src=get_json(BASE+'validation/GBP_FULL_REACTION_STATE_VNEXT_V1_2026-10-06.json')
    out=[]
    for r in src['rows']:
        m=int(r.get('domestic_direction',0))
        if m not in (-1,1) or r.get('signed_20d') is None:continue
        p,_=price_dir('GBP',m,r['checkpoint'],r['fx_entry_date'])
        f=int(r['rates_direction'])
        out.append({'currency':'GBP','checkpoint':r['checkpoint'],'macro_direction':m,'front_end_direction':f,'price_direction':p,'conviction':classify(m,f,p),'signed_20d':float(r['signed_20d'])})
    return out

def from_cad():
    src=get_json(BASE+'validation/CAD_FULL_REACTION_STATE_VNEXT_V2_2026-10-06.json')
    out=[]
    for r in src['rows']:
        m=int(r.get('macro_polarity',0))
        if m not in (-1,1) or r.get('cad_basket_20d') is None:continue
        p,_=price_dir('CAD',m,r['checkpoint'],r['fx_entry_date'])
        f=int(r['rates_direction'])
        out.append({'currency':'CAD','checkpoint':r['checkpoint'],'macro_direction':m,'front_end_direction':f,'price_direction':p,'conviction':classify(m,f,p),'signed_20d':m*float(r['cad_basket_20d'])})
    return out

def from_jpy():
    replay=get_json(BASE+'validation/JPY_REACTION_FUNCTION_REPLAY_V1_2026-10-06.json')
    rates=list(csv.DictReader(io.StringIO(get_text(JPY_BASE+'history/pit_v1/JPY_MOF_JGB_2Y_DAILY_2018_2023.csv'))))
    rs=[]
    for r in rates:
        try:rs.append((date.fromisoformat(r['date']),float(r['jpy_mof_jgb_2y_pct'])))
        except:pass
    rs.sort()
    out=[]
    for s in replay['directional_samples']:
        m=int(s['jpy_polarity']); cp=date.fromisoformat(s['checkpoint'])
        post=[x for x in rs if x[0]>cp]
        if len(post)<6:continue
        rd=sign(post[5][1]-post[0][1]); rend=post[5][0]
        i0=next_idx(cp); ie=next_idx(rend)
        if i0 is None or ie is None or ie<=i0 or ie+20>=len(FX):continue
        p=sign(basket('JPY',i0,ie)); signed20=m*basket('JPY',ie,ie+20)
        out.append({'currency':'JPY','checkpoint':s['checkpoint'],'macro_direction':m,'front_end_direction':rd,'price_direction':p,'conviction':classify(m,rd,p),'signed_20d':signed20})
    return out

def chronological_oos(rows):
    out=[]
    for c in sorted(set(r['currency'] for r in rows)):
        rr=sorted([r for r in rows if r['currency']==c],key=lambda x:x['checkpoint'])
        cut=int(len(rr)*0.4)
        for r in rr[cut:]:
            z=dict(r);z['oos']=True;out.append(z)
    return out

def stats_by_conv(rows):
    return {k:summarize([r['signed_20d'] for r in rows if r['conviction']==k]) for k in ('MEDIUM','LOW')}

def by_currency(rows):
    return {c:stats_by_conv([r for r in rows if r['currency']==c]) for c in sorted(set(r['currency'] for r in rows))}

def main():
    rows=from_usd()+from_gbp()+from_cad()+from_jpy()
    oos=chronological_oos(rows)
    full=stats_by_conv(rows); pooled=stats_by_conv(oos)
    monotonic_full=(full['MEDIUM']['mean'] is not None and full['LOW']['mean'] is not None and full['MEDIUM']['mean']>full['LOW']['mean'] and full['MEDIUM']['hit_rate']>full['LOW']['hit_rate'])
    monotonic_oos=(pooled['MEDIUM']['mean'] is not None and pooled['LOW']['mean'] is not None and pooled['MEDIUM']['mean']>pooled['LOW']['mean'] and pooled['MEDIUM']['hit_rate']>pooled['LOW']['hit_rate'])
    payload={
      'schema':'GMFQ_TRANSMISSION_CONVICTION_COMMON_CORE_REPLAY_V1','status':'PASS_DIAGNOSTIC_NOT_PROMOTED','created_at':'2026-10-07',
      'engine_baseline':{'commit':ENGINE,'rules_fingerprint':FP,'modified':False},
      'scope':'Common-core replay across USD/GBP/CAD/JPY using only post-release 5-observation front-end direction plus contemporaneous FX price confirmation; outcome is subsequent 20-market-day direction-adjusted basket return.',
      'important_limitation':'HIGH is not testable in the common core because historical CB-implication and relative-2Y layers are not uniformly certified for all currencies/events. This replay tests MEDIUM (both common layers aligned) versus LOW only.',
      'timing':{'classification_window':'strictly post-release through 5th front-end observation','fx_outcome':'starts after classification window','oos':'per-currency first 40% chronology excluded'},
      'guardrails':['no threshold tuning','no weights','no macro-bias override','direction-adjusted signed returns only','JPY timing rebuilt to match USD/GBP/CAD','no engine/live-data/OOS-baseline changes'],
      'counts':{'all':len(rows),'oos':len(oos),'by_currency':{c:sum(r['currency']==c for r in rows) for c in sorted(set(r['currency'] for r in rows))}},
      'full_sample':full,'pooled_oos':pooled,'full_monotonic_medium_gt_low':monotonic_full,'oos_monotonic_medium_gt_low':monotonic_oos,
      'oos_by_currency':by_currency(oos),'rows':rows,
      'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False
    }
    OUT.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:payload[k] for k in ['status','counts','full_sample','pooled_oos','full_monotonic_medium_gt_low','oos_monotonic_medium_gt_low','oos_by_currency']},indent=2))
if __name__=='__main__':main()
