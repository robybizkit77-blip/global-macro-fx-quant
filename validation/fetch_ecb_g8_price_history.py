#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import urllib.request
import xml.etree.ElementTree as ET

URL = 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml'
CURRENCIES = ('EUR','USD','GBP','JPY','CHF','CAD','AUD','NZD')
REQUIRED = CURRENCIES[1:]
DEFAULT_RETAIN_DAYS = 800


def fetch(url: str = URL, timeout: int = 45, retain_days: int = DEFAULT_RETAIN_DAYS) -> dict:
    req = urllib.request.Request(url, headers={'User-Agent':'GMFQ/1.0 (+official ECB reference-rates history updater)'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    root = ET.fromstring(raw)

    rows = []
    for node in root.iter():
        as_of = node.attrib.get('time')
        if not as_of:
            continue
        day = dt.date.fromisoformat(as_of)
        vals = {'EUR': 1.0}
        for child in list(node):
            ccy = child.attrib.get('currency')
            rate = child.attrib.get('rate')
            if ccy in REQUIRED and rate is not None:
                vals[ccy] = float(rate)
        missing = [c for c in REQUIRED if c not in vals]
        if missing:
            raise ValueError(f'ECB historical row {as_of} missing required G8 currencies: {missing}')
        if any(vals[c] <= 0 for c in CURRENCIES):
            raise ValueError(f'ECB historical row {as_of} contains non-positive required rate')
        rows.append({'Date': day.isoformat(), **{c: vals[c] for c in CURRENCIES}})

    if not rows:
        raise ValueError('ECB historical XML contains no dated rows')
    rows.sort(key=lambda x: x['Date'])
    if len({r['Date'] for r in rows}) != len(rows):
        raise ValueError('ECB historical XML contains duplicate dates')

    latest = dt.date.fromisoformat(rows[-1]['Date'])
    cutoff = latest - dt.timedelta(days=retain_days)
    rows = [r for r in rows if dt.date.fromisoformat(r['Date']) >= cutoff]
    if len(rows) < 500:
        raise ValueError(f'ECB retained history too short: {len(rows)} rows')

    return {
        'schema': 'GMFQ_ECB_G8_PRICE_HISTORY_V1',
        'source': 'ECB euro foreign exchange reference rates',
        'source_url': URL,
        'base': 'EUR',
        'currencies': list(CURRENCIES),
        'pair_count': 28,
        'retention_calendar_days': retain_days,
        'first_as_of': rows[0]['Date'],
        'last_as_of': rows[-1]['Date'],
        'row_count': len(rows),
        'status': 'CURRENT_OFFICIAL_HISTORY',
        'rows': rows,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out')
    ap.add_argument('--retain-days', type=int, default=DEFAULT_RETAIN_DAYS)
    args = ap.parse_args()
    data = fetch(retain_days=args.retain_days)
    text = json.dumps(data, indent=2, sort_keys=True) + '\n'
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            f.write(text)
    print(json.dumps({
        'schema': data['schema'],
        'status': data['status'],
        'first_as_of': data['first_as_of'],
        'last_as_of': data['last_as_of'],
        'row_count': data['row_count'],
        'out': args.out,
    }, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
