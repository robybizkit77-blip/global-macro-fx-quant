#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import requests
from bs4 import BeautifulSoup

BASE = 'https://www.asx.com.au/data/futures/reports/EODWebMarketSummary{date}SFN.htm'
UA = 'Mozilla/5.0 GMFQ AUD CB pricing temporal PIT discovery v1'
DATE_RE = re.compile(r'close of trade date\s+(\d{2}/\d{2}/\d{2})', re.I)
PRODUCT_RE = re.compile(r'^[A-Z0-9]{2,3}\s+-\s+')
MONTHS = {m:i for i,m in enumerate(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],1)}


def add_months(d: dt.date, months: int) -> tuple[int,int]:
    x = d.year * 12 + (d.month - 1) + months
    return x // 12, x % 12 + 1


def parse_contract_month(s: str) -> tuple[int,int] | None:
    p = s.split()
    if len(p) != 2 or p[0] not in MONTHS:
        return None
    try:
        return int(p[1]), MONTHS[p[0]]
    except ValueError:
        return None


def parse(html: str) -> tuple[dt.date, dict]:
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(' ', strip=True)
    m = DATE_RE.search(text)
    if not m:
        raise ValueError('ASX trade date missing')
    trade_date = dt.datetime.strptime(m.group(1), '%d/%m/%y').date()
    contracts = {}
    active = False
    for tr in soup.find_all('tr'):
        cells = [c.get_text(' ', strip=True) for c in tr.find_all(['th','td'], recursive=False)]
        if not cells:
            continue
        row = ' '.join(cells)
        if 'IB - 30 Day Interbank Cash Rate' in row:
            active = True
            continue
        if active and PRODUCT_RE.match(row) and 'IB - 30 Day Interbank Cash Rate' not in row:
            break
        if not active or len(cells) < 6:
            continue
        cm = parse_contract_month(cells[0])
        if cm is None:
            continue
        try:
            settlement = float(cells[5].replace(',', ''))
        except ValueError:
            continue
        contracts[cm] = {'label': cells[0], 'settlement': settlement}
    if not contracts:
        raise ValueError('ASX IB contract block missing')
    return trade_date, contracts


def fetch(day: dt.date) -> tuple[dt.date, dict, str, str]:
    url = BASE.format(date=day.strftime('%y%m%d'))
    r = requests.get(url, headers={'User-Agent': UA}, timeout=30)
    r.raise_for_status()
    raw = r.content
    parsed_day, contracts = parse(r.text)
    if parsed_day != day:
        raise ValueError(f'date mismatch requested={day} parsed={parsed_day}')
    return parsed_day, contracts, url, hashlib.sha256(raw).hexdigest()


def locate(anchor: dt.date):
    errors = []
    for i in range(0, 8):
        d = anchor - dt.timedelta(days=i)
        if d.weekday() >= 5:
            continue
        try:
            return fetch(d)
        except Exception as exc:
            errors.append(f'{d}:{type(exc).__name__}')
    return None, errors


def anchors():
    out = []
    for y in range(2018, 2027):
        months = (1,4,7,10) if y < 2026 else (1,4,7,9)
        for m in months:
            out.append(dt.date(y,m,15))
    return out


def semantic_hash(rows):
    # Semantic reproducibility must compare parsed economics, not transport bytes.
    # Raw source SHA256 remains captured per row as independent provenance evidence.
    payload = [{k:r[k] for k in ('anchor','trade_date','mapping')} for r in rows]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',',':')).encode()).hexdigest()


def discover():
    rows = []
    missing = []
    for anchor in anchors():
        found = locate(anchor)
        if found[0] is None:
            missing.append({'anchor': anchor.isoformat(), 'errors': found[1]})
            continue
        trade_date, contracts, url, source_sha = found
        mapping = {}
        mapping_ok = True
        for h, months in [('3m',3),('6m',6),('12m',12)]:
            ym = add_months(trade_date, months)
            c = contracts.get(ym)
            if c is None:
                mapping_ok = False
                mapping[h] = {'target_contract_month': f'{ym[0]:04d}-{ym[1]:02d}', 'status':'MISSING'}
            else:
                mapping[h] = {
                    'target_contract_month': f'{ym[0]:04d}-{ym[1]:02d}',
                    'status':'FOUND',
                    'label':c['label'],
                    'settlement':c['settlement'],
                    'implied_rate':round(100.0-c['settlement'],6),
                }
        rows.append({
            'anchor': anchor.isoformat(),
            'trade_date': trade_date.isoformat(),
            'source_url': url,
            'source_sha256': source_sha,
            'listed_contracts': len(contracts),
            'mapping_ok': mapping_ok,
            'mapping': mapping,
        })
    by_year = {}
    for y in range(2018,2027):
        yr = [r for r in rows if r['anchor'].startswith(str(y))]
        by_year[str(y)] = {
            'anchors_found': len(yr),
            'anchors_mapping_ok': sum(1 for r in yr if r['mapping_ok']),
        }
    complete = len(rows) == len(anchors()) and all(r['mapping_ok'] for r in rows)
    return {
        'schema':'GMFQ_AUD_CB_PRICING_TEMPORAL_PIT_DISCOVERY_V1',
        'status':'PASS' if complete else 'INCOMPLETE',
        'purpose':'Read-only discovery of ASX IB dated archive coverage and deterministic exact-month 3M/6M/12M contract mapping. Not a production certification.',
        'authority':'ASX',
        'instrument':'30 Day Interbank Cash Rate futures (IB)',
        'archive_pattern':BASE,
        'temporal_rule':'same-day use forbidden unless publication timestamp is separately verified; discovery only',
        'mapping_rule':'for each horizon, require the exact listed IB contract month equal to trade-date plus 3/6/12 calendar months; no interpolation and no nearest-contract substitution',
        'expected_anchors':len(anchors()),
        'anchors_found':len(rows),
        'anchors_mapping_ok':sum(1 for r in rows if r['mapping_ok']),
        'by_year':by_year,
        'missing':missing,
        'semantic_discovery_sha256':semantic_hash(rows),
        'changes_live_data':False,
        'changes_engine_rules':False,
        'rows':rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=pathlib.Path, required=True)
    args = ap.parse_args()
    out = discover()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k not in ('rows','missing')}, indent=2))

if __name__ == '__main__':
    main()
