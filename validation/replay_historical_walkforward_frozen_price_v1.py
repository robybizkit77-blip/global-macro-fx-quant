#!/usr/bin/env python3
import argparse, json, math, re, statistics
from bisect import bisect_left
from datetime import date, timedelta
from pathlib import Path

CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']
PAIRS=['AUD/CAD','AUD/CHF','AUD/JPY','AUD/NZD','AUD/USD','CAD/CHF','CAD/JPY','CHF/JPY','EUR/AUD','EUR/CAD','EUR/CHF','EUR/GBP','EUR/JPY','EUR/NZD','EUR/USD','GBP/AUD','GBP/CAD','GBP/CHF','GBP/JPY','GBP/NZD','GBP/USD','NZD/CAD','NZD/CHF','NZD/JPY','NZD/USD','USD/CAD','USD/CHF','USD/JPY']
RATE_IDS={
 'USD':'US_DGS2_history_DGS2','GBP':'GBP_RATES_2016_2026_2Y','JPY':'JPY_RATES_2016_2026_2Y',
 'CHF':'CH_CONFED_SPOT_2Y_history_value_pct','CAD':'CAD_RATES_2016_2026_2Y','AUD':'AU_FCMYGBAG2D_history_FCMYGBAG2D',
 'NZD':'NZD_RATES_2016_2026_RBNZ_B2_2Y'
}


def med(xs):
    xs=sorted(x for x in xs if isinstance(x,(int,float)) and math.isfinite(x))
    if not xs:return None
    n=len(xs); m=n//2
    return xs[m] if n%2 else (xs[m-1]+xs[m])/2

def robust_scale(vals):
    diffs=[abs(vals[i]-vals[i-1]) for i in range(1,len(vals)) if math.isfinite(vals[i]) and math.isfinite(vals[i-1])]
    m=med(diffs)
    return m if m and math.isfinite(m) and m>0 else None

def polarity(category,label):
    l=(label or '').lower()
    if category=='Lavoro':
        if 'disoccup' in l or 'sussidi disoccupazione' in l or 'claims' in l:return -1
        if 'costo unitario' in l:return 0
        return 1
    if category=='Crescita':
        if 'tasso di risparmio' in l:return 0
        return 1
    return 0

def impulse(series,category):
    vals=[float(x) for x in series.get('values',[]) if isinstance(x,(int,float)) and math.isfinite(float(x))]
    if len(vals)<8:return None
    pol=polarity(category,series.get('label',''))
    if pol==0:return None
    scale=robust_scale(vals[-80:])
    if not scale:return None
    return ((vals[-1]-vals[-2])*pol/scale,(vals[-2]-vals[-3])*pol/scale)

def block(series_list,category):
    imps=[impulse(s,category) for s in series_list if s.get('category')==category]
    imps=[x for x in imps if x is not None]
    if not imps:return None
    cur=med([x[0] for x in imps]); prev=med([x[1] for x in imps])
    if cur is None or prev is None:return None
    direction=0 if abs(cur)<0.20 else (1 if cur>0 else -1)
    return {'direction':direction,'n':len(imps),'current':cur,'previous':prev}

def series_dyn(vals):
    vals=[float(x) for x in vals if isinstance(x,(int,float)) and math.isfinite(float(x))]
    if len(vals)<10:return None
    n=len(vals); fast=min(5,n//3)
    def slope(end,L):
        st=end-L+1
        if st<0:return None
        return (vals[end]-vals[st])/(L-1)
    recent=slope(n-1,fast); prior=slope(n-fast,fast)
    if recent is None or prior is None:return None
    diffs=[abs(vals[i]-vals[i-1]) for i in range(max(1,n-52),n)]
    typical=med(diffs) or 0
    direction=0 if abs(recent)<typical*0.15 else (1 if recent>0 else -1)
    return {'dir':direction,'recent':recent,'prior':prior}

def load_archive(path):
    text=Path(path).read_text(errors='ignore').strip()
    eq=text.find('='); end=text.rfind(';')
    if eq<0: raise ValueError('macro archive assignment not found')
    raw=text[eq+1:end if end>eq else None].strip()
    return json.loads(raw)

def dt_key(x):
    s=str(x).strip()
    try:
        if re.fullmatch(r'\d{4}-\d{2}',s):
            return date(int(s[:4]),int(s[5:7]),1)
        if re.fullmatch(r'\d{4}/\d{1,2}/\d{1,2}',s):
            y,m,d=(int(v) for v in s.split('/'))
            return date(y,m,d)
        return date.fromisoformat(s[:10])
    except:
        return None

def truncate_series(s,checkpoint):
    dates=s.get('dates') or [] ; vals=s.get('values') or []
    out=[]
    for d,v in zip(dates,vals):
        dd=dt_key(d)
        if dd and dd<=checkpoint and isinstance(v,(int,float)) and math.isfinite(float(v)):
            out.append((d,float(v)))
    z=dict(s); z['dates']=[a for a,b in out]; z['values']=[b for a,b in out]
    return z

def monthly_checkpoints():
    out=[]
    y,m=2018,1
    while (y,m)<=(2026,9):
        out.append(date(y,m,1)); m+=1
        if m==13:y+=1;m=1
    return out

def pair_value(row,pair):
    a,b=pair.split('/')
    return float(row[b])/float(row[a])

def first_row_on_after(rows,dates,target):
    i=bisect_left(dates,target)
    return rows[i] if i<len(rows) else None

def stats(xs):
    if not xs:return {'n':0,'hit':None,'mean':None,'median':None}
    return {'n':len(xs),'hit':sum(x>0 for x in xs)/len(xs),'mean':sum(xs)/len(xs),'median':statistics.median(xs)}

def load_series_override(path,series_id):
    raw=json.loads(Path(path).read_text())
    if isinstance(raw,list):
        hit=next((x for x in raw if x.get('id')==series_id),None)
    elif isinstance(raw,dict) and raw.get('id')==series_id:
        hit=raw
    else:
        hit=None
    if not hit: raise ValueError(f'override series {series_id} not found in {path}')
    return hit

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--macro',default='history/MACRO_SERIES_2016_2026_RUNTIME_ARCHIVE_2026-10-01.js')
    ap.add_argument('--price',default='history/ECB_FX_G8_2018_2026_CANONICAL_V1.json')
    ap.add_argument('--golden',default='validation/HISTORICAL_WALKFORWARD_V93_2026-10-01.json')
    ap.add_argument('--jpy-series-override')
    ap.add_argument('--output',required=True)
    args=ap.parse_args()
    arc=load_archive(args.macro)
    S=arc.get('series',arc.get('currencies',arc)) if isinstance(arc,dict) else arc
    override_meta=None
    if args.jpy_series_override:
        old=load_series_override(args.jpy_series_override,RATE_IDS['JPY'])
        cur=list(S.get('JPY',[]))
        cur=[x for x in cur if x.get('id')!=RATE_IDS['JPY']]
        cur.append(old)
        S['JPY']=cur
        override_meta={'id':old.get('id'),'n':len(old.get('values',[])),'first':old.get('dates',[None])[0] if old.get('dates') else None,'last':old.get('dates',[None])[-1] if old.get('dates') else None,'source_file':old.get('source_file')}
    price=json.loads(Path(args.price).read_text())
    rows=price['rows']; pdates=[date.fromisoformat(r['Date']) for r in rows]
    golden=json.loads(Path(args.golden).read_text())
    cps=monthly_checkpoints(); horizons=[7,28,84]
    outcomes={h:{'CONTRASTO STRUTTURALE FORTE':[],'VANTAGGIO RELATIVO PARZIALE':[]} for h in horizons}
    counts={'CONTRASTO STRUTTURALE FORTE':0,'VANTAGGIO RELATIVO PARZIALE':0,'PILASTRI DIVISI':0,'NESSUN CONTRASTO':0,'WITHHELD':0}
    rows_out=[]
    for cp in cps:
        cstate={}
        for c in CCYS:
            ser=S.get(c,[]) if isinstance(S,dict) else []
            t=[truncate_series(s,cp) for s in ser]
            g=block(t,'Crescita'); l=block(t,'Lavoro')
            macro=None
            if g is not None and l is not None:
                sm=g['direction']+l['direction']; macro=1 if sm>0 else -1 if sm<0 else 0
            rates=None
            rid=RATE_IDS.get(c)
            if rid:
                rs=next((s for s in t if s.get('id')==rid),None)
                if rs: rates=series_dyn(rs.get('values',[]))
            cstate[c]={'macro':macro,'policy':None if rates is None else rates['dir'],'growth':g,'labour':l}
        for pair in PAIRS:
            a,b=pair.split('/'); A=cstate[a]; B=cstate[b]
            if None in (A['macro'],B['macro'],A['policy'],B['policy']):
                q='WITHHELD'; fav=None
            else:
                ms='A' if A['macro']>B['macro'] else 'B' if B['macro']>A['macro'] else 'TIE'
                ps='A' if A['policy']>B['policy'] else 'B' if B['policy']>A['policy'] else 'TIE'
                if ms!='TIE' and ms==ps:q='CONTRASTO STRUTTURALE FORTE';fav=a if ms=='A' else b
                elif ms!='TIE' and ps=='TIE':q='VANTAGGIO RELATIVO PARZIALE';fav=a if ms=='A' else b
                elif ps!='TIE' and ms=='TIE':q='VANTAGGIO RELATIVO PARZIALE';fav=a if ps=='A' else b
                elif ms!='TIE' and ps!='TIE' and ms!=ps:q='PILASTRI DIVISI';fav=None
                else:q='NESSUN CONTRASTO';fav=None
            counts[q]+=1
            rec={'checkpoint':cp.isoformat(),'pair':pair,'quality':q,'favored':fav}
            if fav:
                entry=first_row_on_after(rows,pdates,cp)
                for h in horizons:
                    exitrow=first_row_on_after(rows,pdates,cp+timedelta(days=h))
                    if entry and exitrow:
                        p0=pair_value(entry,pair); p1=pair_value(exitrow,pair)
                        r=(p1/p0-1)*100
                        if fav==b:r=-r
                        rec[str(h)]=r
                        outcomes[h][q].append(r)
            rows_out.append(rec)
    result={
      'schema':'GMFQ_HISTORICAL_WALKFORWARD_FROZEN_PRICE_REPLAY_V1',
      'status':'PASS', 'rules_fingerprint':'3356baf0','checkpoint_count':len(cps),'pair_count':len(PAIRS),
      'jpy_series_override':override_meta,
      'quality_counts':counts,'golden_quality_counts':golden.get('quality_counts_4w',{}),
      'quality_counts_match':counts==golden.get('quality_counts_4w',{}),
      'results':{str(h):{'strong':stats(outcomes[h]['CONTRASTO STRUTTURALE FORTE']),'partial':stats(outcomes[h]['VANTAGGIO RELATIVO PARZIALE'])} for h in horizons},
      'golden_results':{str(h):{'strong':golden['results'][str(h)]['strong'],'partial':golden['results'][str(h)]['partial']} for h in horizons},
      'model_rules_modified':False,'live_data_modified':False,
      'rows':rows_out
    }
    Path(args.output).write_text(json.dumps(result,indent=2,ensure_ascii=False))
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2,ensure_ascii=False))

if __name__=='__main__': main()
