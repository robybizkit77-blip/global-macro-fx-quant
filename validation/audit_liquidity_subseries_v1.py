#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import statistics
from pathlib import Path

PATH = Path('live_data/sections/NATIVE_LIQ_DATA.json')


def parse_period(value):
    if not isinstance(value, str):
        return None
    try:
        if len(value) == 7:
            y, m = map(int, value.split('-'))
            return ('month', y * 12 + m)
        return ('day', dt.date.fromisoformat(value).toordinal())
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
    if currencies != sorted(['USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD']):
        raise SystemExit(f'liquidity currency coverage mismatch: {currencies}')
    unknown = [x for x in rows if x['observed_cadence_class'] == 'UNKNOWN']
    result = {
        'schema': 'GMFQ_LIQUIDITY_SUBSERIES_INVENTORY_V1',
        'status': 'INVENTORY_COMPLETE_POLICY_NOT_MAPPED',
        'currency_count': len(currencies),
        'subseries_count': len(rows),
        'unknown_cadence_count': len(unknown),
        'records': rows,
        'policy_note': 'Observed cadence is descriptive only. A subseries cannot become GREEN until its official source cadence and allowed release lag are explicitly mapped.',
        'bias_score_sizing_effect': 'NONE',
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
