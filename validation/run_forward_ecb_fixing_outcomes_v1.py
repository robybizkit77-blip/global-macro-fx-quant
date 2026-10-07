#!/usr/bin/env python3
import json, math, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
LEDGER=ROOT/'validation/FORWARD_SNAPSHOT_LEDGER_V1_2026-10-07.json'
PAYLOAD=ROOT/'validation/DASHBOARD_PAIR_RENDER_PAYLOAD_V1_2026-10-07.json'
OUT=ROOT/'validation/FORWARD_ECB_FIXING_STATE_V1_2026-10-07.json'
URL='https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml'
REQ={'USD','JPY','GBP','CHF','AUD','CAD','NZD'}
HORIZONS=(5,20,60)
BRUSSELS=ZoneInfo('Europe/Brussels')

def load_json(p):
    return json.loads(p.read_text(encoding='utf-8'))

def fetch_ecb():
    req=urllib.request.Request(URL,headers={'User-Agent':'GMFQ-forward-research/1.0'})
    with urllib.request.urlopen(req,timeout=30) as r:
        raw=r.read()
    root=ET.fromstring(raw)
    rows=[]
    for node in root.iter():
        t=node.attrib.get('time')
        if not t: continue
        rates={'EUR':1.0}
        for c in list(node):
            ccy=c.attrib.get('currency'); rate=c.attrib.get('rate')
            if ccy and rate:
                try: rates[ccy]=float(rate)
                except ValueError: pass
        if REQ.issubset(rates): rows.append((t,rates))
    rows.sort(key=lambda x:x[0])
    if not rows: raise RuntimeError('No ECB fixing history parsed')
    return rows

def pair_price(pair,rates):
    a,b=pair.split('/')
    if a not in rates or b not in rates: return None
    return rates[b]/rates[a]

def eligible_entry_date(captured_at, rows):
    dt=datetime.fromisoformat(captured_at.replace('Z','+00:00')).astimezone(BRUSSELS)
    # Conservative no-leakage cutoff. Before 14:00 Brussels time the same-day
    # fixing is not yet established; at/after 14:00 use the next fixing date.
    target=dt.date().isoformat()
    dates=[d for d,_ in rows]
    candidates=[d for d in dates if d>=target]
    if dt.hour>=14:
        candidates=[d for d in candidates if d>target]
    return candidates[0] if candidates else None

def main():
    ledger=load_json(LEDGER); payload=load_json(PAYLOAD); rows=fetch_ecb()
    dates=[d for d,_ in rows]; bydate=dict(rows)
    state={
      'schema':'GMFQ_FORWARD_ECB_FIXING_STATE_V1',
      'status':'ACTIVE_RESEARCH_FORWARD_OUTCOME_STATE',
      'source':'ECB euro foreign exchange reference rates',
      'source_url':URL,
      'entry_cutoff_policy':'same-day allowed only when snapshot captured before 14:00 Europe/Brussels; otherwise next fixing',
      'horizons_fixing_observations':list(HORIZONS),
      'primary_horizon':20,
      'snapshots':{}
    }
    if OUT.exists():
        prev=load_json(OUT)
        if prev.get('schema')==state['schema']:
            state['snapshots']=prev.get('snapshots',{})
    for snap in ledger.get('snapshots',[]):
        sid=snap['snapshot_id']; old=state['snapshots'].get(sid,{})
        entry_date=old.get('entry_fixing_date') or eligible_entry_date(snap['captured_at'],rows)
        rec={
          'snapshot_id':sid,
          'captured_at':snap['captured_at'],
          'entry_fixing_date':entry_date,
          'entry_locked':bool(old.get('entry_locked',False)),
          'entry_prices':old.get('entry_prices',{}),
          'outcomes':old.get('outcomes',{}),
          'state_counts':snap.get('state_counts',{}),
          'robustness_counts':snap.get('robustness_counts',{})
        }
        if entry_date and entry_date in bydate and not rec['entry_locked']:
            rates=bydate[entry_date]
            rec['entry_prices']={p:pair_price(p,rates) for p in payload.get('pairs',{})}
            if len(rec['entry_prices'])!=28 or any(v is None for v in rec['entry_prices'].values()):
                raise RuntimeError('Entry matrix incomplete')
            rec['entry_locked']=True
        if rec['entry_locked']:
            ei=dates.index(entry_date)
            for h in HORIZONS:
                k=f't_plus_{h}'
                if k in rec['outcomes']: continue
                xi=ei+h
                if xi>=len(dates): continue
                exit_date=dates[xi]; exit_rates=bydate[exit_date]
                pair_results={}
                for p,meta in payload.get('pairs',{}).items():
                    ep=rec['entry_prices'][p]; xp=pair_price(p,exit_rates)
                    raw=100.0*(xp/ep-1.0)
                    anchor=meta.get('macro_anchor')
                    signed=raw if anchor=='A' else (-raw if anchor=='B' else None)
                    pair_results[p]={
                      'state':meta.get('state'),
                      'robustness_badge':meta.get('robustness_badge'),
                      'macro_anchor':anchor,
                      'entry_price':ep,
                      'exit_price':xp,
                      'raw_return_pct':raw,
                      'signed_macro_return_pct':signed,
                      'hit':(signed>0) if signed is not None else None
                    }
                rec['outcomes'][k]={'exit_fixing_date':exit_date,'pair_results':pair_results}
        state['snapshots'][sid]=rec
    state['latest_ecb_fixing_date']=dates[-1]
    state['guards']={'changes_engine_rules':False,'changes_live_data':False,'changes_oos_baseline':False,'production_promotion':False,'retroactive_label_changes':False}
    OUT.write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':'PASS','latest_ecb_fixing_date':dates[-1],'snapshots':{k:{'entry':v['entry_fixing_date'],'entry_locked':v['entry_locked'],'outcomes':sorted(v['outcomes'])} for k,v in state['snapshots'].items()}},indent=2))

if __name__=='__main__': main()
