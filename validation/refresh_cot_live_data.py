from pathlib import Path
import urllib.request,zipfile,io,csv,json,re,math,sys
ROOT=Path('.')
SEC=ROOT/'live_data'/'sections'
URL='https://www.cftc.gov/files/dea/history/deacot2026.zip'
CODES={'EUR':'099741','GBP':'096742','JPY':'097741','CHF':'092741','AUD':'232741','NZD':'112741','CAD':'090741','USD':'098662'}

def load(name): return json.loads((SEC/name).read_text(encoding='utf-8'))
def dump(name,obj): (SEC/name).write_text(json.dumps(obj,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
def fnum(x): return float(str(x).strip().replace(',',''))
def inum(x): return int(round(fnum(x)))
def percentile_104(vals):
    w=[float(x) for x in vals[-104:] if x is not None and math.isfinite(float(x))]
    if not w:return None
    cur=w[-1]
    # inclusive empirical percentile, rounded to dashboard precision
    return round(100.0*sum(x<=cur for x in w)/len(w),6)

chart=load('V250_COT_CHART_DATA.json')
d=load('D.json')
stories=load('V247_COT_STORIES.json')

# A narrative-only reconciliation is intentionally offline: it can only use
# the last already-validated official CFTC chart observation and cannot change
# V250, D, or any model state.
if '--sync-narrative-only' in sys.argv:
    audit={'schema':'GMFQ_COT_NARRATIVE_SYNC_V1','source':'V250_COT_CHART_DATA validated against official CFTC audit','updated':{}}
    for ccy,s in chart.items():
        dt=s['dates'][-1]; net=int(s['net'][-1]); lo=int(s['long'][-1]); sh=int(s['short'][-1]); pct=float(s['percentile'][-1]); netoi=float(s['netoi'][-1])
        week_net=net-int(s['net'][-2]); month_net=net-int(s['net'][-5])
        sign='long' if net > 0 else 'short' if net < 0 else 'neutrale'
        level='positivo' if net > 0 else 'negativo' if net < 0 else 'neutrale'
        flow='migliora' if week_net > 0 else 'peggiora' if week_net < 0 else 'resta invariato'
        story=stories.setdefault(ccy,{})
        story.update({
            'today':f'CFTC al {dt}: fondi net {sign} {net:+,} contratti; Net/OI {netoi:+.1f}% e percentile 104 settimane {pct:.1f}.',
            'w4':f'Variazione su 4 settimane: {month_net:+,} contratti netti; il livello resta {level}.',
            'w1':f'Variazione settimanale: {week_net:+,} contratti netti ({flow}).',
            'why':'Stock, flusso e percentile sono aggiornati dal medesimo record CFTC; il rapporto con il prezzo richiede un refresh prezzo validato separato.',
            'funds':'Flusso CFTC aggiornato',
            'funds_detail':f'Long {lo:,}; short {sh:,}.',
            'price':'WITHHELD',
            'price_detail':'Conferma prezzo non ricalcolata: nessun input prezzo validato in questo refresh CFTC.'
        })
        audit['updated'][ccy]={'as_of':dt,'net':net,'netoi_pct':netoi,'percentile_104w':pct,'week_net':week_net,'four_week_net':month_net}
    dump('V247_COT_STORIES.json',stories)
    (ROOT/'validation'/'COT_NARRATIVE_SYNC_AUDIT_2026-10-04.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(audit,ensure_ascii=False))
    raise SystemExit()

req=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0 GMFQ/1.0'})
raw=urllib.request.urlopen(req,timeout=45).read()
z=zipfile.ZipFile(io.BytesIO(raw)); member=next((n for n in z.namelist() if n.lower().endswith(('.txt','.csv'))),z.namelist()[0])
reader=csv.DictReader(io.StringIO(z.read(member).decode('utf-8-sig',errors='replace')))
rows=list(reader); headers=reader.fieldnames or []

def norm(s): return re.sub(r'[^a-z0-9]+','_',str(s).lower()).strip('_')
nh={norm(h):h for h in headers}
def col(name):
    if name in nh:return nh[name]
    for k,h in nh.items():
        if name in k:return h
    raise RuntimeError('column missing '+name)
code_col=col('cftc_contract_market_code'); date_col=col('as_of_date_in_form_yyyy_mm_dd'); long_col=col('noncommercial_positions_long_all'); short_col=col('noncommercial_positions_short_all'); oi_col=col('open_interest_all')

audit={'schema':'GMFQ_COT_LIVE_REFRESH_V1','source':URL,'updated':{},'warnings':[]}
latest_dates=set()
for ccy,code in CODES.items():
    rr=[r for r in rows if str(r.get(code_col,'')).strip().replace('"','')==code]
    rr.sort(key=lambda r:str(r.get(date_col,'')))
    if not rr: raise RuntimeError(f'no CFTC rows {ccy}')
    r=rr[-1]; dt=str(r[date_col]).strip(); latest_dates.add(dt)
    lo,sh,oi=inum(r[long_col]),inum(r[short_col]),inum(r[oi_col]); net=lo-sh
    s=chart[ccy]
    arrays=['dates','net','long','short','percentile','netoi']
    for k in arrays:
        if k not in s or not isinstance(s[k],list): raise RuntimeError(f'{ccy} chart {k} missing')
    old_date=s['dates'][-1]; old_net=int(s['net'][-1])
    if dt in s['dates']:
        idx=s['dates'].index(dt)
        s['net'][idx]=net; s['long'][idx]=lo; s['short'][idx]=sh; s['netoi'][idx]=round(net/oi*100,3)
        # percentile recalculated after ordering/trimming below
    else:
        s['dates'].append(dt); s['net'].append(net); s['long'].append(lo); s['short'].append(sh); s['percentile'].append(None); s['netoi'].append(round(net/oi*100,3))
    order=sorted(range(len(s['dates'])),key=lambda i:s['dates'][i])
    for k in arrays:
        s[k]=[s[k][i] for i in order]
    # Keep the chart at the canonical 104-week window.
    for k in arrays:s[k]=s[k][-104:]
    s['percentile'][-1]=percentile_104(s['net'])
    pct=s['percentile'][-1]
    if isinstance(d.get('macro'),dict) and isinstance(d['macro'].get(ccy),dict): d['macro'][ccy]['cot_pct']=pct
    # Defensive synchronization of D.cot if its current schema exposes a currency entry.
    dc=d.get('cot')
    entry=None
    if isinstance(dc,dict): entry=dc.get(ccy)
    elif isinstance(dc,list): entry=next((x for x in dc if isinstance(x,dict) and x.get('ccy')==ccy),None)
    if isinstance(entry,dict):
        for k,v in [('date',dt),('as_of',dt),('net',net),('long',lo),('short',sh),('netoi',round(net/oi*100,3)),('percentile',pct),('pct',pct)]:
            if k in entry: entry[k]=v
    audit['updated'][ccy]={'from_date':old_date,'to_date':dt,'old_net':old_net,'net':net,'long':lo,'short':sh,'open_interest':oi,'netoi_pct':round(net/oi*100,3),'percentile_104w':pct}
    # The narrative is a presentation layer, but its numerical claims must
    # always be traceable to the same official CFTC observation as V250.
    # Price confirmation is deliberately withheld here: this job has no
    # validated same-run price input.
    week_net=net-int(s['net'][-2])
    month_net=net-int(s['net'][-5])
    sign='long' if net > 0 else 'short' if net < 0 else 'neutrale'
    level='positivo' if net > 0 else 'negativo' if net < 0 else 'neutrale'
    flow='migliora' if week_net > 0 else 'peggiora' if week_net < 0 else 'resta invariato'
    story=stories.setdefault(ccy,{})
    story.update({
        'today': f'CFTC al {dt}: fondi net {sign} {net:+,} contratti; Net/OI {net/oi*100:+.1f}% e percentile 104 settimane {pct:.1f}.',
        'w4': f'Variazione su 4 settimane: {month_net:+,} contratti netti; il livello resta {level}.',
        'w1': f'Variazione settimanale: {week_net:+,} contratti netti ({flow}).',
        'why': 'Stock, flusso e percentile sono aggiornati dal medesimo record CFTC; il rapporto con il prezzo richiede un refresh prezzo validato separato.',
        'funds': 'Flusso CFTC aggiornato',
        'funds_detail': f'Long {lo:,}; short {sh:,}; open interest {oi:,}.',
        'price': 'WITHHELD',
        'price_detail': 'Conferma prezzo non ricalcolata: nessun input prezzo validato in questo refresh CFTC.'
    })
if len(latest_dates)!=1: raise RuntimeError('CFTC latest dates differ '+repr(latest_dates))
audit['as_of']=next(iter(latest_dates))
dump('V250_COT_CHART_DATA.json',chart); dump('D.json',d)
dump('V247_COT_STORIES.json',stories)
(ROOT/'validation'/'COT_LIVE_REFRESH_AUDIT_2026-10-04.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'as_of':audit['as_of'],'updated':audit['updated']},ensure_ascii=False))
