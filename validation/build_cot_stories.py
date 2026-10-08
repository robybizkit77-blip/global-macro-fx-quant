#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, pathlib, sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
SRC=ROOT/'live_data'/'sections'/'V250_COT_CHART_DATA.json'
CURRENT=ROOT/'live_data'/'sections'/'V247_COT_STORIES.json'
ORDER=['EUR','GBP','JPY','CHF','AUD','NZD','CAD','USD']


def sign_int(v:int)->str:
    return f'{v:+,d}'
def fmt_num(v:int)->str:
    return f'{v:,d}'
def signal_from_percentile(p:float)->str:
    if p>=80: return 'EXTREME LONG'
    if p<=20: return 'EXTREME SHORT'
    return 'NEUTRALE'
def build_one(ccy:str,s:dict)->dict:
    required=['dates','net','long','short','percentile','netoi']
    for k in required:
        if k not in s or len(s[k])<5: raise ValueError(f'{ccy}: missing/short series {k}')
    n=len(s['dates'])
    if any(len(s[k])!=n for k in required[1:]): raise ValueError(f'{ccy}: inconsistent series lengths')
    date=s['dates'][-1]
    net=int(s['net'][-1]); prev=int(s['net'][-2]); prev4=int(s['net'][-5])
    longv=int(s['long'][-1]); shortv=int(s['short'][-1])
    pct=float(s['percentile'][-1]); netoi=float(s['netoi'][-1])
    d1=net-prev; d4=net-prev4
    pos='long' if net>=0 else 'short'; level='positivo' if net>=0 else 'negativo'
    flow='migliora' if d1>0 else 'peggiora' if d1<0 else 'invariato'
    return {
      'signal':signal_from_percentile(pct),
      'today':f'CFTC al {date}: fondi net {pos} {sign_int(net)} contratti; Net/OI {netoi:+.1f}% e percentile 104 settimane {pct:.1f}.',
      'w4':f'Variazione su 4 settimane: {sign_int(d4)} contratti netti; il livello resta {level}.',
      'w1':f'Variazione settimanale: {sign_int(d1)} contratti netti ({flow}).',
      'why':'Stock, flusso e percentile sono aggiornati dal medesimo record CFTC; il rapporto con il prezzo richiede un refresh prezzo validato separato.',
      'funds':'Flusso CFTC aggiornato',
      'funds_detail':f'Long {fmt_num(longv)}; short {fmt_num(shortv)}.',
      'price':'WITHHELD',
      'price_detail':'Conferma prezzo non ricalcolata: nessun input prezzo validato in questo refresh CFTC.'
    }
def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',default=str(SRC))
    ap.add_argument('--output')
    ap.add_argument('--audit-current',action='store_true')
    a=ap.parse_args()
    src=json.loads(pathlib.Path(a.source).read_text())
    if set(src)!=set(ORDER): raise SystemExit('source must contain exactly 8 G8 currencies')
    out={c:build_one(c,src[c]) for c in ORDER}
    result={'status':'PASS','currencies':len(out),'extreme_low':20,'extreme_high':80,'output':out}
    if a.audit_current:
        cur=json.loads(CURRENT.read_text()); drift=[]
        for c in ORDER:
            for k,v in out[c].items():
                if cur.get(c,{}).get(k)!=v: drift.append({'currency':c,'field':k,'current':cur.get(c,{}).get(k),'built':v})
        result['current_drift']=drift; result['current_drift_count']=len(drift)
    if a.output: pathlib.Path(a.output).write_text(json.dumps(out,separators=(',',':'),ensure_ascii=False)+'\n')
    print(json.dumps(result,indent=2,ensure_ascii=False)); return 0
if __name__=='__main__': sys.exit(main())
