#!/usr/bin/env python3
import json
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OFFICIAL=ROOT/'live_data/sections/MACRO_RELEASE_OFFICIAL_SEED_V1.json'
OUT=ROOT/'live_data/sections/MACRO_CONSENSUS_SECONDARY_V1.json'

G8={'USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD'}
ALIASES={
    'INFLATION':('inflation','consumer price','cpi','price index','prices'),
    'LABOUR':('employment','unemployment','labour','labor','jobless','payroll','claimant'),
    'LABOUR_COST':('employment cost','labour cost','labor cost','wages','earnings'),
    'GROWTH':('gdp','gross domestic product','growth'),
}
MONTHS={m.lower():i for i,m in enumerate(('Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'),1)}

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows=[]
        self._in_tr=False
        self._in_cell=False
        self._cell=[]
        self._row=[]
    def handle_starttag(self,tag,attrs):
        tag=tag.lower()
        if tag=='tr':
            self._in_tr=True; self._row=[]
        elif self._in_tr and tag in {'td','th'}:
            self._in_cell=True; self._cell=[]
    def handle_data(self,data):
        if self._in_cell:
            self._cell.append(data)
    def handle_endtag(self,tag):
        tag=tag.lower()
        if self._in_tr and tag in {'td','th'} and self._in_cell:
            text=' '.join(' '.join(self._cell).split())
            self._row.append(text)
            self._in_cell=False; self._cell=[]
        elif tag=='tr' and self._in_tr:
            if self._row:
                self.rows.append(self._row)
            self._in_tr=False; self._row=[]

def norm(s):
    return re.sub(r'[^a-z0-9]+',' ',str(s or '').lower()).strip()

def iso_day(raw):
    try:
        return datetime.fromisoformat(str(raw).replace('Z','+00:00')).date()
    except Exception:
        try: return date.fromisoformat(str(raw)[:10])
        except Exception: return None

def parse_calendar_date(text,default_year):
    s=' '.join(str(text or '').replace(',',' ').split())
    m=re.search(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})(?:\s+(\d{4}))?\b',s,re.I)
    if not m:
        return None
    mon=MONTHS[m.group(1).lower()]
    day=int(m.group(2)); year=int(m.group(3) or default_year)
    try:
        return date(year,mon,day)
    except ValueError:
        return None

def semantic_score(official,candidate):
    o=norm(official.get('title'))
    c=norm(candidate.get('event'))
    score=0
    if o and c and (o in c or c in o): score+=6
    owords={w for w in o.split() if len(w)>3}
    cwords=set(c.split())
    score+=min(5,len(owords & cwords))
    aliases=ALIASES.get(official.get('event_type'),())
    if any(a in c for a in aliases): score+=4
    return score

def fetch_calendar(start,end):
    currencies='%2C'.join(sorted(G8))
    url=f'https://www.myfxbook.com/forex-economic-calendar/{currencies}'
    req=urllib.request.Request(url,headers={
        'User-Agent':'Mozilla/5.0 (compatible; GMFQ/1.0; +https://github.com/robybizkit77-blip/global-macro-fx-quant)',
        'Accept-Language':'en-US,en;q=0.9',
        'Accept':'text/html,application/xhtml+xml'
    })
    with urllib.request.urlopen(req,timeout=30) as r:
        html=r.read().decode('utf-8','replace')
    parser=TableParser(); parser.feed(html)

    out=[]; current_date=None
    for cells in parser.rows:
        joined=' | '.join(cells)
        maybe_date=parse_calendar_date(joined,start.year)
        if maybe_date and not any(c.strip().upper() in G8 for c in cells):
            current_date=maybe_date
            continue
        ccy_idx=next((i for i,c in enumerate(cells) if c.strip().upper() in G8),None)
        if ccy_idx is None:
            continue
        row_date=parse_calendar_date(cells[0] if cells else '',start.year) or current_date or maybe_date
        if not row_date or row_date<start or row_date>end:
            continue
        impact_idx=next((i for i,c in enumerate(cells) if c.strip().lower() in {'high','medium','low','none'}),None)
        if impact_idx is None or impact_idx<=ccy_idx:
            continue
        event=' '.join(c for c in cells[ccy_idx+1:impact_idx] if c).strip()
        if not event or event.lower().startswith('myfxbook '):
            continue
        tail=cells[impact_idx+1:]
        previous=tail[0].strip() if len(tail)>0 and tail[0].strip() else None
        consensus=tail[1].strip() if len(tail)>1 and tail[1].strip() else None
        actual=tail[2].strip() if len(tail)>2 and tail[2].strip() else None
        out.append({
            'currency':cells[ccy_idx].strip().upper(),
            'event':event,
            'date':row_date.isoformat(),
            'previous':previous,
            'consensus':consensus,
            'actual':actual,
            'impact':cells[impact_idx].strip().title()
        })
    if not parser.rows:
        raise RuntimeError('Myfxbook page returned no parseable table rows')
    return out

def main():
    official=json.loads(OFFICIAL.read_text(encoding='utf-8')).get('events',[])
    today=date.today()
    horizon=today+timedelta(days=90)
    try:
        provider_rows=fetch_calendar(today,horizon)
    except Exception as exc:
        print(json.dumps({'status':'PROVIDER_FETCH_FAILED','provider':'MYFXBOOK_PUBLIC_CALENDAR','error':str(exc),'changed':False,'output':str(OUT.relative_to(ROOT))}))
        raise

    by_ccy={ccy:[] for ccy in G8}
    for row in provider_rows:
        ccy=str(row.get('currency') or '').upper().strip()
        if ccy in by_ccy:
            by_ccy[ccy].append(row)

    rows=[]
    for e in official:
        d=iso_day(e.get('date'))
        ccy=e.get('ccy')
        if ccy not in G8 or not d or d<today or d>horizon:
            continue
        best=None; best_rank=None; best_gap=None
        for cand in by_ccy.get(ccy,[]):
            cd=iso_day(cand.get('date'))
            if not cd:
                continue
            gap=abs((cd-d).days)
            if gap>1:
                continue
            sem=semantic_score(e,cand)
            if sem<4:
                continue
            rank=(10 if gap==0 else 6)+sem
            if best_rank is None or rank>best_rank:
                best_rank=rank; best=cand; best_gap=gap
        if not best:
            continue

        consensus=best.get('consensus')
        previous=best.get('previous')
        if consensus in (None,'') and previous in (None,''):
            continue

        event_key='|'.join([str(e.get('ccy','')),str(e.get('date','')),str(e.get('event_type','')),str(e.get('title',''))])
        status='AVAILABLE' if consensus not in (None,'') else 'PREVIOUS_ONLY'
        rows.append({
            'event_key':event_key,
            'ccy':ccy,
            'official_date':e.get('date'),
            'official_title':e.get('title'),
            'event_type':e.get('event_type'),
            'status':status,
            'consensus':consensus if consensus not in ('',None) else None,
            'previous':previous if previous not in ('',None) else None,
            'unit':None,
            'impact':best.get('impact') or None,
            'provider':'MYFXBOOK_PUBLIC_CALENDAR',
            'provider_event':best.get('event'),
            'provider_country':None,
            'provider_date':best.get('date'),
            'confidence_grade':'B' if best_gap==0 else 'C',
            'date_match_gap_days':best_gap,
            'official_date_overridden':False,
            'actual_ignored_for_pre_release_consensus':True
        })

    status='ACTIVE_PARTIAL' if rows else 'PROVIDER_ACTIVE_NO_MATCHED_VALUES'
    out={
        'schema':'GMFQ_MACRO_CONSENSUS_SECONDARY_V1',
        'status':status,
        'provider':'MYFXBOOK_PUBLIC_CALENDAR',
        'provider_endpoint':'https://www.myfxbook.com/forex-economic-calendar/',
        'provider_field':'consensus',
        'provider_previous_field':'previous',
        'generated_at_utc':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        'events':rows,
        'rules':{
            'never_promote_to_official':True,
            'never_fill_missing_with_zero':True,
            'never_change_release_date':True,
            'context_only':True,
            'core_score_impact':0,
            'estimate_field_is_consensus_only':True,
            'actual_not_used_as_pre_release_consensus':True,
            'official_calendar_remains_primary':True,
            'public_html_secondary_source':True
        }
    }
    old=OUT.read_text(encoding='utf-8') if OUT.exists() else ''
    new=json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    changed=old!=new
    if changed:
        OUT.write_text(new,encoding='utf-8')
    print(json.dumps({'status':'PASS','provider':'MYFXBOOK_PUBLIC_CALENDAR','changed':changed,'provider_rows':len(provider_rows),'matched_events':len(rows),'consensus_available':sum(r['status']=='AVAILABLE' for r in rows),'output':str(OUT.relative_to(ROOT))}))

if __name__=='__main__':
    main()
