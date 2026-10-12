#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,math
from bisect import bisect_right
from collections import Counter
from datetime import date,datetime
from pathlib import Path

CCYS=('EUR','JPY','CAD','AUD')
OFFICIAL_UNAVAILABLE={'UNAVAILABLE_OFFICIAL_NOT_PUBLISHED','NOT_PUBLISHED_OFFICIAL'}

def normalize_release_date(raw):
    x=raw.strip()
    for fmt in ('%Y-%m-%d','%d/%m/%Y'):
        try:return datetime.strptime(x[:10],fmt).date().isoformat()
        except ValueError:pass
    raise RuntimeError(f'unsupported certified release-date format: {raw!r}')

def load_rates(p):
    out=[]
    with Path(p).open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):out.append({'obs':r['observation_date'],'eligible':r['first_eligible_decision_date'],'y2':float(r['yield_2y'])})
    out.sort(key=lambda r:(r['eligible'],r['obs']));return out

def select_rate(rows,dp):
    q=[r for r in rows if r['eligible']<=dp]
    if not q:return None
    r=q[-1]
    if not (r['obs']<dp and r['eligible']<=dp):raise RuntimeError(f'temporal violation {dp}: {r}')
    return r

def load_macro(p):
    out=[]
    with Path(p).open(newline='',encoding='utf-8-sig') as f:
        rd=csv.DictReader(f);fs=set(rd.fieldnames or [])
        if 'release_date' not in fs or 'value' not in fs:raise RuntimeError(f'{p}: expected canonical release_date/value schema')
        for r in rd:
            if (r.get('availability_status') or '').strip() in OFFICIAL_UNAVAILABLE:continue
            rel=(r.get('release_date') or '').strip();val=(r.get('value') or '').strip()
            if not rel or not val:continue
            out.append((normalize_release_date(rel),float(val)))
    out.sort();return out

def latest3(rows,asof):
    ds=[d for d,_ in rows];i=bisect_right(ds,asof)-1
    return None if i<2 else (rows[i][1],rows[i-1][1],rows[i-2][1])

def sd(rows,asof):
    x=latest3(rows,asof)
    if x is None:return None
    a,b,c=x;return (a-b)-(b-c)

def sgn(x,e=1e-12):return 1 if x>e else (-1 if x<-e else 0)

def direction(local,usd,asof):
    li,ui,ll,ul=sd(local['inf'],asof),sd(usd['inf'],asof),sd(local['lab'],asof),sd(usd['lab'],asof)
    if None in (li,ui,ll,ul):return 0
    a,b=sgn(li-ui),sgn((-ll)-(-ul))
    return a if a!=0 and a==b else 0

def load_fx(p):
    out={}
    with Path(p).open(newline='',encoding='utf-8-sig') as f:
        rd=csv.DictReader(f);fs=rd.fieldnames or []
        dk=next(k for k in ['TIME_PERIOD','TIME PERIOD','Date','DATE'] if k in fs);vk=next(k for k in ['OBS_VALUE','OBS VALUE','Value','VALUE'] if k in fs)
        for r in rd:
            ds=(r.get(dk) or '')[:10];vs=(r.get(vk) or '').strip()
            try:date.fromisoformat(ds);v=float(vs)
            except Exception:continue
            if v>0:out[ds]=v
    return out

def first_common_after(dp,*series):
    c=sorted(set.intersection(*(set(s) for s in series)));i=bisect_right(c,dp)
    return None if i>=len(c) else c[i]

def next_month_day10(dp):
    d=date.fromisoformat(dp);y,m=d.year,d.month
    y,m=(y+1,1) if m==12 else (y,m+1)
    return f'{y:04d}-{m:02d}-10'

def local_usd(ccy,ds,usd,loc):return usd[ds] if ccy=='EUR' else usd[ds]/loc[ds]
def mean(x):return sum(x)/len(x) if x else None

def month_points(start,end):
    sy,sm=map(int,start[:7].split('-'));ey,em=map(int,end[:7].split('-'));out=[];y,m=sy,sm
    while (y,m)<=(ey,em):out.append(f'{y:04d}-{m:02d}-10');y,m=(y+1,1) if m==12 else (y,m+1)
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--contract',required=True,type=Path);ap.add_argument('--rates-dir',required=True,type=Path);ap.add_argument('--macro-dir',required=True,type=Path);ap.add_argument('--fx-dir',required=True,type=Path);ap.add_argument('--max-certified-decision-point',required=True);ap.add_argument('--output',required=True,type=Path);a=ap.parse_args()
    c=json.loads(a.contract.read_text());assert c['schema']=='GMFQ_G4USD_RELATIVE_MACRO_TURNING_2Y_FX_FORWARD_SHADOW_V1'
    first=c['first_permitted_macro_signal_asof'];maxdp=date.fromisoformat(a.max_certified_decision_point).isoformat()
    rates={x:load_rates(a.rates_dir/f'{x.lower()}.csv') for x in (*CCYS,'USD')}
    macro={x:{'inf':load_macro(a.macro_dir/f'{x.lower()}_inflation.csv'),'lab':load_macro(a.macro_dir/f'{x.lower()}_labour.csv')} for x in (*CCYS,'USD')}
    usd_fx=load_fx(a.fx_dir/'USD.csv');locfx={'EUR':None,'JPY':load_fx(a.fx_dir/'JPY.csv'),'CAD':load_fx(a.fx_dir/'CAD.csv'),'AUD':load_fx(a.fx_dir/'AUD.csv')}
    audit=[];events=[]
    if maxdp>=first:
        dps=month_points(first,maxdp)
        for x in CCYS:
            levels=[];d0=date.fromisoformat(first);py,pm=(d0.year-1,12) if d0.month==1 else (d0.year,d0.month-1)
            for dp in [f'{py:04d}-{pm:02d}-10']+dps:
                lr,ur=select_rate(rates[x],dp),select_rate(rates['USD'],dp)
                if lr and ur:levels.append({'dp':dp,'diff':lr['y2']-ur['y2']})
            for i in range(1,len(levels)):
                cur,prev=levels[i],levels[i-1]
                if cur['dp']<first:continue
                md=direction(macro[x],macro['USD'],cur['dp']);d2=cur['diff']-prev['diff']
                audit.append({'currency':x,'macro_signal_asof':cur['dp'],'macro_direction':md,'current_relative_2y_repricing':d2})
                if md==0:continue
                confirm=next_month_day10(cur['dp'])
                if confirm>maxdp:continue
                lr2,ur2=select_rate(rates[x],confirm),select_rate(rates['USD'],confirm)
                if not lr2 or not ur2:continue
                diff2=lr2['y2']-ur2['y2'];signed_bp=md*(diff2-cur['diff'])*100.0
                if signed_bp<=0:continue
                entry=first_common_after(confirm,usd_fx) if x=='EUR' else first_common_after(confirm,usd_fx,locfx[x]);exit_anchor=next_month_day10(confirm);exitd=first_common_after(exit_anchor,usd_fx) if x=='EUR' else first_common_after(exit_anchor,usd_fx,locfx[x]);outcome=None
                if entry and exitd:outcome=md*math.log(local_usd(x,exitd,usd_fx,locfx[x])/local_usd(x,entry,usd_fx,locfx[x]))
                events.append({'currency':x,'macro_signal_asof':cur['dp'],'macro_direction':md,'rates_confirmation_asof':confirm,'signed_next_month_relative_2y_bp':signed_bp,'entry_fixing_date':entry,'exit_anchor':exit_anchor,'exit_fixing_date':exitd,'signed_fx_log_return':outcome})
    matured=[e for e in events if e['signed_fx_log_return'] is not None];per={x:[e['signed_fx_log_return'] for e in matured if e['currency']==x] for x in CCYS};vals=[e['signed_fx_log_return'] for e in matured];counts=Counter(e['currency'] for e in matured);g=c['forward_confirmation_gate'];maxshare=max(counts.values())/len(matured) if matured else 0.0
    gates={'minimum_matured_fx_events':len(matured)>=g['minimum_matured_fx_events'],'minimum_currencies_represented':len(counts)>=g['minimum_currencies_represented'],'positive_mean_signed_fx':bool(vals) and mean(vals)>g['mean_signed_fx_log_return_gt'],'directional_accuracy':bool(vals) and sum(v>0 for v in vals)/len(vals)>=g['directional_accuracy_min'],'positive_currencies':sum(bool(per[x]) and mean(per[x])>0 for x in CCYS)>=g['minimum_currencies_positive_mean'],'concentration':maxshare<=g['max_single_currency_share'] if matured else False,'both_directions':any(e['macro_direction']>0 for e in matured) and any(e['macro_direction']<0 for e in matured)}
    enough=len(matured)>=g['minimum_matured_fx_events'];passed=enough and all(gates.values());status='FORWARD_CONFIRMED_PENDING_PROMOTION_REVIEW' if passed else ('FORWARD_GATE_FAILED_NO_TUNING' if enough else 'WAITING_FOR_UNSEEN_OBSERVATIONS')
    out={'schema':'GMFQ_G4USD_RELATIVE_MACRO_TURNING_2Y_FX_FORWARD_RESULT_V1','status':status,'first_permitted_macro_signal_asof':first,'max_certified_decision_point':maxdp,'signals_total':len(events),'matured_fx_events':len(matured),'currencies_represented':sorted(counts),'pooled_mean_signed_fx_log_return':mean(vals),'directional_accuracy':sum(v>0 for v in vals)/len(vals) if vals else None,'per_currency_mean':{x:mean(per[x]) for x in CCYS},'gates':gates,'audit_rows':audit,'events':events,'input_refresh_required':maxdp<first,'historical_backfill_used':False,'edge_certified':False,'production_signal_authorized':False,'sizing_authorized':False,'no_rescue_tuning':True}
    if any(e['macro_signal_asof']<first for e in events):raise RuntimeError('historical backfill violation')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps({k:out[k] for k in ['status','signals_total','matured_fx_events','currencies_represented','input_refresh_required','gates']},indent=2,sort_keys=True))
if __name__=='__main__':main()
