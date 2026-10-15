#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OIS = ROOT / 'live_data/sections/OIS_DATA.json'
EST = ROOT / 'live_data/sections/CB_PRICING_ESTIMATED.json'
OUT = ROOT / 'live_data/sections/OIS_OPERATIONAL_VIEW.json'
CCYS = ('USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD')


def build():
    official = json.loads(OIS.read_text(encoding='utf-8'))['currencies']
    estimated = json.loads(EST.read_text(encoding='utf-8'))['currencies']
    out = {
        'schema': 'GMFQ_OIS_OPERATIONAL_VIEW_V1',
        'status': 'GREEN_8_OF_8',
        'official_runtime_untouched': True,
        'currencies': {}
    }
    for ccy in CCYS:
        o = official.get(ccy) or {}
        if o.get('status') == 'ACTIVE':
            out['currencies'][ccy] = {
                'operational_status': 'GREEN_OFFICIAL',
                'quality': 'OFFICIAL_CERTIFIED',
                'confidence': 'A',
                'official_status': 'ACTIVE',
                'as_of': o.get('as_of'),
                'policy_rate': o.get('policy_rate'),
                'source': o.get('source'),
                'horizons': o.get('horizons'),
                'direction_vs_policy': o.get('direction'),
                'change_1d_available': True,
                'change_1w_available': True,
                'backtest_eligible_as_official': True
            }
        else:
            e = estimated.get(ccy) or {}
            usable = any(((e.get('horizons') or {}).get(h) or {}).get('rate') is not None for h in ('3m','6m','12m'))
            if not usable:
                raise SystemExit(f'{ccy}: neither official ACTIVE nor usable estimated pricing')
            out['currencies'][ccy] = {
                'operational_status': 'GREEN_ESTIMATED',
                'quality': 'ESTIMATED_INFORMATIONAL',
                'confidence': e.get('confidence_grade'),
                'official_status': o.get('status'),
                'as_of': e.get('as_of'),
                'policy_rate': e.get('policy_rate'),
                'source': e.get('source'),
                'horizons': e.get('horizons'),
                'direction_vs_policy': e.get('direction_vs_policy'),
                'change_1d_available': e.get('change_1d_bp') is not None,
                'change_1w_available': e.get('change_1w_bp') is not None,
                'backtest_eligible_as_official': False
            }
    out['summary'] = {
        'g8_total': 8,
        'operational_green': sum(v['operational_status'].startswith('GREEN_') for v in out['currencies'].values()),
        'green_official': sum(v['operational_status']=='GREEN_OFFICIAL' for v in out['currencies'].values()),
        'green_estimated': sum(v['operational_status']=='GREEN_ESTIMATED' for v in out['currencies'].values()),
        'operational_withheld': sum(not v['operational_status'].startswith('GREEN_') for v in out['currencies'].values())
    }
    return out


def main():
    out = build()
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(out['summary'], sort_keys=True))

if __name__ == '__main__':
    main()
