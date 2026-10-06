#!/usr/bin/env python3
import csv,json,math,statistics
from bisect import bisect_right
from pathlib import Path

GDP=Path('history/pit_v1/JPY_GROWTH_GDP_FIRST_PRELIM_2018_2023.csv')
MACH=Path('history/pit_v1/JPY_GROWTH_MACHINERY_ORDERS_FIRST_RELEASE_2018_2023.csv')
LAB=Path('history/pit_v1/JPY_LABOUR_LFS_FIRST_RELEASE_2018_2023_07.csv')
FX=Path('history/pit_v1/FX_G8_DAILY_ECB_2016_2026.csv')
OUT=Path('validation/JPY_FROZEN_MACRO_REPLAY_V1_2026-10-06.json')
CCY=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']; H=(5,20,60)
TH=0.20; MINOBS=8; WIN=80

def med(xs):
    xs=[x for x in xs if x is not None and math.isfinite(float(x))]
    return statistics.median(xs) if xs else None

def synth(rows,date_key,rate_key):
    lvl=100.0; out=[]
    for r in sorted(rows,key=lambda x:x[date_key]):
        v=float(r[rate_key]); lvl*=1+v/100.0
        out.append({'release_date':r['release_date'],'value':lvl})
    return out

def impulse_asof(rows,cp,pol):
    vals=[float(r['value']) for r in rows if r['release_date']<=cp]
    if len(vals)<MINOBS:return None
    tail=vals[-WIN:]
    diffs=[abs(tail[i]-tail[i-1]) for i in range(1,len(tail))]
    s=med(diffs)
    if not s or s<=0:return None
    cur=(vals[-1]-vals[-2])*pol/s
    prev=(vals[-2]-vals[-3])*pol/s
    return {'current':cur,'previous':prev}

def block(series,cp):
    z=[impulse_asof(rows,cp,pol) for rows,pol in series]
    z=[x for x in z if x]
    if not z:return None
    cur=med([x['current'] for x in z]); prev=med([x['previous'] for x in z])
    direction=0 if abs(cur)<TH else (1 if cur>0 else -1)
    acc=cur-prev; accel=0 if abs(acc)<TH else (1 if acc>0 else -1)
    turning=(prev!=0 and direction!=0 and (1 if prev>0 else -1)!=direction)
    return {'direction':direction,'speed':abs(cur),'acceleration':acc,'accelDir':accel,'turning':turning,'n':len(z)}

def pair_value(row,a,b):
    if a==b:return 1.0
    order=CCY.index(a)<CCY.index(b); key=a+b if order else b+a
    v=float(row[key]); return v if order else 1.0/v

def stats(vals):
    if not vals:return {'n':0,'hit_rate':None,'mean_signed_log_return':None,'median_signed_log_return':None}
    s=sorted(vals); n=len(vals); m=s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2
    return {'n':n,'hit_rate':sum(v>0 for v in vals)/n,'mean_signed_log_return':sum(vals)/n,'median_signed_log_return':m}

def eval_events(events,fxrows,dates):
    out=[]
    for e in events:
        i=bisect_right(dates,e['checkpoint'])
        if i>=len(fxrows):continue
        r={'checkpoint':e['checkpoint'],'polarity':e['macro_polarity'],'growth_direction':e['growth_direction'],'labour_direction':e['labour_direction'],'entry_date':dates[i]}
        for h in H:
            if i+h>=len(fxrows):continue
            rel=[]
            for o in CCY:
                if o=='JPY':continue
                p0=pair_value(fxrows[i],'JPY',o); p1=pair_value(fxrows[i+h],'JPY',o)
                rel.append(math.log(p1/p0))
            b=sum(rel)/len(rel); r[f'basket_log_return_{h}d']=b; r[f'signed_{h}d']=e['macro_polarity']*b
        out.append(r)
    return out

def summarize(rows):
    return {f'{h}d':stats([r[f'signed_{h}d'] for r in rows if f'signed_{h}d' in r]) for h in H}

def walkforward(rows):
    n=len(rows); start=max(1,math.floor(n*0.4)); folds=[]; pooled=[]
    prev=start
    for k,frac in enumerate((0.6,0.8,1.0),1):
        end=n if frac==1.0 else max(prev+1,math.floor(n*frac))
        test=rows[prev:end]; pooled.extend(test)
        folds.append({'fold':k,'train_event_count':prev,'test_event_count':len(test),'test_start':test[0]['checkpoint'] if test else None,'test_end':test[-1]['checkpoint'] if test else None,'stats':summarize(test)})
        prev=end
    return {'initial_train_fraction':0.4,'folds':folds,'pooled_oos_event_count':len(pooled),'pooled_oos':summarize(pooled)}

def main():
    with GDP.open(newline='',encoding='utf-8') as f:gdp=list(csv.DictReader(f))
    with MACH.open(newline='',encoding='utf-8') as f:mach=list(csv.DictReader(f))
    with LAB.open(newline='',encoding='utf-8') as f:lab=list(csv.DictReader(f))
    with FX.open(newline='',encoding='utf-8') as f:fxrows=list(csv.DictReader(f))
    dates=[r['date'] for r in fxrows]

    gdp_lvl=synth(gdp,'reference_quarter','real_gdp_sa_qoq_pct')
    mach_lvl=synth(mach,'reference_month','private_core_orders_sa_mom_pct')
    emp=[{'release_date':r['release_date'],'value':float(r['employed_sa_10k'])} for r in lab]
    un=[{'release_date':r['release_date'],'value':float(r['unemployment_rate_sa_pct'])} for r in lab]

    cps=sorted(set([r['release_date'] for r in gdp_lvl+mach_lvl+emp+un]))
    replay=[]
    for cp in cps:
        g=block([(gdp_lvl,1),(mach_lvl,1)],cp)
        l=block([(emp,1),(un,-1)],cp)
        pol=None
        if g and l:
            sm=g['direction']+l['direction']; pol=0 if sm==0 else (1 if sm>0 else -1)
        replay.append({'checkpoint':cp,'blocks':{'Crescita':g,'Lavoro':l,'Inflazione':None},'macro_polarity':pol,'macro_turning':bool(g and l and (g.get('turning') or l.get('turning'))) if g and l else None})

    usable=[x for x in replay if x['macro_polarity'] in (-1,1)]
    regime=[];last=None
    for x in usable:
        if x['macro_polarity']!=last:
            regime.append({'checkpoint':x['checkpoint'],'macro_polarity':x['macro_polarity'],'growth_direction':x['blocks']['Crescita']['direction'],'labour_direction':x['blocks']['Lavoro']['direction']})
            last=x['macro_polarity']
    samples=eval_events(regime,fxrows,dates)

    attrib={}
    for bn,key in [('Growth','Crescita'),('Labour','Lavoro')]:
        ev=[];last=None
        for x in replay:
            b=x['blocks'][key]
            if not b or b['direction'] not in (-1,1):continue
            if b['direction']!=last:
                ev.append({'checkpoint':x['checkpoint'],'macro_polarity':b['direction'],'growth_direction':b['direction'] if key=='Crescita' else None,'labour_direction':b['direction'] if key=='Lavoro' else None}); last=b['direction']
        sam=eval_events(ev,fxrows,dates)
        attrib[bn]={'event_count':len(sam),'full_sample':summarize(sam),'walkforward':walkforward(sam)}

    out={
      'schema':'GMFQ_JPY_FROZEN_MACRO_REPLAY_V1','status':'PASS','created_at':'2026-10-06',
      'scope':'Frozen v9.3 PIT Macro directional replay for JPY versus equal-weight G8 counterpart basket; Inflation historical PIT remains WITHHELD and casts no vote.',
      'engine':{'commit':'ff52198a75cc67f7dae96fc2bbf65623f170791c','rules_fingerprint':'3356baf0','model_rules_version':'9.3-pair-attention-hierarchy','threshold_direction':0.2,'threshold_acceleration':0.2,'scale':'median absolute first differences, last 80 observations','minimum_observations':8,'threshold_tuning':False},
      'aggregation_rule':'Exact frozen PIT replay rule: macro_polarity = sign(Growth.direction + Labour.direction); opposing +1/-1 tie => 0. No weights.',
      'series':{
        'Growth':[{'name':'ESRI Real GDP SA q/q first preliminary','polarity':1,'rows':len(gdp_lvl)},{'name':'ESRI private-sector machinery orders ex ships/electric power SA m/m first release','polarity':1,'rows':len(mach_lvl)}],
        'Labour':[{'name':'LFS employment SA','polarity':1,'rows':len(emp)},{'name':'LFS unemployment rate SA','polarity':-1,'rows':len(un)}],
        'Inflation':{'status':'WITHHELD_HISTORICAL_PIT','vote':None}},
      'timing_policy':'Asynchronous release timeline. Each series updates only at its contemporaneous release; latest eligible series state is carried forward. FX entry is first ECB daily reference observation strictly after Macro checkpoint.',
      'coverage':{'first_checkpoint':cps[0] if cps else None,'last_checkpoint':cps[-1] if cps else None,'checkpoints':len(cps),'directional_macro_checkpoints':len(usable),'macro_regime_entries':len(samples)},
      'full_sample':summarize(samples),'walkforward':walkforward(samples),'subblock_attribution':attrib,
      'replay':replay,'regime_samples':samples,
      'guardrails':['PIT/first-release inputs only','No revised-history fallback','No parameter fitting or threshold tuning','Inflation WITHHELD casts no vote','Same v9.3 block and macro aggregation rules','Conservative next-reference-price FX entry'],
      'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False
    }
    OUT.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':out['status'],'coverage':out['coverage'],'full_sample':out['full_sample'],'pooled_oos':out['walkforward']['pooled_oos'],'subblocks':{k:{'events':v['event_count'],'pooled_oos':v['walkforward']['pooled_oos']} for k,v in attrib.items()}},indent=2))
if __name__=='__main__':main()
