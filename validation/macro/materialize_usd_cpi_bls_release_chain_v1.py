#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, html, json, pathlib, re, time, urllib.request
from datetime import datetime

BASE='https://www.bls.gov/news.release/archives/cpi_{stamp}.htm'
UA='Mozilla/5.0 (compatible; GLOBAL-MACRO-FX-QUANT/1.0; strict PIT release-chain validation)'
SEED_RELEASE='2018-01-12'  # official CPI release for December 2017
SEED_REFERENCE='2017-12'
TARGET_START='2018-01'
TARGET_END='2026-08'
EXPECTED=104


def stamp(iso:str)->str:
    y,m,d=iso.split('-'); return f'{m}{d}{y}'

def fetch(release_date:str)->tuple[bytes,str]:
    url=BASE.format(stamp=stamp(release_date)); last=None
    for attempt,wait in enumerate((0,2,5,10),start=1):
        if wait: time.sleep(wait)
        try:
            req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*;q=0.8','Connection':'close'})
            with urllib.request.urlopen(req,timeout=30) as r:
                raw=r.read(); final=r.geturl()
            return raw,final
        except Exception as exc: last=exc
    raise RuntimeError(f'BLS archive fetch failed {release_date}: {last!r}')

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

def parse(raw:bytes, expected_release_date:str)->dict:
    text=plain(raw)
    # Historical BLS HTML contains several separator encodings (dash, em-dash,
    # or a replacement glyph after legacy charset conversion). Anchor on the
    # stable title and accept a short non-alphanumeric separator only.
    m=re.search(r'CONSUMER PRICE INDEX\s+[^A-Za-z0-9]{1,6}\s*([A-Za-z]+\s+\d{4})',text,re.I)
    if not m:
        # Fallback remains tightly anchored to the title and month-year token.
        m=re.search(r'CONSUMER PRICE INDEX.{0,12}?([A-Za-z]+\s+\d{4})',text,re.I)
    if not m: raise ValueError('current reference month not found')
    ref=month_key(m.group(1))
    # Official availability timestamp embedded in release embargo line. Newer
    # releases may use ET rather than explicit EST/EDT and may include weekday
    # between timezone and calendar date; canonical timezone remains NY.
    emb=re.search(
        r'embargoed until\s+8:30\s*a\.m\.\s*\((EST|EDT|ET)\)\s+'
        r'(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday),?\s+)?'
        r'([A-Za-z]+\s+\d{1,2},\s+\d{4})',
        text,re.I)
    if not emb: raise ValueError(f'embargo timestamp not found for {ref}')
    embargo_date=iso_date(emb.group(2))
    if embargo_date != expected_release_date:
        raise ValueError(f'archive URL date {expected_release_date} != embargo date {embargo_date}')
    # Each official CPI release announces the exact next CPI release date.
    nxt=re.search(r'The Consumer Price Index for\s+([A-Za-z]+\s+\d{4})\s+is scheduled to be released on\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday),?\s+([A-Za-z]+\s+\d{1,2},\s+\d{4}),?\s+at\s+8:30\s+a\.m\.\s*\((EST|EDT|ET)\)',text,re.I)
    if not nxt:
        # Some releases omit weekday punctuation; retain strict 8:30 requirement.
        nxt=re.search(r'The Consumer Price Index for\s+([A-Za-z]+\s+\d{4})\s+is scheduled to be released on\s+([A-Za-z]+\s+\d{1,2},\s+\d{4}),?\s+at\s+8:30\s+a\.m\.\s*\((EST|EDT|ET)\)',text,re.I)
    if not nxt: raise ValueError(f'next-release statement not found for {ref}')
    next_ref=month_key(nxt.group(1)); next_date=iso_date(nxt.group(2))
    return {
      'reference_month':ref,
      'release_date':expected_release_date,
      'release_time':'08:30',
      'release_timezone':'America/New_York',
      'embargo_tz_abbrev':emb.group(1).upper(),
      'next_reference_month':next_ref,
      'next_release_date':next_date,
    }

def next_month(k:str)->str:
    y,m=map(int,k.split('-')); m+=1
    if m==13: y+=1; m=1
    return f'{y:04d}-{m:02d}'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True,type=pathlib.Path); a=ap.parse_args()
    current_date=SEED_RELEASE; expected_ref=SEED_REFERENCE
    selected=[]; chain=[]; errors=[]
    try:
        while True:
            raw,url=fetch(current_date); row=parse(raw,current_date)
            if row['reference_month'] != expected_ref:
                raise ValueError(f'expected reference {expected_ref}, got {row["reference_month"]}')
            row['source_url']=url; row['source_sha256']=hashlib.sha256(raw).hexdigest()
            chain.append(row)
            if TARGET_START <= row['reference_month'] <= TARGET_END:
                selected.append(row)
            if row['reference_month']==TARGET_END: break
            if row['next_reference_month'] != next_month(row['reference_month']):
                raise ValueError(f'non-consecutive next reference after {row["reference_month"]}: {row["next_reference_month"]}')
            expected_ref=row['next_reference_month']; current_date=row['next_release_date']
            time.sleep(0.15)
    except Exception as exc:
        errors.append(repr(exc))

    refs=[r['reference_month'] for r in selected]
    status='CERTIFIABLE_RELEASE_CALENDAR' if not errors and len(selected)==EXPECTED and refs[0]==TARGET_START and refs[-1]==TARGET_END and len(set(refs))==EXPECTED else 'WITHHELD'
    semantic_rows=[{k:v for k,v in r.items() if k not in {'source_sha256'}} for r in selected]
    semantic_sha=hashlib.sha256(json.dumps(semantic_rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    out={
      'schema':'GMFQ_USD_CPI_BLS_RELEASE_CHAIN_V1',
      'status':status,
      'authority':'U.S. Bureau of Labor Statistics',
      'coverage':{'start':TARGET_START,'end':TARGET_END,'expected_months':EXPECTED,'observed_months':len(selected)},
      'seed':{'reference_month':SEED_REFERENCE,'release_date':SEED_RELEASE},
      'release_rows':selected,
      'errors':errors,
      'semantic_sha256':semantic_sha,
      'invariants':{
        'official_archive_only':True,
        'each_next_release_date_announced_by_prior_official_release':True,
        'official_embargo_timestamp_required':True,
        'availability_rule':'AT_OR_AFTER_08:30_AMERICA_NEW_YORK_ON_RELEASE_DATE',
        'no_schedule_page_dependency':True,
        'no_inflation_values_materialized':True,
        'certifies_values':False,
        'production_write':False,
      }
    }
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k!='release_rows'},indent=2,sort_keys=True))
    if status!='CERTIFIABLE_RELEASE_CALENDAR': raise SystemExit(2)

if __name__=='__main__': main()
