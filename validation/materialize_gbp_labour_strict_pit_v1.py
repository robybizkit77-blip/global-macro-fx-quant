#!/usr/bin/env python3
"""Materialise ONS first-release UK unemployment bulletins, fail closed.

The ONS MGSX runtime series stores the final month of the rolling three-month
LFS estimate.  This collector deliberately reads the immutable monthly
statistical-bulletin page for each release; it never uses the current ONS time
series API, whose history can be revised.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

BASE = 'https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/bulletins/uklabourmarket'
UA = 'global-macro-fx-quant/strict-pit-gbp-labour-v1'
MONTHS = ('January','February','March','April','May','June','July','August','September','October','November','December')
FIELDS = ('reference_month','rolling_period','headline_unemployment_rate_pct','release_date','source_url','page_sha256','pit_status')
SEMANTIC = ('reference_month','rolling_period','headline_unemployment_rate_pct','release_date','pit_status')


def month_range(start: tuple[int, int], end: tuple[int, int]):
    y, m = start
    while (y, m) <= end:
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def add_months(y: int, m: int, n: int) -> tuple[int, int]:
    return (y * 12 + (m - 1) + n) // 12, (y * 12 + (m - 1) + n) % 12 + 1


def rolling_period(y: int, m: int) -> str:
    sy, sm = add_months(y, m, -2)
    return f'{MONTHS[sm - 1]} {sy} to {MONTHS[m - 1]} {y}'


def fetch(url: str) -> tuple[bytes, str]:
    req = Request(url, headers={'User-Agent': UA, 'Accept-Language': 'en-GB,en;q=0.9'})
    with urlopen(req, timeout=45) as response:
        return response.read(), response.geturl()


def plain(raw: bytes) -> str:
    body = raw.decode('utf-8', errors='replace')
    body = re.sub(r'<(?:script|style)\b.*?</(?:script|style)>', ' ', body, flags=re.I | re.S)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', body))).strip()


def release_date(text: str) -> str:
    found = re.search(r'\bRelease date:\s*([0-9]{1,2})\s+([A-Z][a-z]+)\s+(20[0-9]{2})\b', text)
    if not found or found.group(2) not in MONTHS:
        raise ValueError('official ONS release date not found')
    return date(int(found.group(3)), MONTHS.index(found.group(2)) + 1, int(found.group(1))).isoformat()


def headline(text: str, period: str) -> float:
    # Scope to the opening release summary.  The rest of an ONS bulletin
    # intentionally contains historical comparisons and must not be searched.
    start = text.find('Main points')
    if start < 0:
        start = text.find('Other pages in this release')
    if start < 0:
        raise ValueError('ONS opening summary marker not found')
    section = text[start:start + 6000]
    if period not in section:
        raise ValueError(f'expected rolling period absent from ONS opening summary: {period}')
    escaped = re.escape(period)
    patterns = (
        rf'\b(?:UK )?unemployment rate(?: for (?:people|all people)(?: aged 16(?: years)? and over)?)?\s+(?:for|in)\s+{escaped}\b[^.]{0,220}?\b(?:was|at|to)\s*([0-9]+(?:\.[0-9]+)?)\s*%',
        rf'\b(?:UK )?unemployment rate(?: for (?:people|all people)(?: aged 16(?: years)? and over)?)?\b[^.]{0,140}?\b{escaped}\b[^.]{0,180}?\b(?:was|at|to)\s*([0-9]+(?:\.[0-9]+)?)\s*%',
        rf'\b{escaped}\b[^.]{0,150}?\b(?:UK )?unemployment rate(?: for (?:people|all people))?\b[^.]{0,120}?\b(?:was|at|to)\s*([0-9]+(?:\.[0-9]+)?)\s*%',
    )
    values = [float(m.group(1)) for pat in patterns for m in re.finditer(pat, section, flags=re.I)]
    values = list(dict.fromkeys(values))
    if len(values) != 1:
        raise ValueError(f'ambiguous or missing exact ONS unemployment headline for {period}: {values}')
    return values[0]


def digest(rows, keys: tuple[str, ...]) -> str:
    payload = [{key: row[key] for key in keys} for row in rows]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def one(y: int, m: int) -> dict[str, object]:
    # The bulletin name is the publication month, not the reference month.
    ry, rm = add_months(y, m, 2)
    slug = f'{MONTHS[rm - 1].lower()}{ry}'
    raw, final_url = fetch(f'{BASE}/{slug}')
    text = plain(raw)
    expected_title = f'{MONTHS[rm - 1]} {ry}'
    if not re.search(rf'\b(?:UK labour market|Labour market overview, UK):\s*{re.escape(expected_title)}\b', text, re.I):
        raise ValueError(f'ONS page identity mismatch for {slug}')
    period = rolling_period(y, m)
    return {
        'reference_month': f'{y:04d}-{m:02d}',
        'rolling_period': period,
        'headline_unemployment_rate_pct': headline(text, period),
        'release_date': release_date(text),
        'source_url': final_url,
        'page_sha256': hashlib.sha256(raw).hexdigest(),
        'pit_status': 'STRICT_FIRST_RELEASE',
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', required=True, type=Path)
    ap.add_argument('--evidence', required=True, type=Path)
    args = ap.parse_args()
    target = list(month_range((2018, 1), (2026, 6)))
    rows = []
    for i, (y, m) in enumerate(target, 1):
        row = one(y, m)
        rows.append(row)
        print(f'[{i:03d}/{len(target)}] {row["reference_month"]} {row["rolling_period"]}={row["headline_unemployment_rate_pct"]} release={row["release_date"]}', flush=True)
        time.sleep(0.03)
    if len(rows) != 102 or len({r['reference_month'] for r in rows}) != 102:
        raise ValueError('incomplete or duplicate GBP rolling-month coverage')
    if len({r['page_sha256'] for r in rows}) != 102:
        raise ValueError('a period-specific ONS page hash was reused')
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
    evidence = {
        'schema': 'GMFQ_GBP_LABOUR_STRICT_PIT_EVIDENCE_V1_RUNTIME', 'status': 'PASS',
        'target': 'GBP.labour', 'evidence_class': 'STRICT_DIRECT_ARCHIVAL_PIT',
        'authority': 'UK Office for National Statistics',
        'coverage': {'start': '2018-01', 'end': '2026-06', 'expected_months': 102, 'materialized_months': len(rows)},
        'series_contract': {'series_id': 'MGSX', 'frequency': 'M', 'transformation': 'level', 'unit': '%', 'storage_month': 'final month of rolling three-month window'},
        'route_counts': {'ONS_PERIOD_SPECIFIC_UK_LABOUR_MARKET_BULLETIN': len(rows)},
        'unique_page_hashes': len({r['page_sha256'] for r in rows}),
        'semantic_rowset_sha256': digest(rows, SEMANTIC), 'raw_fetch_rowset_sha256': digest(rows, FIELDS),
        'strict_rules': {'official_publisher_only': True, 'period_specific_release_artifact_required': True, 'publication_date_required': True, 'url_and_sha256_required': True, 'current_revised_history_forbidden': True, 'revised_history_fallback_used': False},
        'changes_live_data': False, 'changes_engine_rules': False,
    }
    args.evidence.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(evidence, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
