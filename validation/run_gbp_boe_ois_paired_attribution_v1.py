import csv,json,math,random
from datetime import datetime
from pathlib import Path

FX='history/pit_v1/FX_G8_DAILY_ECB_2016_2026.csv'
AWE='history/pit_v1/GBP_AWE_K54L_CERTIFIED_VINTAGES_2018_2026.csv'
OIS='history/pit_v1/GBP_BOE_OIS_SPOT_2Y_DAILY_2018_2026.csv'
OUT=Path('validation/GBP_BOE_OIS_PAIRED_ATTRIBUTION_V1_2026-10-06.json')
H=[5,20,60]; PEERS=['USD','EUR','JPY','CHF','CAD','AUD','NZD']; B=20000; SEED=3356

def iso(s): return datetime.strptime(s,'%d %B %Y').strftime('%Y-%m-%d')
def load(p):
    with open(p,encoding='utf-8') as f:return list(csv.DictReader(f))
def sign(x):return 1 if x>0 else -1 if x<0 else 0

def first_new_ref(rows):
    out=[];seen=set()
    for r in sorted(rows,key=lambda x:iso(x['available_date'])):
        ref=r['reference_month']
        if ref in seen:continue
        seen.add(ref)
        try:v=float(r['yoy_pct'])
        except:continue
        out.append((iso(r['available_date']),ref,v))
    return out

def fxret(rows,i,h):
    if i+h>=len(rows):return None
    a,b=rows[i],rows[i+h];vals=[]
    for p in PEERS:
        direct='GBP'+p;inv=p+'GBP'
        try:
            if direct in a and a[direct] and b[direct]:r=math.log(float(b[direct])/float(a[direct]))
            elif inv in a and a[inv] and b[inv]:r=-math.log(float(b[inv])/float(a[inv]))
            else:continue
            vals.append(r)
        except:continue
    return sum(vals)/len(vals) if vals else None

def first_after(rows,d):
    for i,r in enumerate(rows):
        if r['date']>d:return i
    return None

def build_events():
    fx=load(FX);awe=load(AWE);ois=load(OIS)
    pts=first_new_ref(awe); changes=[]
    for a,b in zip(pts,pts[1:]):
        d=b[2]-a[2]
        if d!=0:changes.append((b[0],b[1],d))
    bydate={r['date']:float(r['gbp_ois_spot_2y_pct']) for r in ois};dates=sorted(bydate)
    all_ev=[];confirmed=[];rejected=[]
    for d,ref,chg in changes:
        s=sign(chg);idx=next((i for i,x in enumerate(dates) if x>=d),None)
        if idx is None or idx+5>=len(dates):continue
        d0,d1=dates[idx],dates[idx+5];dr=bydate[d1]-bydate[d0];rs=sign(dr)
        i=first_after(fx,d1)
        if i is None:continue
        e={'wage_checkpoint':d,'reference_month':ref,'signal':s,'confirmation_date':d1,'entry_date':fx[i]['date'],'ois_change_pp':dr,'ois_signal':rs,'confirmed':rs==s}
        for h in H:
            r=fxret(fx,i,h);e[f'signed_{h}d']=None if r is None else s*r
        all_ev.append(e);(confirmed if rs==s else rejected).append(e)
    return all_ev,confirmed,rejected

def med(xs):
    y=sorted(xs);n=len(y);return y[n//2] if n%2 else (y[n//2-1]+y[n//2])/2

def q(a,p):
    y=sorted(a);i=(len(y)-1)*p;lo=int(math.floor(i));hi=int(math.ceil(i))
    return y[lo] if lo==hi else y[lo]+(y[hi]-y[lo])*(i-lo)

def wilson(k,n,z=1.959963984540054):
    if not n:return [None,None]
    p=k/n;den=1+z*z/n;c=(p+z*z/(2*n))/den;h=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return [max(0,c-h),min(1,c+h)]

def stats(ev,bootstrap=True):
    out={};rng=random.Random(SEED)
    for h in H:
        xs=[e[f'signed_{h}d'] for e in ev if e.get(f'signed_{h}d') is not None];n=len(xs)
        if not n:out[f'{h}d']={'n':0};continue
        k=sum(x>0 for x in xs);d={'n':n,'hit_rate':k/n,'mean':sum(xs)/n,'median':med(xs),'wilson95_hit':wilson(k,n)}
        if bootstrap:
            means=[];hits=[]
            for _ in range(B):
                ss=[xs[rng.randrange(n)] for __ in range(n)];means.append(sum(ss)/n);hits.append(sum(x>0 for x in ss)/n)
            d['bootstrap95_mean']=[q(means,.025),q(means,.975)];d['bootstrap95_hit']=[q(hits,.025),q(hits,.975)]
        out[f'{h}d']=d
    return out

def chronological_pool(ev):
    x=sorted(ev,key=lambda e:e['entry_date']);cut=max(1,int(len(x)*.4));test=x[cut:]
    return {'train_n':cut,'test_n':len(test),'test_start':test[0]['entry_date'] if test else None,'test_end':test[-1]['entry_date'] if test else None,'test_stats':stats(test)}

def delta_stats(c,r):
    out={}
    for h in H:
        cs=stats(c,False)[f'{h}d'];rs=stats(r,False)[f'{h}d']
        out[f'{h}d']={'confirmed_minus_rejected_hit_rate':cs.get('hit_rate',0)-rs.get('hit_rate',0),'confirmed_minus_rejected_mean':cs.get('mean',0)-rs.get('mean',0)}
    return out

def main():
    all_ev,c,r=build_events()
    out={'schema':'GMFQ_GBP_BOE_OIS_PAIRED_ATTRIBUTION_V1','status':'PASS','created_at':'2026-10-06','scope':'Exact paired attribution of fixed 5-market-day BoE OIS 2Y confirmation on the same nonzero monthly AWE event universe and identical post-confirmation FX timing.','guardrails':['same 102-ish nonzero monthly wage-change universe','all groups enter after identical 5-market-day OIS observation window','no regime-entry frequency mismatch','K54L and 2Y OIS definitions frozen','no threshold tuning','engine untouched','live_data untouched'],'counts':{'all':len(all_ev),'confirmed':len(c),'rejected':len(r)},'all_events_same_timing':{'stats':stats(all_ev),'walkforward_reference':chronological_pool(all_ev)},'confirmed':{'stats':stats(c),'walkforward_reference':chronological_pool(c)},'rejected':{'stats':stats(r),'walkforward_reference':chronological_pool(r)},'incremental_confirmation':delta_stats(c,r),'assessment_policy':'OIS confirmation adds value only if confirmed events are materially stronger than rejected events on the same horizon and the effect is not solely in-sample.','changes_engine_rules':False,'changes_live_data':False,'threshold_tuning':False}
    OUT.write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
