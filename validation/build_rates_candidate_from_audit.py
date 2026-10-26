#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json, pathlib, sys
from datetime import date, timedelta

ROOT=pathlib.Path(__file__).resolve().parents[1]
DEFAULT_CURRENT=ROOT/'live_data'/'sections'/'NATIVE_RATES_DATA.json'
SUPPORTED={'USD','EUR','GBP','JPY','CAD','AUD'}
SOURCE_LABELS={
 'USD':'U.S. Department of the Treasury · Daily Par Yield Curve',
 'EUR':'European Central Bank · AAA Svensson spot curve',
 'GBP':'Bank of England · UK nominal government zero-coupon spot curve',
 'JPY':'Japan Ministry of Finance · JGB Interest Rate',
 'CAD':'Bank of Canada · benchmark Government of Canada bond yields',
 'AUD':'Reserve Bank of Australia · F2 Capital Market Yields – Government Bonds – Daily',
}

def hist_points(obj,key):
    h=obj.get(key) or {}; ds=h.get('dates') or []; vs=h.get('values') or []
    if len(ds)!=len(vs): raise ValueError(f'{key}: dates/values length mismatch')
    return [(str(d),float(v)) for d,v in zip(ds,vs)]

def reference_point(obj,key,end_date):
    cutoff=(date.fromisoformat(end_date)-timedelta(days=7)).isoformat()
    pts=[p for p in hist_points(obj,key) if p[0] <= cutoff]
    if not pts: raise ValueError(f'{key}: no same-basis history on/before {cutoff}')
    return max(pts,key=lambda x:x[0]), cutoff

def append_hist(obj,key,dt,val):
    h=obj.get(key)
    if not isinstance(h,dict): raise ValueError(f'{key}: missing history')
    ds=h.setdefault('dates',[]); vs=h.setdefault('values',[])
    if len(ds)!=len(vs): raise ValueError(f'{key}: dates/values length mismatch')
    if dt in ds: vs[ds.index(dt)]=val
    else: ds.append(dt); vs.append(val)
    h['last_date']=dt; h['last_value']=val

def classify(d2,d10):
    if d2>0 and d10>0: return 'Bear steepening' if d10>d2 else 'Bear flattening'
    if d2<0 and d10<0: return 'Bull steepening' if d2<d10 else 'Bull flattening'
    return 'Movimento misto'

# The exact original ECB AAA spot 2Y+10Y values for the eight reliable
# historical dates observed as of 2026-10-26. The preceding legacy history
# is NOT on a uniform source basis and must remain quarantined. Values from
# current ECB official publisher parity QA (PR #642).
EUR_CLEAN_TAIL={
    '2026-10-13':(3.0815162392,3.4917781650),
    '2026-10-14':(3.0890919460,3.5107961880),
    '2026-10-15':(2.9927412165,3.3904255140),
    '2026-10-16':(3.0299726083,3.4444646497),
    '2026-10-19':(3.0533254392,3.4690828084),
    '2026-10-20':(3.0280750033,3.4401015770),
    '2026-10-21':(3.0281868841,3.4291547786),
    '2026-10-22':(3.0074951382,3.3844008945),
}
EUR_LEGACY_STATUS='SEPARATE_BASIS_CURRENT_SNAPSHOT_NOT_SPLICED'
EUR_LEGACY_QUALITY='LEGACY_NOT_SAME_BASIS_WITH_VALIDATED_25SEP'
EUR_APPROVED_STATUS='FULL_ECB_SAME_BASIS_2Y_10Y_OFFICIAL_PUBLISHED'


def eur_daily_append_source_gate(obj, new_date):
    """Block EUR update if pre-existing ECB value/date provenance drifts.

    This intentionally checks only the publisher-reconciled clean source
    suffix; it does NOT re-certify or relabel the older legacy history.
    Updating no EUR is a reason to leave legacy unchanged, not to fail
    USD/JPY/CAD/AUD/GBP daily updates.
    """
    import math
    if (not isinstance(obj,dict) or
        'European Central Bank' not in str(obj.get('source','')) or
        'AAA Svensson' not in str(obj.get('source','')) or
        obj.get('quality')!='FULL_CURRENT_OFFICIAL'):
        raise ValueError('EUR source identity / official snapshot not verified')
    status=obj.get('history_status')
    if status==EUR_LEGACY_STATUS:
        if obj.get('history2_quality')!=EUR_LEGACY_QUALITY:
            raise ValueError('EUR legacy two-year history quarantine label changed')
        # These histories continue to be explicitly NON-comparable before
        # the verified suffix, even when the latest snapshot is official.
    elif status==EUR_APPROVED_STATUS:
        if (obj.get('history2_quality')!='ECB_ORIGINAL_2Y_FULL_HISTORICAL_LATEST_VINTAGE_NOT_PIT'
            or obj.get('history10_quality')!='ECB_ORIGINAL_10Y_FULL_HISTORICAL_LATEST_VINTAGE_NOT_PIT'):
            raise ValueError('EUR 2Y/10Y approved full-source provenance incomplete')
    else:
        raise ValueError('EUR historical curve provenance not approved for daily append')
    pts={}
    for key in ('history2','history10'):
        raw=hist_points(obj,key)
        dates=[d for d,_ in raw]
        if not dates or len(dates)!=len(set(dates)) or dates!=sorted(dates):
            raise ValueError('EUR '+key+' history duplicated or unordered')
        if any(len(d)!=10 or date.fromisoformat(d).isoformat()!=d for d in dates):
            raise ValueError('EUR '+key+' history date not ISO')
        if dates[-1]!=obj.get('date'):
            raise ValueError('EUR '+key+' last date not equal to current')
        if any(not math.isfinite(y) for _,y in raw):
            raise ValueError('EUR '+key+' non-finite rate')
        pts[key]=dict(raw)
    if set(pts['history2'])!=set(pts['history10']):
        raise ValueError('EUR paired 2Y/10Y historical calendar diverges')
    for d,(y2,y10) in EUR_CLEAN_TAIL.items():
        if (d not in pts['history2'] or
            abs(pts['history2'][d]-y2)>0.000005 or
            abs(pts['history10'][d]-y10)>0.000005):
            raise ValueError('EUR verified official 2Y/10Y clean tail drift on '+d)
    if (abs(float(obj['2Y'])-pts['history2'][obj['date']])>0.000005 or
        abs(float(obj['10Y'])-pts['history10'][obj['date']])>0.000005):
        raise ValueError('EUR latest snapshot vs history value mismatch')
    if not date.fromisoformat(new_date)>date.fromisoformat(obj['date']):
        raise ValueError('EUR new official observation does not advance')
    if (date.fromisoformat(new_date)-date.fromisoformat(obj['date'])).days>12:
        raise ValueError('EUR official source gap >12 calendar days: need history recovery')
    cutoff=(date.fromisoformat(new_date)-timedelta(days=7)).isoformat()
    refs=[d for d in pts['history2'] if d<=cutoff]
    if not refs or max(refs)<'2026-10-13':
        raise ValueError('EUR weekly reference crosses historically incompatible legacy basis')
    return {'source':'ECB_AAA_SVENSSON_2Y10Y',
            'source_clean_tail_from':'2026-10-13',
            'history_status':status,
            'weekly_ref':max(refs),
            'historical_first_release_pit_certified':False,
            'historical_legacy_basis_quarantined':status==EUR_LEGACY_STATUS}



def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--audit',required=True)
    ap.add_argument('--output',required=True)
    ap.add_argument('--current-rates',default=str(DEFAULT_CURRENT))
    a=ap.parse_args()
    audit=json.load(open(a.audit))
    if audit.get('status')!='PASS': raise SystemExit('unified audit is not PASS')
    updates=list(audit.get('summary',{}).get('updates_available') or [])
    if len(updates)!=len(set(updates)): raise SystemExit('duplicate UPDATE_AVAILABLE currencies: '+repr(updates))
    unsupported=[c for c in updates if c not in SUPPORTED]
    if unsupported: raise SystemExit('UPDATE_AVAILABLE without generic live-fetch support: '+repr(unsupported))
    cur=json.load(open(a.current_rates)); out=copy.deepcopy(cur)
    summary={'status':'NO_UPDATES' if not updates else 'CANDIDATE_READY',
             'changed_currencies':[],'currencies':{},'quarantined_currencies':{}}
    for c in updates:
        row=audit['currencies'][c]
        if row.get('coverage_mode')!='LIVE_FETCH': raise SystemExit(f'{c}: update is not from LIVE_FETCH')
        src=row.get('official') or {}
        dt=str(src.get('date')); y2=float(src['2Y']); y10=float(src['10Y'])
        old=cur[c]
        if dt <= str(old.get('date')): raise SystemExit(f'{c}: non-advancing update {dt} <= {old.get("date")}')
        if c=='EUR':
            try:
                proof=eur_daily_append_source_gate(old,dt)
            except (ValueError,KeyError,TypeError,OverflowError) as err:
                summary['quarantined_currencies']['EUR']={
                    'status':'DAILY_OFFICIAL_NEW_SNAPSHOT_QUARANTINED',
                    'reason':str(err),
                    'historical_first_release_pit_certified':False,
                    'existing_eur_history_unchanged':True,
                    'other_currency_updates_permitted':True}
                continue
            summary['currencies']['EUR']={'source_parity_guard':proof}
        obj=out[c]
        (r2d,r2),cutoff=reference_point(obj,'history2',dt)
        (r10d,r10),_=reference_point(obj,'history10',dt)
        d2=round((y2-r2)*100,1); d10=round((y10-r10)*100,1)
        label=SOURCE_LABELS[c]
        obj['date']=dt; obj['source']=f'{label} · {dt}'; obj['quality']='FULL_CURRENT_OFFICIAL'
        obj['2Y']=y2; obj['10Y']=y10; obj['curve_bp']=round((y10-y2)*100,1)
        obj['chg2_bp']=d2; obj['chg10_bp']=d10; obj['curve_state']=classify(d2,d10)
        for t in obj.get('tenors',[]):
            if t.get('tenor')=='2Y': t['value']=y2; t['date']=dt
            if t.get('tenor')=='10Y': t['value']=y10; t['date']=dt
        append_hist(obj,'history2',dt,y2); append_hist(obj,'history10',dt,y10)
        obj['freshness_status']='CURRENT_OFFICIAL_SAME_BASIS'
        obj['freshness_note']=f'Official same-basis 2Y/10Y updated through {dt}.'
        obj['weekly2_validation']={'start_date':r2d,'start_value':r2,'end_date':dt,'end_value':y2,'change_bp':d2,'source':f'{label} · {dt}','note':f'Same-basis change from latest observation on/before {cutoff}.'}
        obj['weekly10_validation']={'start_date':r10d,'start_value':r10,'end_date':dt,'end_value':y10,'change_bp':d10,'source':f'{label} · {dt}','note':f'Same-basis change from latest observation on/before {cutoff}.'}
        summary['changed_currencies'].append(c)
        summary['currencies'][c]={**summary['currencies'].get(c,{}),
            'old_date':old.get('date'),'new_date':dt,'2Y':y2,'10Y':y10,'curve_bp':obj['curve_bp'],
            'reference_2Y_date':r2d,'reference_10Y_date':r10d,'chg2_bp':d2,
            'chg10_bp':d10,'curve_state':obj['curve_state']}
    summary['status']='CANDIDATE_READY' if summary['changed_currencies'] else 'NO_UPDATES'
    changed=[c for c in cur if cur[c]!=out[c]]
    if len(changed)!=len(set(changed)): raise SystemExit('duplicate changed currencies: '+repr(changed))
    if set(changed)!=set(summary['changed_currencies']): raise SystemExit(f'scope mismatch expected={summary["changed_currencies"]} actual={changed}')
    pathlib.Path(a.output).write_text(json.dumps(out,separators=(',',':'),ensure_ascii=False)+'\n')
    print(json.dumps(summary,indent=2,ensure_ascii=False))
    return 0
if __name__=='__main__': sys.exit(main())
