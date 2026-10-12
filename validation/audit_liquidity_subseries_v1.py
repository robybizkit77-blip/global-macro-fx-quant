#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import re
import statistics
from collections import Counter
from pathlib import Path

PATH = Path('live_data/sections/NATIVE_LIQ_DATA.json')
G8 = ['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']
MIN_SERIES_PER_CURRENCY = {ccy: 3 for ccy in G8}
MIN_SERIES_PER_CURRENCY['EUR'] = 4
MIN_SERIES_PER_CURRENCY['JPY'] = 4
REQUIRED_PATHS = {
    'USD': {'liquidity', 'credit', 'conditions'},
    'EUR': {'liquidity', 'money', 'credit', 'conditions'},
}


def parse_period(value):
    if not isinstance(value, str) or not value.strip():
        return None
    s = value.strip()
    try:
        # Monthly period: 2026-08
        if re.fullmatch(r'\d{4}-\d{2}', s):
            y, m = map(int, s.split('-'))
            return ('month', y * 12 + m)

        # Quarterly period: 2026-Q3
        m = re.fullmatch(r'(\d{4})-Q([1-4])', s)
        if m:
            y, q = int(m.group(1)), int(m.group(2))
            return ('quarter', y * 4 + q)

        # European date: 31/07/2026
        if re.fullmatch(r'\d{2}/\d{2}/\d{4}', s):
            return ('day', dt.datetime.strptime(s, '%d/%m/%Y').date().toordinal())

        # ISO timestamp: 2026-09-21T00:00:00.000Z
        if 'T' in s:
            iso = s.replace('Z', '+00:00')
            return ('day', dt.datetime.fromisoformat(iso).date().toordinal())

        # ISO date: 2026-09-16
        return ('day', dt.date.fromisoformat(s).toordinal())
    except Exception:
        return None


def cadence(dates):
    parsed = [parse_period(x) for x in dates[-12:]]
    parsed = [x for x in parsed if x]
    if len(parsed) < 2 or len({x[0] for x in parsed}) != 1:
        return 'UNKNOWN'
    unit = parsed[0][0]
    diffs = [b[1] - a[1] for a, b in zip(parsed, parsed[1:]) if b[1] > a[1]]
    if not diffs:
        return 'UNKNOWN'
    med = statistics.median(diffs)

    if unit == 'quarter':
        if med <= 1.5:
            return 'QUARTERLY_PERIOD'
        return 'LOW_FREQUENCY_PERIOD'

    if unit == 'month':
        if med <= 1.5:
            return 'MONTHLY_OR_FASTER_PERIOD'
        if med <= 4:
            return 'QUARTERLY_PERIOD'
        return 'LOW_FREQUENCY_PERIOD'

    if med <= 2:
        return 'DAILY_OR_NEAR_DAILY'
    if med <= 10:
        return 'WEEKLY_OR_NEAR_WEEKLY'
    if med <= 40:
        return 'MONTHLY_OR_NEAR_MONTHLY'
    if med <= 120:
        return 'QUARTERLY_OR_NEAR_QUARTERLY'
    return 'LOW_FREQUENCY_OR_IRREGULAR'


def walk(currency, node, path=()):
    out = []
    if isinstance(node, dict):
        dates = node.get('dates')
        if isinstance(dates, list) and dates:
            last = node.get('last_date') or dates[-1]
            out.append({
                'currency': currency,
                'series_path': '.'.join(path) or 'root',
                'label': node.get('label'),
                'last_date': last,
                'observed_cadence_class': cadence(dates),
                'observation_count': len(dates),
            })
        for k, v in node.items():
            if isinstance(v, (dict, list)):
                out.extend(walk(currency, v, path + (str(k),)))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if isinstance(v, (dict, list)):
                out.extend(walk(currency, v, path + (str(i),)))
    return out


def main():
    data = json.loads(PATH.read_text(encoding='utf-8'))
    rows = []
    for ccy, node in sorted(data.items()):
        rows.extend(walk(ccy, node))
    if not rows:
        raise SystemExit('no dated liquidity subseries found')

    currencies = sorted({x['currency'] for x in rows})
    if currencies != sorted(G8):
        raise SystemExit(f'liquidity currency coverage mismatch: {currencies}')

    counts = Counter(x['currency'] for x in rows)
    for ccy, minimum in MIN_SERIES_PER_CURRENCY.items():
        if counts[ccy] < minimum:
            raise SystemExit(f'liquidity structural undercount for {ccy}: {counts[ccy]} < {minimum}')

    paths = {ccy: {x['series_path'].split('.')[0] for x in rows if x['currency'] == ccy} for ccy in G8}
    for ccy, required in REQUIRED_PATHS.items():
        missing = required - paths[ccy]
        if missing:
            raise SystemExit(f'liquidity required component paths missing for {ccy}: {sorted(missing)}')

    unknown = [x for x in rows if x['observed_cadence_class'] == 'UNKNOWN']
    if unknown:
        raise SystemExit('unparsed liquidity cadence/date formats remain: ' + ', '.join(f"{x['currency']}:{x['series_path']}:{x['last_date']}" for x in unknown))

    result = {
        'schema': 'GMFQ_LIQUIDITY_SUBSERIES_INVENTORY_V1',
        'status': 'INVENTORY_COMPLETE_POLICY_NOT_MAPPED',
        'currency_count': len(currencies),
        'subseries_count': len(rows),
        'series_count_by_currency': dict(sorted(counts.items())),
        'unknown_cadence_count': len(unknown),
        'records': rows,
        'policy_note': 'Observed cadence is descriptive only. A subseries cannot become GREEN until its official source cadence and allowed release lag are explicitly mapped.',
        'bias_score_sizing_effect': 'NONE',
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
