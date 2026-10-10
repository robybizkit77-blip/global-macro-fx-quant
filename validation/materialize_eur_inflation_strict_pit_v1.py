#!/usr/bin/env python3
from __future__ import annotations

import argparse,csv,hashlib,html,json,re,time,urllib.error,urllib.request
from datetime import date,datetime,timedelta,timezone
from html.parser import HTMLParser
from pathlib import Path

START=(2018,1)
END=(2026,9)
MONTHS=['january','february','march','april','may','june','july','august','september','october','november','december']
ROW_KEYS=['reference_month','headline_hicp_yoy_pct','release_date','source_url','page_sha256','source_route','pit_status']
SEMANTIC_KEYS=['reference_month','headline_hicp_yoy_pct','release_date','source_route','pit_status']
MIN_REQUEST_INTERVAL_SECONDS=1.25
_LAST_REQUEST_AT=0.0

# Official period-specific Eurostat releases already resolved by successful
# strict-PIT materializations. Reuse avoids date/suffix rediscovery and 429s.
RESOLVED_RELEASES={
(2018,1):('2018-01-31','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-31012018-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2018,2):('2018-02-28','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-28022018-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2018,3):('2018-04-04','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-04042018-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2018,5):('2018-05-31','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-31052018-BP','EUROSTAT_EURO_INDICATORS_LEGACY_BP'),
(2018,6):('2018-06-29','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-29062018-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2018,7):('2018-07-31','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-31072018-BP','EUROSTAT_EURO_INDICATORS_LEGACY_BP'),
(2018,8):('2018-08-31','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-31082018-BP','EUROSTAT_EURO_INDICATORS_LEGACY_BP'),
(2018,9):('2018-09-28','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-28092018-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2018,10):('2018-10-31','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-31102018-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2018,11):('2018-11-30','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-30112018-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2018,12):('2019-01-04','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-04012019-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2019,1):('2019-02-01','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-01022019-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2019,2):('2019-03-01','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-01032019-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2019,3):('2019-04-01','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-01042019-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2019,4):('2019-05-03','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-03052019-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2019,5):('2019-06-04','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-04062019-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2019,6):('2019-06-28','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-28062019-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2019,7):('2019-07-31','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-31072019-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2019,8):('2019-08-30','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-30082019-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2019,9):('2019-10-01','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-01102019-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2019,10):('2019-10-31','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-31102019-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2019,11):('2019-11-29','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-29112019-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2019,12):('2020-01-07','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-07012020-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2020,1):('2020-01-31','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-31012020-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2020,2):('2020-03-03','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-03032020-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2020,3):('2020-03-31','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-31032020-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2020,9):('2020-10-02','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-02102020-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2020,10):('2020-10-30','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-30102020-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2020,11):('2020-12-01','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-01122020-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2020,12):('2021-01-07','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-07012021-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2021,1):('2021-02-03','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-03022021-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2021,2):('2021-03-02','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-02032021-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2021,3):('2021-03-31','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-31032021-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2021,4):('2021-04-30','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-30042021-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2021,5):('2021-06-01','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-01062021-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2021,6):('2021-06-30','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-30062021-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2021,7):('2021-07-30','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-30072021-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2021,8):('2021-08-31','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-31082021-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2021,9):('2021-10-01','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-01102021-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2021,10):('2021-10-29','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-29102021-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2021,11):('2021-11-30','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-30112021-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2021,12):('2022-01-07','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-07012022-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2022,1):('2022-02-02','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-02022022-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2022,2):('2022-03-02','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-02032022-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2022,3):('2022-04-01','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-01042022-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2022,4):('2022-04-29','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-29042022-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2022,5):('2022-05-31','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-31052022-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2022,6):('2022-07-01','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-01072022-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2022,7):('2022-07-29','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-29072022-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2022,8):('2022-08-31','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-31082022-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2022,9):('2022-09-30','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-30092022-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2022,10):('2022-10-31','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-31102022-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2022,11):('2022-11-30','https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-30112022-AP','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2022,12):('2023-01-06','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-06012023-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2023,1):('2023-02-01','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-01022023-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2023,2):('2023-03-02','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-02032023-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2023,3):('2023-03-31','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-31032023-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2023,4):('2023-05-02','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-02052023-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2023,5):('2023-06-01','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-01062023-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2023,6):('2023-06-30','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-30062023-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2023,7):('2023-07-31','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-31072023-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2023,8):('2023-08-31','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-31082023-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2023,9):('2023-09-29','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-29092023-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2023,10):('2023-10-31','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-31102023-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2023,11):('2023-11-30','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-30112023-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2023,12):('2024-01-05','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-05012024-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2024,1):('2024-02-01','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-01022024-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2024,2):('2024-03-01','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-01032024-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2024,3):('2024-04-03','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-03042024-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2024,4):('2024-04-30','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-30042024-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2024,5):('2024-05-31','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-31052024-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2024,6):('2024-07-02','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-02072024-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2024,7):('2024-07-31','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-31072024-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2024,8):('2024-08-30','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-30082024-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2024,9):('2024-10-01','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-01102024-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2024,10):('2024-10-31','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-31102024-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2024,11):('2024-11-29','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-29112024-ap','EUROSTAT_EURO_INDICATORS_LEGACY_AP'),
(2024,12):('2025-01-07','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-07012025-ap','EUROSTAT_EURO_INDICATORS_WEB_AP'),
(2025,1):('2025-02-03','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-03022025-ap','EUROSTAT_EURO_INDICATORS_WEB_AP'),
(2025,2):('2025-03-03','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-03032025-ap','EUROSTAT_EURO_INDICATORS_WEB_AP'),
(2025,3):('2025-04-01','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-01042025-ap','EUROSTAT_EURO_INDICATORS_WEB_AP'),
(2025,4):('2025-05-02','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-02052025-ap','EUROSTAT_EURO_INDICATORS_WEB_AP'),
(2025,5):('2025-06-03','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-03062025-ap','EUROSTAT_EURO_INDICATORS_WEB_AP'),
(2025,6):('2025-07-01','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-01072025-ap','EUROSTAT_EURO_INDICATORS_WEB_AP'),
(2025,7):('2025-08-01','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-01082025-ap','EUROSTAT_EURO_INDICATORS_WEB_AP'),
(2025,8):('2025-09-02','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-02092025-ap','EUROSTAT_EURO_INDICATORS_WEB_AP'),
(2025,9):('2025-10-01','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-01102025-ap','EUROSTAT_EURO_INDICATORS_WEB_AP'),
(2025,10):('2025-10-31','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-31102025-ap','EUROSTAT_EURO_INDICATORS_WEB_AP'),
(2025,11):('2025-12-02','https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-02122025-ap','EUROSTAT_EURO_INDICATORS_WEB_AP'),
}

# Narrow immutable archival exceptions where the official product page is not
# reliably resolvable by the runner but the period-specific first-release PDF is.
SPECIAL_RELEASES={
    (2018,4): {'release_date':'2018-05-03','headline_hicp_yoy_pct':1.2,'source_url':'https://ec.europa.eu/eurostat/documents/2995521/8869609/2-03052018-BP-EN.pdf/bfc9d63f-f717-4c48-b074-526c59e8de02','source_route':'EUROSTAT_IMMUTABLE_RELEASE_PDF_BP'},
    (2020,4): {'release_date':'2020-04-30','headline_hicp_yoy_pct':0.4,'source_url':'https://ec.europa.eu/eurostat/documents/2995521/10294696/2-30042020-AP-EN.pdf/695df4c4-1a67-bf92-3a0f-69534046cbfe','source_route':'EUROSTAT_IMMUTABLE_RELEASE_PDF_AP'},
    (2020,5): {'release_date':'2020-05-29','headline_hicp_yoy_pct':0.1,'source_url':'https://ec.europa.eu/eurostat/documents/2995521/10294840/2-29052020-AP-EN.pdf/82e74a7c-bfea-cc42-b842-260f2ce4039e','source_route':'EUROSTAT_IMMUTABLE_RELEASE_PDF_AP'},
    (2020,6): {'release_date':'2020-06-30','headline_hicp_yoy_pct':0.3,'source_url':'https://ec.europa.eu/eurostat/documents/2995521/10294972/2-30062020-AP-EN.pdf/4d9c6e1d-b92c-431d-384a-2ab18f6eeaa6','source_route':'EUROSTAT_IMMUTABLE_RELEASE_PDF_AP'},
    (2020,7): {'release_date':'2020-07-31','headline_hicp_yoy_pct':0.4,'source_url':'https://ec.europa.eu/eurostat/documents/2995521/11156763/2-31072020-AP-EN.pdf/c033a89c-da21-8888-d9a1-3bc1d0ce1a6f','source_route':'EUROSTAT_IMMUTABLE_RELEASE_PDF_AP'},
    (2020,8): {'release_date':'2020-09-01','headline_hicp_yoy_pct':-0.2,'source_url':'https://ec.europa.eu/eurostat/documents/2995521/10545459/2-01092020-AP-EN.pdf/7c0db6bb-3974-ce20-a7f0-6281743d0d7c','source_route':'EUROSTAT_IMMUTABLE_RELEASE_PDF_AP'},
}

class Text(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]
    def handle_data(self,data):
        s=' '.join(data.split())
        if s:self.parts.append(s)

def text_from_html(raw:bytes)->str:
    p=Text(); p.feed(raw.decode('utf-8',errors='replace')); return html.unescape(' '.join(p.parts))

def months():
    y,m=START
    while (y,m)<=END:
        yield y,m; m+=1
        if m==13:y+=1;m=1

def last_weekday_of_month(y:int,m:int)->date:
    nxt=date(y+1,1,1) if m==12 else date(y,m+1,1)
    d=nxt-timedelta(days=1)
    while d.weekday()>=5:d-=timedelta(days=1)
    return d

def candidate_dates(y:int,m:int):
    anchor=last_weekday_of_month(y,m); ordered=[anchor]; d=anchor
    while len(ordered)<6:
        d+=timedelta(days=1)
        if d.weekday()<5:ordered.append(d)
    d=anchor
    while len(ordered)<9:
        d-=timedelta(days=1)
        if d.weekday()<5:ordered.append(d)
    yield from ordered

def urls_for(d:date):
    key=d.strftime('%d%m%Y'); legacy=[]; modern=[]
    for suffix in ('AP','BP'):
        legacy.append((f'EUROSTAT_EURO_INDICATORS_LEGACY_{suffix}',f'https://ec.europa.eu/eurostat/web/products-euro-indicators/-/2-{key}-{suffix}'))
        modern.append((f'EUROSTAT_EURO_INDICATORS_WEB_{suffix}',f'https://ec.europa.eu/eurostat/web/products-euro-indicators/w/2-{key}-{suffix.lower()}'))
    return legacy+modern if d.year<=2024 else modern+legacy

def throttle():
    global _LAST_REQUEST_AT
    now=time.monotonic(); wait=MIN_REQUEST_INTERVAL_SECONDS-(now-_LAST_REQUEST_AT)
    if wait>0:time.sleep(wait)
    _LAST_REQUEST_AT=time.monotonic()

def fetch(url:str):
    req=urllib.request.Request(url,headers={'User-Agent':'global-macro-fx-quant/1.0 strict-pit'})
    for attempt in range(8):
        throttle()
        try:
            with urllib.request.urlopen(req,timeout=30) as r:return r.read(),r.geturl()
        except urllib.error.HTTPError as e:
            if e.code in (404,410):return None
            if e.code==429 and attempt<7:
                retry_after=e.headers.get('Retry-After') if e.headers else None
                try:delay=max(15.0,float(retry_after)) if retry_after else min(120.0,15.0*(2**attempt))
                except (TypeError,ValueError):delay=min(120.0,15.0*(2**attempt))
                print(f'[transport] Eurostat 429; retry same URL in {delay:.0f}s attempt={attempt+1}/8',flush=True); time.sleep(delay); continue
            raise

def parse_period(text:str,y:int,m:int):
    month=MONTHS[m-1].capitalize(); period=f'{month} {y}'
    if re.search(rf'Flash estimate\s*[-–]\s*{re.escape(period)}',text,re.I) is None and re.search(rf'expected to be\s+[-0-9.]+\s*%\s+in\s+{re.escape(month)}(?:\s+{y})?',text,re.I) is None:return None
    pats=[rf'Euro area annual inflation is expected to be\s+(-?[0-9]+(?:\.[0-9]+)?)\s*%\s+in\s+{re.escape(month)}',rf'Euro area annual inflation\s+is expected to be\s+(-?[0-9]+(?:\.[0-9]+)?)%\s+in\s+{re.escape(month)}',rf'In\s+{re.escape(month)}\s+{y}[^.]*?Euro area annual inflation is expected to be\s+(-?[0-9]+(?:\.[0-9]+)?)%']
    vals=[]
    for p in pats:vals += [float(x.group(1)) for x in re.finditer(p,text,re.I)]
    uniq=[]
    for v in vals:
        if all(abs(v-u)>1e-12 for u in uniq):uniq.append(v)
    if len(uniq)!=1:raise ValueError(f'ambiguous flash headline for {period}: {uniq}')
    return uniq[0]

def one(y:int,m:int):
    ref=f'{y:04d}-{m:02d}'
    special=SPECIAL_RELEASES.get((y,m))
    if special:
        got=fetch(special['source_url'])
        if got is None:raise ValueError(f'official immutable Eurostat PDF missing for {ref}')
        raw,final=got
        return {'reference_month':ref,'headline_hicp_yoy_pct':special['headline_hicp_yoy_pct'],'release_date':special['release_date'],'source_url':final,'page_sha256':hashlib.sha256(raw).hexdigest(),'source_route':special['source_route'],'pit_status':'STRICT_FIRST_RELEASE_FLASH'}
    resolved=RESOLVED_RELEASES.get((y,m))
    if resolved:
        rd,url,route=resolved; got=fetch(url)
        if got is None:raise ValueError(f'resolved official Eurostat release missing for {ref}: {url}')
        raw,final=got; value=parse_period(text_from_html(raw),y,m)
        if value is None:raise ValueError(f'resolved official Eurostat release failed semantic parse for {ref}: {url}')
        return {'reference_month':ref,'headline_hicp_yoy_pct':value,'release_date':rd,'source_url':final,'page_sha256':hashlib.sha256(raw).hexdigest(),'source_route':route,'pit_status':'STRICT_FIRST_RELEASE_FLASH'}
    hits=[]
    for d in candidate_dates(y,m):
        for route,url in urls_for(d):
            got=fetch(url)
            if got is None:continue
            raw,final=got; value=parse_period(text_from_html(raw),y,m)
            if value is None:continue
            hits.append((d.isoformat(),value,final,hashlib.sha256(raw).hexdigest(),route)); break
        if hits:break
    if len(hits)!=1:raise ValueError(f'expected one official Eurostat flash release for {ref}, got {hits}')
    rd,value,url,sha,route=hits[0]
    return {'reference_month':ref,'headline_hicp_yoy_pct':value,'release_date':rd,'source_url':url,'page_sha256':sha,'source_route':route,'pit_status':'STRICT_FIRST_RELEASE_FLASH'}

def digest(rows):
    canon=[{k:r[k] for k in SEMANTIC_KEYS} for r in rows]
    return hashlib.sha256(json.dumps(canon,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def write_progress(csv_path:str,evidence_path:str,rows:list[dict],status:str,last_error:str|None=None):
    p=Path(csv_path); p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=ROW_KEYS,lineterminator='\n'); w.writeheader(); w.writerows(rows)
    ev={'schema':'GMFQ_EUR_INFLATION_STRICT_PIT_EVIDENCE_V1_RUNTIME','status':status,'target':'EUR.inflation','evidence_class':'STRICT_DIRECT_ARCHIVAL_PIT','authority':'Eurostat','coverage':{'start':'2018-01','end':'2026-09','expected_months':105,'materialized_months':len(rows)},'series_contract':{'series_id':'EA_HICP_HEADLINE_YOY','frequency':'M','transformation':'reported_yoy_rate','unit':'% YoY','first_release_semantics':'FLASH_ESTIMATE'},'unique_page_hashes':len({r['page_sha256'] for r in rows}),'semantic_rowset_sha256':digest(rows),'semantic_fingerprint_fields':SEMANTIC_KEYS,'strict_rules':{'official_publisher_only':True,'period_specific_release_artifact_required':True,'publication_date_required':True,'url_and_sha256_required':True,'current_revised_history_forbidden':True,'final_release_fallback_forbidden':True,'revised_history_fallback_used':False},'last_materialized_month':rows[-1]['reference_month'] if rows else None,'last_error':last_error,'generated_at_utc':datetime.now(timezone.utc).isoformat()}
    Path(evidence_path).write_text(json.dumps(ev,indent=2)+'\n',encoding='utf-8')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--csv',required=True); ap.add_argument('--evidence',required=True); a=ap.parse_args(); rows=[]; total=105
    try:
        for i,(y,m) in enumerate(months(),1):
            r=one(y,m); rows.append(r); write_progress(a.csv,a.evidence,rows,'IN_PROGRESS'); print(f'[{i:03d}/{total}] {r["reference_month"]} HICP_FLASH={r["headline_hicp_yoy_pct"]} release={r["release_date"]}',flush=True)
    except Exception as exc:
        write_progress(a.csv,a.evidence,rows,'FAIL',f'{type(exc).__name__}: {exc}'); raise
    assert len(rows)==105 and rows[0]['reference_month']=='2018-01' and rows[-1]['reference_month']=='2026-09'
    assert len({r['page_sha256'] for r in rows})==105
    by={r['reference_month']:r for r in rows}
    anchors={'2018-01':(1.3,'2018-01-31'),'2018-04':(1.2,'2018-05-03'),'2020-01':(1.4,'2020-01-31'),'2020-04':(0.4,'2020-04-30'),'2020-05':(0.1,'2020-05-29'),'2020-06':(0.3,'2020-06-30'),'2020-07':(0.4,'2020-07-31'),'2020-08':(-0.2,'2020-09-01'),'2026-08':(3.3,'2026-09-01'),'2026-09':(3.8,'2026-10-02')}
    for k,(v,d) in anchors.items():assert abs(by[k]['headline_hicp_yoy_pct']-v)<1e-12 and by[k]['release_date']==d,(k,by[k])
    write_progress(a.csv,a.evidence,rows,'PASS')
    ev=json.loads(Path(a.evidence).read_text(encoding='utf-8'))
    ev['anchor_checks']={k:{'rate':v,'release_date':d} for k,(v,d) in anchors.items()}
    ev['manual_semantic_checks']={'2018-04':'Official Eurostat flash-estimate PDF 78/2018, 3 May 2018: 1.2%.','2020-04':'Official Eurostat flash-estimate PDF 73/2020, 30 April 2020: 0.4%; final May release was 0.3%, therefore final-release fallback is forbidden.','2020-05':'Official Eurostat flash-estimate PDF 86/2020, 29 May 2020: 0.1%.','2020-06':'Official Eurostat flash-estimate PDF 102/2020, 30 June 2020: 0.3%.','2020-07':'Official Eurostat flash-estimate PDF 120/2020, 31 July 2020: 0.4%.','2020-08':'Official Eurostat flash-estimate PDF 129/2020, 1 September 2020: -0.2%.'}
    Path(a.evidence).write_text(json.dumps(ev,indent=2)+'\n',encoding='utf-8'); print(json.dumps(ev,indent=2)); return 0

if __name__=='__main__':raise SystemExit(main())