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
from urllib.error import HTTPError
from pathlib import Path
from urllib.request import Request, urlopen

BASE = 'https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/bulletins/uklabourmarket'
EMPLOYMENT_BASE = 'https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/employmentandemployeetypes/bulletins/employmentintheuk'
UA = 'global-macro-fx-quant/strict-pit-gbp-labour-v1'
MONTHS = ('January','February','March','April','May','June','July','August','September','October','November','December')
FIELDS = ('reference_month','rolling_period','source_rolling_period','headline_unemployment_rate_pct','release_date','source_route','source_url','page_sha256','pit_status')
SEMANTIC = ('reference_month','rolling_period','source_rolling_period','headline_unemployment_rate_pct','release_date','source_route','pit_status')


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


def page_period_variants(y: int, m: int) -> tuple[str, ...]:
    canonical = rolling_period(y, m)
    sy, _ = add_months(y, m, -2)
    # ONS commonly prints a same-year window as "January to March 2023".
    # Keep this explicitly mapped rather than accepting arbitrary contractions.
    compact = f'{MONTHS[add_months(y, m, -2)[1] - 1]} to {MONTHS[m - 1]} {y}' if sy == y else canonical
    return tuple(dict.fromkeys((canonical, compact)))


def fetch(url: str) -> tuple[bytes, str]:
    req = Request(url, headers={'User-Agent': UA, 'Accept-Language': 'en-GB,en;q=0.9'})
    # The first full chain hit ONS's explicit 429 limit after seven pages.
    # Retry only that same official URL, preserving fail-closed behaviour for
    # any other HTTP status or an exhausted official rate-limit response.
    for attempt in range(5):
        try:
            with urlopen(req, timeout=45) as response:
                return response.read(), response.geturl()
        except HTTPError as exc:
            if exc.code != 429 or attempt == 4:
                raise
            time.sleep(2 ** attempt)
    raise AssertionError('unreachable')


def plain(raw: bytes) -> str:
    body = raw.decode('utf-8', errors='replace')
    body = re.sub(r'<(?:script|style)\b.*?</(?:script|style)>', ' ', body, flags=re.I | re.S)
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', body))).strip()


def release_date(text: str) -> str:
    found = re.search(r'\bRelease date:\s*([0-9]{1,2})\s+([A-Z][a-z]+)\s+(20[0-9]{2})\b', text)
    if not found or found.group(2) not in MONTHS:
        raise ValueError('official ONS release date not found')
    return date(int(found.group(3)), MONTHS.index(found.group(2)) + 1, int(found.group(1))).isoformat()


def headline(text: str, periods: tuple[str, ...]) -> tuple[float, str]:
    # Scope to the opening release summary.  The rest of an ONS bulletin
    # intentionally contains historical comparisons and must not be searched.
    start = text.find('Main points')
    if start < 0:
        start = text.find('Other pages in this release')
    if start < 0:
        raise ValueError('ONS opening summary marker not found')
    section = text[start:start + 6000]
    source_periods = [p for p in periods if p in section]
    # July 2020 repeats the period in the overview without the rate.  Select
    # its named Unemployment section only when its dedicated all-people first-
    # release sentence exists, rather than widening the overview scan.
    marker = 'Unemployment Unemployment measures'
    us = text.find(marker, start)
    ue = text.find('Economic inactivity', us + len(marker)) if us >= 0 else -1
    if us >= 0 and ue > us:
        unemployment_section = text[us:ue]
        if any(re.search(rf'\bFor\s+{re.escape(p)}:\s+the estimated UK unemployment rate for all people was\s*[0-9]', unemployment_section, re.I) for p in periods):
            section = unemployment_section
            source_periods = [p for p in periods if p in section]
    if len(source_periods) != 1:
        raise ValueError(f'expected one mapped rolling-period wording in ONS opening summary: {periods}; found={source_periods}')
    source_period = source_periods[0]
    escaped = re.escape(source_period)
    end_month = re.escape(source_period.rsplit(' to ', 1)[1])
    patterns = (
        # 2018-era bulletins state the exact period in the Main-points heading
        # and then put the rate in a definition-bearing bullet immediately
        # beneath it.  This route remains tied to that verified heading.
        rf'\bMain points for\s+{escaped}\b.{{0,1400}}?\bunemployment rate\s*\([^)]{{0,240}}\)\s*was\s*([0-9]+(?:\.[0-9]+)?)\s*%',
        # July 2020's named Unemployment section has an explicit all-people
        # first-release sentence for the exact rolling window.
        rf'\bFor\s+{escaped}:\s+the estimated UK unemployment rate for all people was\s*([0-9]+(?:\.[0-9]+)?)\s*%',
        # December 2018 keeps the same first-release main-points structure but
        # adds "estimated at" after the exact unemployment definition.
        rf'\bMain points for\s+{escaped}\b.{{0,1400}}?\bunemployment rate\s*\([^)]{{0,240}}\)\s*was estimated at\s*([0-9]+(?:\.[0-9]+)?)\s*%',
        # 2020-era overview wording identifies the rolling window by its final
        # month; the complete three-month window above must still be present.
        rf'\b(?:UK )?unemployment rate for the three months to\s+{end_month}\b[^.]{{0,180}}?\b(?:was estimated at|was|at)\s*([0-9]+(?:\.[0-9]+)?)\s*%',
        # November 2020 uses "in the three months to" in the opening summary.
        rf'\bUK unemployment rate in the three months to\s+{end_month}\b[^.]{{0,180}}?\bwas estimated at\s*([0-9]+(?:\.[0-9]+)?)\s*%',
        # The May 2021 companion bulletin puts the period and the UK headline
        # in separate bullets inside the same explicitly bounded Main points.
        r'\bUK unemployment rate was estimated at\s*([0-9]+(?:\.[0-9]+)?)\s*%',
        # May 2023-style summaries put a decimal quarterly change between the
        # exact window and the level, so this is deliberately a separate route.
        rf'\bunemployment rate for\s+{escaped}\b\s+(?:increased|decreased) by\s+[0-9]+(?:\.[0-9]+)?\s+percentage points[^.]{{0,100}}?\bto\s+([0-9]+(?:\.[0-9]+)?)\s*%',
        # August 2026 places the rate before, rather than after, the period.
        rf'\b(?:UK )?unemployment rate(?: for people aged 16 years and over)?\s+was estimated at\s+([0-9]+(?:\.[0-9]+)?)\s*%\s+in\s+{escaped}\b',
        rf'\b(?:UK )?unemployment rate(?: for (?:people|all people)(?: aged 16(?: years)? and over)?)?\s+(?:for|in)\s+{escaped}\b[^.]{{0,220}}?\b(?:was|at|to)\s*([0-9]+(?:\.[0-9]+)?)\s*%',
        rf'\b(?:UK )?unemployment rate(?: for (?:people|all people)(?: aged 16(?: years)? and over)?)?\b[^.]{{0,140}}?\b{escaped}\b[^.]{{0,180}}?\b(?:was|at|to)\s*([0-9]+(?:\.[0-9]+)?)\s*%',
        rf'\b{escaped}\b[^.]{{0,150}}?\b(?:UK )?unemployment rate(?: for (?:people|all people))?\b[^.]{{0,120}}?\b(?:was|at|to)\s*([0-9]+(?:\.[0-9]+)?)\s*%',
    )
    # Each route has the headline value as its final capture.  This avoids
    # coupling extraction to optional descriptive captures in a route.
    values = [float(m.groups()[-1]) for pat in patterns for m in re.finditer(pat, section, flags=re.I)]
    values = list(dict.fromkeys(values))
    if len(values) != 1:
        raise ValueError(f'ambiguous or missing exact ONS unemployment headline for {source_period}: {values}')
    return values[0], source_period


def digest(rows, keys: tuple[str, ...]) -> str:
    payload = [{key: row[key] for key in keys} for row in rows]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def parse_release(raw: bytes, final_url: str, title_pattern: str, y: int, m: int, route: str) -> dict[str, object]:
    text = plain(raw)
    if not re.search(rf'\b{title_pattern}:\s*{MONTHS[add_months(y, m, 2)[1]-1]}\s+{add_months(y, m, 2)[0]}\b', text, re.I):
        raise ValueError(f'ONS page identity mismatch for {title_pattern}')
    period = rolling_period(y, m)
    value, source_period = headline(text, page_period_variants(y, m))
    return {'reference_month': f'{y:04d}-{m:02d}', 'rolling_period': period, 'source_rolling_period': source_period,
            'headline_unemployment_rate_pct': value, 'release_date': release_date(text), 'source_route': route,
            'source_url': final_url, 'page_sha256': hashlib.sha256(raw).hexdigest(), 'pit_status': 'STRICT_FIRST_RELEASE'}


def parse_october_2023_experimental_release(raw: bytes, final_url: str) -> dict[str, object]:
    """Read the single ONS release whose LFS headline was withheld.

    The 24 October 2023 overview explicitly says unadjusted June--August LFS
    data were not published, then supplies the same-release experimental
    unemployment estimate.  This is deliberately a one-release route: it is
    not a relaxed headline parser or a fallback to any revised series.
    """
    text = plain(raw)
    if not re.search(r'\bLabour market overview, UK:\s*October\s+2023\b', text, re.I):
        raise ValueError('ONS October 2023 experimental overview identity mismatch')
    if release_date(text) != '2023-10-24':
        raise ValueError('ONS October 2023 experimental overview release-date mismatch')
    opening = text[text.find('Main points'):text.find('Latest indicators at a glance')]
    if 'Unadjusted June to August LFS data are not published.' not in opening:
        raise ValueError('ONS October 2023 LFS-withheld disclosure not found')
    matches = re.findall(
        r'\bExperimental estimates for June to August 2023 show a\s+[0-9]+(?:\.[0-9]+)?\s+'
        r'percentage point (?:increase|decrease) in the UK unemployment rate to\s+'
        r'([0-9]+(?:\.[0-9]+)?)\s*%',
        opening,
        flags=re.I,
    )
    values = list(dict.fromkeys(float(value) for value in matches))
    if len(values) != 1:
        raise ValueError(f'ambiguous or missing fixed ONS October 2023 experimental unemployment headline: {values}')
    return {
        'reference_month': '2023-08', 'rolling_period': 'June to August 2023',
        'source_rolling_period': 'June to August 2023', 'headline_unemployment_rate_pct': values[0],
        'release_date': '2023-10-24', 'source_route': 'ONS_UK_LABOUR_MARKET_EXPERIMENTAL_OVERVIEW_BULLETIN',
        'source_url': final_url, 'page_sha256': hashlib.sha256(raw).hexdigest(), 'pit_status': 'STRICT_FIRST_RELEASE',
    }


def one(y: int, m: int) -> dict[str, object]:
    # The bulletin name is the publication month, not the reference month.
    ry, rm = add_months(y, m, 2)
    slug = f'{MONTHS[rm - 1].lower()}{ry}'
    raw, final_url = fetch(f'{BASE}/{slug}')
    if (y, m) == (2023, 8):
        return parse_october_2023_experimental_release(raw, final_url)
    try:
        return parse_release(raw, final_url, r'(?:UK labour market|Labour market overview, UK)', y, m, 'ONS_UK_LABOUR_MARKET_BULLETIN')
    except ValueError as overview_error:
        # The 2021 split-release layout delegates the exact labour headline to
        # the immutable, same-day official Employment in the UK bulletin.
        companion_raw, companion_url = fetch(f'{EMPLOYMENT_BASE}/{slug}')
        row = parse_release(companion_raw, companion_url, 'Employment in the UK', y, m, 'ONS_EMPLOYMENT_IN_UK_COMPANION_BULLETIN')
        overview_date = release_date(plain(raw))
        if row['release_date'] != overview_date:
            raise ValueError(f'ONS companion release-date mismatch ({overview_error!r}): {row["release_date"]}!={overview_date}')
        return row


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
        # ONS begins returning 429s under a rapid archival scan.  This is a
        # transport throttle, not a fallback to another source or vintage.
        time.sleep(1.25)
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
        'route_counts': {route: sum(row['source_route'] == route for row in rows) for route in sorted({row['source_route'] for row in rows})},
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
