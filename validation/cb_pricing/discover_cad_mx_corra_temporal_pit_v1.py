#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import time

import requests
from bs4 import BeautifulSoup

BASE = 'https://www.m-x.ca/en/trading/data/market-review'
UA = 'Mozilla/5.0 GMFQ CAD CB pricing temporal PIT discovery v1'
DATE_RE = re.compile(r'([A-Z][a-z]+) (\d{1,2}), (20\d{2})')
CONTRACT_RE = re.compile(r'^(MR|JN|SE|DE)\s+(\d{2})$')
MONTH_CODE = {'MR': 3, 'JN': 6, 'SE': 9, 'DE': 12}
MONTH_LABEL = {3: 'MR', 6: 'JN', 9: 'SE', 12: 'DE'}


def add_months(d: dt.date, months: int) -> tuple[int, int]:
    x = d.year * 12 + (d.month - 1) + months
    return x // 12, x % 12 + 1


def floor_standard_quarter(year: int, month: int) -> tuple[int, int]:
    q = max(m for m in (3, 6, 9, 12) if m <= month) if month >= 3 else 12
    if month < 3:
        return year - 1, 12
    return year, q


def contract_key(year: int, month: int) -> str:
    return f'{MONTH_LABEL[month]} {year % 100:02d}'


def parse(html: str) -> tuple[dt.date, dict]:
    soup = BeautifulSoup(html, 'html.parser')
    page_date = None
    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4']):
        m = DATE_RE.fullmatch(tag.get_text(' ', strip=True))
        if m:
            page_date = dt.datetime.strptime(' '.join(m.groups()), '%B %d %Y').date()
            break
    if page_date is None:
        raise ValueError('market review date missing')
    title = soup.find(['th', 'td'], string=re.compile(r'^Three-Month CORRA Futures \(CRA\)$'))
    if title is None:
        raise ValueError('CRA table heading missing')
    table = title.find_parent('table')
    if table is None:
        raise ValueError('CRA table missing')
    contracts = {}
    for tr in table.find_all('tr'):
        cells = [c.get_text(' ', strip=True) for c in tr.find_all(['th', 'td'])]
        if len(cells) != 8 or not CONTRACT_RE.fullmatch(cells[0]):
            continue
        m = CONTRACT_RE.fullmatch(cells[0])
        year = 2000 + int(m.group(2))
        month = MONTH_CODE[m.group(1)]
        try:
            settlement = float(cells[4])
            volume = int(cells[6].replace(',', ''))
            open_interest = int(cells[7].replace(',', ''))
        except ValueError as exc:
            raise ValueError(f'CRA numeric parse failed: {cells}') from exc
        contracts[(year, month)] = {
            'label': cells[0],
            'settlement': settlement,
            'volume': volume,
            'open_interest': open_interest,
        }
    if not contracts:
        raise ValueError('CRA rows missing')
    return page_date, contracts


def get(rid: int, session: requests.Session) -> tuple[dt.date, dict, str, str]:
    r = session.get(BASE, params={'id': rid}, headers={'User-Agent': UA}, timeout=25)
    r.raise_for_status()
    raw = r.content
    d, contracts = parse(r.text)
    return d, contracts, r.url, hashlib.sha256(raw).hexdigest()


def anchors() -> list[dt.date]:
    out = []
    for y in range(2018, 2027):
        months = (1, 4, 7, 10) if y < 2026 else (1, 4, 7, 9)
        for m in months:
            out.append(dt.date(y, m, 15))
    return out


def coarse_index(session: requests.Session) -> list[tuple[int, dt.date]]:
    points = []
    for rid in range(3600, 6401, 100):
        try:
            d, _, _, _ = get(rid, session)
            points.append((rid, d))
        except Exception:
            continue
        time.sleep(0.03)
    points.sort(key=lambda x: x[1])
    return points


def estimated_id(target: dt.date, points: list[tuple[int, dt.date]]) -> int | None:
    before = [p for p in points if p[1] <= target]
    after = [p for p in points if p[1] >= target]
    if before and after:
        a = before[-1]
        b = after[0]
        if a[1] == b[1]:
            return a[0]
        frac = (target - a[1]).days / (b[1] - a[1]).days
        return round(a[0] + frac * (b[0] - a[0]))
    if before:
        rid, d = before[-1]
        return round(rid + (target - d).days * 5 / 7)
    if after:
        rid, d = after[0]
        return round(rid - (d - target).days * 5 / 7)
    return None


def locate(anchor: dt.date, points, session):
    eid = estimated_id(anchor, points)
    if eid is None:
        return None, ['no-id-estimate']
    candidates = []
    # Market Review IDs are approximately session-sequential. Search a conservative
    # local window and choose the latest review on/before the anchor.
    for rid in range(max(1, eid - 22), eid + 23):
        try:
            d, contracts, url, sha = get(rid, session)
        except Exception:
            continue
        if d <= anchor and (anchor - d).days <= 10:
            candidates.append((d, rid, contracts, url, sha))
        time.sleep(0.02)
    if not candidates:
        return None, [f'no review within 10 calendar days on/before anchor around id {eid}']
    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[-1], []


def mapping_for(trade_date: dt.date, contracts: dict):
    out = {}
    ok = True
    for horizon, months in (('3m', 3), ('6m', 6), ('12m', 12)):
        ty, tm = add_months(trade_date, months)
        cy, cm = floor_standard_quarter(ty, tm)
        key = (cy, cm)
        c = contracts.get(key)
        if c is None:
            ok = False
            out[horizon] = {
                'target_horizon_month': f'{ty:04d}-{tm:02d}',
                'canonical_contract_month': f'{cy:04d}-{cm:02d}',
                'canonical_contract_label': contract_key(cy, cm),
                'status': 'MISSING'
            }
        else:
            out[horizon] = {
                'target_horizon_month': f'{ty:04d}-{tm:02d}',
                'canonical_contract_month': f'{cy:04d}-{cm:02d}',
                'canonical_contract_label': c['label'],
                'status': 'FOUND',
                'settlement': c['settlement'],
                'implied_rate': round(100.0 - c['settlement'], 6),
                'volume': c['volume'],
                'open_interest': c['open_interest'],
            }
    return ok, out


def semantic_hash(rows):
    payload = [{k: r[k] for k in ('anchor', 'trade_date', 'market_review_id', 'mapping')} for r in rows]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def discover():
    with requests.Session() as session:
        points = coarse_index(session)
        rows, missing = [], []
        for anchor in anchors():
            found, errors = locate(anchor, points, session)
            if found is None:
                missing.append({'anchor': anchor.isoformat(), 'errors': errors})
                continue
            d, rid, contracts, url, source_sha = found
            mapping_ok, mapping = mapping_for(d, contracts)
            rows.append({
                'anchor': anchor.isoformat(),
                'trade_date': d.isoformat(),
                'market_review_id': rid,
                'source_url': url,
                'source_sha256': source_sha,
                'listed_contracts': len(contracts),
                'mapping_ok': mapping_ok,
                'mapping': mapping,
            })
    by_year = {}
    for y in range(2018, 2027):
        yr = [r for r in rows if r['anchor'].startswith(str(y))]
        by_year[str(y)] = {
            'anchors_found': len(yr),
            'anchors_mapping_ok': sum(1 for r in yr if r['mapping_ok'])
        }
    complete = len(rows) == len(anchors()) and all(r['mapping_ok'] for r in rows)
    return {
        'schema': 'GMFQ_CAD_CB_PRICING_TEMPORAL_PIT_DISCOVERY_V1',
        'status': 'PASS' if complete else 'INCOMPLETE',
        'purpose': 'Read-only discovery of official Montréal Exchange Market Review CRA historical coverage and dynamic canonical quarterly horizon mapping. Not production certification.',
        'authority': 'Montréal Exchange',
        'instrument': 'Three-Month CORRA Futures (CRA)',
        'archive_endpoint': BASE,
        'temporal_rule': 'same-day use forbidden unless publication timestamp is separately verified; discovery only',
        'mapping_rule': 'for 3M/6M/12M target horizon month, use the standard CRA quarter month (Mar/Jun/Sep/Dec) on or immediately before the target month; no interpolation and no current-contract-label reuse',
        'expected_anchors': len(anchors()),
        'anchors_found': len(rows),
        'anchors_mapping_ok': sum(1 for r in rows if r['mapping_ok']),
        'coarse_index_points': len(points),
        'by_year': by_year,
        'missing': missing,
        'semantic_discovery_sha256': semantic_hash(rows),
        'changes_live_data': False,
        'changes_engine_rules': False,
        'rows': rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=pathlib.Path, required=True)
    args = ap.parse_args()
    out = discover()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in out.items() if k not in ('rows', 'missing')}, indent=2))


if __name__ == '__main__':
    main()
