#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, html, json, pathlib, re, time, urllib.request
from datetime import datetime

BASE='https://www.bls.gov/news.release/archives/empsit_{stamp}.htm'
UA='Mozilla/5.0 (compatible; GLOBAL-MACRO-FX-QUANT/1.0; strict PIT labour validation)'
TARGET_START='2018-01'
TARGET_END='2026-08'
SEED_REFERENCE='2018-01'
SEED_RELEASE='2018-02-02'
EXPECTED=104

SPECIAL_TRANSITIONS={
  '2025-09': {
    'announced_release_date':'2025-10-03',
    'actual_release_date':'2025-11-20',
    'kind':'RESCHEDULED_2025_LAPSE',
    'evidence_url':'https://www.bls.gov/bls/2025-lapse-revised-release-dates.htm',
    'missing_reference_month':'2025-10',
    'missing_kind':'HOUSEHOLD_SURVEY_NOT_COLLECTED_2025_LAPSE',
    'resume_reference_month':'2025-11',
    'resume_release_date':'2025-12-16',
  },
  '2026-01': {
    'announced_release_date':'2026-02-06',
    'actual_release_date':'2026-02-11',
    'kind':'RESCHEDULED_2026_LAPSE',
    'evidence_url':'https://www.bls.gov/bls/2025-lapse-revised-release-dates.htm',
  },
}


def stamp(iso:str)->str:
    y,m,d=iso.split('-'); return f'{m}{d}{y}'

def fetch_url(url:str)->tuple[bytes,str]:
    last=None
    for wait in (0,2,5,10):
        if wait: time.sleep(wait)
        try:
            req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*;q=0.8','Connection':'close'})
            with urllib.request.urlopen(req,timeout=30) as r:
                return r.read(),r.geturl()
        except Exception as exc: last=exc
    raise RuntimeError(f'BLS fetch failed {url}: {last!r}')

def fetch(release_date:str)->tuple[bytes,str]:
    return fetch_url(BASE.format(stamp=stamp(release_date)))

def plain(raw:bytes)->str:
    s=raw.decode('utf-8','replace')
    s=re.sub(r'(?is)<script.*?</script>|<style.*?</style>',' ',s)
    s=re.sub(r'(?s)<[^>]+>',' ',s)
    s=html.unescape(s).replace('\xa0',' ')
    return ' '.join(s.split())

def month_key(label:str)->str:
    return datetime.strptime(label.strip(),'%B %Y').strftime('%Y-%m')

def iso_date(label:str)->str:
    return datetime.strptime(' '.join(label.split()),'%B %d, %Y').date().isoformat()

def next_month(k:str)->str:
    y,m=map(int,k.split('-')); m+=1
    if m==13: y+=1; m=1
    return f'{y:04d}-{m:02d}'

def parse_release(raw:bytes, expected_release_date:str, expected_ref:str, allow_missing_next:bool=False)->dict:
    text=plain(raw)
    title=re.search(r'THE EMPLOYMENT SITUATION\s+[-–—]{1,2}\s+([A-Za-z]+\s+\d{4})',text,re.I)
    if not title:
        title=re.search(r'THE EMPLOYMENT SITUATION.{0,12}?([A-Za-z]+\s+\d{4})',text,re.I)
    if not title: raise ValueError('employment-situation reference month not found')
    ref=month_key(title.group(1))
    if ref!=expected_ref: raise ValueError(f'expected reference {expected_ref}, got {ref}')

    emb=re.search(
      r'embargoed until\s+8:30\s*a\.m\.\s*\((EST|EDT|ET)\)\s+'
      r'(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday),?\s+)?'
      r'([A-Za-z]+\s+\d{1,2},\s+\d{4})',text,re.I)
    if not emb: raise ValueError(f'embargo timestamp not found for {ref}')
    embargo_date=iso_date(emb.group(2))
    if embargo_date!=expected_release_date:
        raise ValueError(f'archive URL date {expected_release_date} != embargo date {embargo_date}')

    # First-published U-3 headline value. Keep the extraction tightly anchored to
    # "unemployment rate" and the first narrative occurrence before detailed tables.
    prefix=text[:min(len(text),12000)]
    ur=None
    patterns=[
      r'unemployment rate(?:\s+was|\s+is|\s+remained|\s+held|\s+changed little)?(?:\s+at|\s+was)?\s*(\d+(?:\.\d+)?)\s*percent',
      r'unemployment rate[^.]{0,100}?at\s+(\d+(?:\.\d+)?)\s*percent',
    ]
    for p in patterns:
        m=re.search(p,prefix,re.I)
        if m:
            ur=float(m.group(1)); break
    if ur is None: raise ValueError(f'headline unemployment rate not found for {ref}')
    if not (2.0 <= ur <= 15.0): raise ValueError(f'implausible unemployment rate {ur} for {ref}')

    next_patterns=[
      r'The Employment Situation for\s+([A-Za-z]+\s+\d{4})\s+is scheduled to be released on\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday),?\s+([A-Za-z]+\s+\d{1,2},\s+\d{4}),?\s+at\s+8:30\s*a\.m\.\s*\((EST|EDT|ET)\)',
      r'The Employment Situation for\s+([A-Za-z]+\s+\d{4})\s+is scheduled to be released on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4}),?\s+at\s+8:30\s*a\.m\.\s*\((EST|EDT|ET)\)',
      r'The Employment Situation news release for\s+([A-Za-z]+\s+\d{4})\s+is scheduled to be published on\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday),?\s+([A-Za-z]+\s+\d{1,2},\s+\d{4}),?\s+at\s+8:30\s*a\.m\.\s*\((EST|EDT|ET)\)',
      r'The Employment Situation news release for\s+([A-Za-z]+\s+\d{4})\s+is scheduled to be published on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4}),?\s+at\s+8:30\s*a\.m\.\s*\((EST|EDT|ET)\)',
    ]
    nxt=None
    for p in next_patterns:
        nxt=re.search(p,text,re.I)
        if nxt: break
    if not nxt and not allow_missing_next:
        raise ValueError(f'next-release statement not found for {ref}')

    return {
      'reference_month':ref,
      'release_date':expected_release_date,
      'release_time':'08:30',
      'release_timezone':'America/New_York',
      'embargo_tz_abbrev':emb.group(1).upper(),
      'availability_status':'AVAILABLE_STRICT_PIT',
      'unemployment_rate':ur,
      'official_series_id':'LNS14000000',
      'next_reference_month':month_key(nxt.group(1)) if nxt else None,
      'next_release_date':iso_date(nxt.group(2)) if nxt else None,
    }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=pathlib.Path); a=ap.parse_args()
    current_ref=SEED_REFERENCE; current_date=SEED_RELEASE
    rows=[]; errors=[]
    try:
        while True:
            special=SPECIAL_TRANSITIONS.get(current_ref)
            if special and current_date==special['announced_release_date']:
                current_date=special['actual_release_date']
            has_gap=bool(special and special.get('missing_reference_month'))
            raw,url=fetch(current_date)
            row=parse_release(raw,current_date,current_ref,allow_missing_next=has_gap)
            row['source_url']=url; row['source_sha256']=hashlib.sha256(raw).hexdigest()
            if special:
                eraw,efinal=fetch_url(special['evidence_url'])
                row['schedule_exception']=special['kind']
                row['announced_release_date']=special['announced_release_date']
                row['actual_release_date']=special['actual_release_date']
                row['schedule_exception_evidence_url']=efinal
                row['schedule_exception_evidence_sha256']=hashlib.sha256(eraw).hexdigest()
            if TARGET_START <= current_ref <= TARGET_END: rows.append(row)
            if current_ref==TARGET_END: break

            if has_gap:
                # BLS states household survey data were not collected for Oct 2025
                # and will not be collected retroactively. U-3 therefore does not
                # exist for this reference month and must remain unavailable.
                missing={
                  'reference_month':special['missing_reference_month'],
                  'release_date':None,'release_time':None,
                  'release_timezone':'America/New_York',
                  'availability_status':'UNAVAILABLE_OFFICIAL_NOT_PUBLISHED',
                  'unemployment_rate':None,
                  'official_series_id':'LNS14000000',
                  'unavailable_reason':special['missing_kind'],
                  'source_url':row['source_url'],
                  'source_sha256':row['source_sha256'],
                  'next_reference_month':special['resume_reference_month'],
                  'next_release_date':special['resume_release_date'],
                }
                if TARGET_START <= missing['reference_month'] <= TARGET_END: rows.append(missing)
                current_ref=special['resume_reference_month']; current_date=special['resume_release_date']
                time.sleep(0.15); continue

            if row['next_reference_month']!=next_month(current_ref):
                raise ValueError(f'non-consecutive next reference after {current_ref}: {row["next_reference_month"]}')
            current_ref=row['next_reference_month']; current_date=row['next_release_date']
            time.sleep(0.15)
    except Exception as exc:
        errors.append(repr(exc))

    refs=[r['reference_month'] for r in rows]
    available=sum(r['availability_status']=='AVAILABLE_STRICT_PIT' for r in rows)
    unavailable=sum(r['availability_status']=='UNAVAILABLE_OFFICIAL_NOT_PUBLISHED' for r in rows)
    status='CERTIFIABLE_STRICT_PIT_WITH_OFFICIAL_GAP' if not errors and len(rows)==EXPECTED and refs and refs[0]==TARGET_START and refs[-1]==TARGET_END and len(set(refs))==EXPECTED and unavailable==1 else 'WITHHELD'
    semantic=[{k:v for k,v in r.items() if k not in {'source_sha256','schedule_exception_evidence_sha256'}} for r in rows]
    sha=hashlib.sha256(json.dumps(semantic,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    out={
      'schema':'GMFQ_USD_LABOUR_BLS_RELEASE_PIT_V1',
      'status':status,
      'authority':'U.S. Bureau of Labor Statistics',
      'series_contract':{'series_id':'LNS14000000','measure':'U-3 seasonally adjusted unemployment rate','unit':'percent','semantics':'as first published in Employment Situation'},
      'coverage':{'start':TARGET_START,'end':TARGET_END,'expected_months':EXPECTED,'observed_months':len(rows),'materialized_months':available,'official_unavailable_months':unavailable},
      'rows':rows,'errors':errors,'semantic_sha256':sha,
      'invariants':{
        'official_archive_only':True,
        'actual_release_date_required':True,
        'official_embargo_timestamp_required':True,
        'headline_first_published_u3_only':True,
        'current_revised_history_substitution_forbidden':True,
        'october_2025_household_imputation_forbidden':True,
        'production_write':False,
      },
      'policy':{'authorizes_pr123_performance_by_itself':False,'production_signal_authorized':False}
    }
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k!='rows'},indent=2,sort_keys=True))
    if status!='CERTIFIABLE_STRICT_PIT_WITH_OFFICIAL_GAP': raise SystemExit(2)

if __name__=='__main__': main()
