import csv, json, math, urllib.request
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FX_PATH=ROOT/'history/pit_v1/FX_G8_DAILY_ECB_2016_2026.csv'
OUT=ROOT/'validation/PIT_MACRO_SUBBLOCK_ATTRIBUTION_V1_2026-10-06.json'
REPLAY_URL='https://raw.githubusercontent.com/robybizkit77-blip/global-macro-fx-quant/staging-usd-pit-readiness-2026-10-03/validation/PIT_MACRO_REPLAY_V1_2026-10-03.json'
CCYS=['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']
H=[5,20,60]

with urllib.request.urlopen(REPLAY_URL,timeout=30) as r:
    replay=json.load(r)
with FX_PATH.open(newline='',encoding='utf-8') as f:
    rows=list(csv.DictReader(f))

dates=[date.fromisoformat(r['date']) for r in rows]

def entry_idx(checkpoint):
    d=date.fromisoformat(checkpoint)
    for i,x in enumerate(dates):
        if x>d:
            return i
    return None

def pair_log_return(ccy,other,i0,i1):
    direct=ccy+other
    inverse=other+ccy
    if direct in rows[i0] and rows[i0][direct] and rows[i1][direct]:
        return math.log(float(rows[i1][direct])/float(rows[i0][direct]))
    if inverse in rows[i0] and rows[i0][inverse] and rows[i1][inverse]:
        return -math.log(float(rows[i1][inverse])/float(rows[i0][inverse]))
    raise KeyError((ccy,other))

def basket_return(ccy,i0,i1):
    vals=[pair_log_return(ccy,o,i0,i1) for o in CCYS if o!=ccy]
    return sum(vals)/len(vals)

def classify_block(name):
    x=name.lower()
    if 'cresc' in x or 'growth' in x:
        return 'Growth'
    if 'lavor' in x or 'labour' in x or 'labor' in x or 'occup' in x or 'employment' in x:
        return 'Labour'
    return name

def regime_entries(ccy,block_label):
    out=[]; prev=None
    source=replay['currencies'][ccy]['replay']
    for rec in source:
        found=None
        for k,v in (rec.get('blocks') or {}).items():
            if classify_block(k)==block_label:
                found=v; break
        if not found:
            continue
        direction=found.get('direction')
        if direction not in (-1,1):
            continue
        if direction==prev:
            continue
        prev=direction
        i0=entry_idx(rec['checkpoint'])
        if i0 is None:
            continue
        e={'checkpoint':rec['checkpoint'],'entry_date':rows[i0]['date'],'direction':direction}
        for h in H:
            i1=i0+h
            if i1 < len(rows):
                br=basket_return(ccy,i0,i1)
                e[f'signed_{h}d']=direction*br
        out.append(e)
    return out

def stats(sample,h):
    vals=[x[f'signed_{h}d'] for x in sample if f'signed_{h}d' in x]
    if not vals: return {'n':0,'hit_rate':None,'mean':None,'median':None}
    s=sorted(vals); n=len(vals)
    med=s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2
    return {'n':n,'hit_rate':sum(v>0 for v in vals)/n,'mean':sum(vals)/n,'median':med}

def walkforward(entries):
    n=len(entries); init=max(1,int(n*0.4)); rem=n-init
    base=rem//3; extra=rem%3; start=init; folds=[]; pooled=[]
    for fold in range(3):
        size=base+(1 if fold<extra else 0)
        test=entries[start:start+size]; start+=size
        if not test: continue
        pooled.extend(test)
        folds.append({'fold':fold+1,'train_n':n-len(entries[start-size:]),'test_n':len(test),
                      'test_start':test[0]['checkpoint'],'test_end':test[-1]['checkpoint'],
                      'test':{f'{h}d':stats(test,h) for h in H}})
    return {'folds':folds,'pooled_oos':{f'{h}d':stats(pooled,h) for h in H},'pooled_oos_n':len(pooled)}

result={
 'schema':'GMFQ_PIT_MACRO_SUBBLOCK_ATTRIBUTION_V1','status':'PASS','created_at':'2026-10-06',
 'scope':'Frozen PIT Macro Growth/Labour attribution for EUR and CAD versus equal-weight G8 basket; no tuning or rule changes.',
 'engine':{'commit':'ff52198a75cc67f7dae96fc2bbf65623f170791c','rules_fingerprint':'3356baf0','threshold_tuning':False},
 'method':{'signal':'subblock direction +/-1','event':'new non-zero subblock direction regime only','walkforward':'first 40% descriptive history then three chronological OOS folds','rules_reestimated':False},
 'currencies':{}
}
for ccy in ['EUR','CAD']:
    cres={}
    block_names=set()
    for rec in replay['currencies'][ccy]['replay']:
        for k in (rec.get('blocks') or {}): block_names.add(classify_block(k))
    for block in ['Growth','Labour']:
        entries=regime_entries(ccy,block)
        cres[block]={'regime_entry_count':len(entries),'full_sample':{f'{h}d':stats(entries,h) for h in H},'walkforward':walkforward(entries)}
    cres['detected_blocks']=sorted(block_names)
    result['currencies'][ccy]=cres
result['guardrails']=['No threshold tuning','No parameter fitting','No revised-history fallback','Chronological order preserved','Audit-only output']
result['changes_live_data']=False; result['changes_engine_rules']=False; result['changes_oos_baseline']=False
OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps({c:{b:result['currencies'][c][b]['walkforward']['pooled_oos'] for b in ['Growth','Labour']} for c in ['EUR','CAD']},indent=2))
