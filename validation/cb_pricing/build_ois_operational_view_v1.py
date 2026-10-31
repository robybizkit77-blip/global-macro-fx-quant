#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ois_estimated_snapshot_v1 import HORIZONS, load_history, fingerprint, method_id

ROOT = Path(__file__).resolve().parents[2]
OIS = ROOT / 'live_data/sections/OIS_DATA.json'
EST = ROOT / 'live_data/sections/CB_PRICING_ESTIMATED.json'
OUT = ROOT / 'live_data/sections/OIS_OPERATIONAL_VIEW.json'
HISTORY = ROOT / 'validation/cb_pricing/history/OIS_ESTIMATED_SNAPSHOTS_V1.jsonl'
LIVE_QUOTES = ROOT / 'live_data/sections/CB_PRICING_ESTIMATED_LIVE_QUOTES.json'
CCYS = ('USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD')
DAILY_REFERENCE_MIN_AGE = timedelta(hours=18)
WEEKLY_REFERENCE_MIN_AGE = timedelta(days=5)


def _parse_capture(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
    except ValueError:
        return None


def _bp_delta(current, reference):
    if current is None or reference is None:
        return None
    return round((float(current) - float(reference)) * 100.0, 1)


def _empty_repricing():
    return {
        'previous_reference': None,
        'weekly_reference': None,
        'change_1d_available': False,
        'change_1w_available': False,
        'horizon_changes': {h: {'change_1d_bp': None, 'change_1w_bp': None} for h in HORIZONS},
    }


def _secondary_verified_quotes(ccy: str, live: dict, today):
    """Observation-level research context only; never an OIS/path/pricing signal.

    Non-synchronized contracts are displayed individually, never aggregated.
    Real daily-bar timestamps are required per observed contract.
    """
    raw = ((live.get('currencies') or {}).get(ccy) or {})
    if raw.get('status') != 'LIVE_SECONDARY_READY':
        return None
    tenors = {}
    for h in HORIZONS:
        q = (raw.get('horizons') or {}).get(h) or {}
        day = q.get('quote_as_of')
        contract = str(q.get('contract') or '')
        symbol = str(q.get('symbol') or '')
        try:
            quote_day = datetime.fromisoformat(day).date()
            rate = float(q['rate'])
            if not (-5.0 <= rate <= 25.0):
                continue
        except (ValueError, TypeError, KeyError):
            continue
        if not (0 <= (today - quote_day).days <= 5):
            continue
        if (q.get('quote_timestamp_verified') is not True
                or q.get('quote_timestamp_source') != 'SSR_DAILY_BAR_DATA_UPDATE_TIME'
                or not contract or '!' in contract or '!' in symbol):
            continue
        tenors[h] = {
            'contract': contract,
            'quote_as_of': quote_day.isoformat(),
            'rate_indicative': rate,
            'source_quality': 'SECONDARY_VERIFIED_DAILY_BAR',
        }
    if not tenors:
        return None
    days = {v['quote_as_of'] for v in tenors.values()}
    return {
        'status': 'INDICATIVE_OBSERVATIONS_NON_OIS',
        'source': raw.get('source'),
        'method_id': 'TRADINGVIEW_DATED_FUTURES_SSR_V2',
        'full_curve_usable': False,
        'cross_date_join_allowed': False,
        'policy_delta_allowed': False,
        'repricing_signal_allowed': False,
        'backtest_eligible_as_official': False,
        'date_mismatch': len(days) > 1,
        'horizons': tenors,
    }


def _estimated_repricing(ccy: str, row: dict, history: list[dict]):
    current_method = method_id(row)
    rows = [
        x for x in history
        if x.get('currency') == ccy and method_id(x) == current_method
    ]
    rows.sort(key=lambda x: _parse_capture(x.get('captured_at_utc')) or datetime.min.replace(tzinfo=timezone.utc))
    current_fp = fingerprint(ccy, row)
    current_rec = None
    for rec in reversed(rows):
        rec_fp = rec.get('fingerprint')
        if rec_fp is None:
            rec_fp = fingerprint(ccy, {
                'method_id': method_id(rec),
                'as_of': rec.get('source_as_of'),
                'source': rec.get('source'),
                'confidence': rec.get('confidence'),
                'horizons': rec.get('horizons') or {},
            })
        if rec_fp == current_fp:
            current_rec = rec
            break
    if current_rec is None:
        return _empty_repricing()
    current_dt = _parse_capture(current_rec.get('captured_at_utc'))
    prior = [x for x in rows if _parse_capture(x.get('captured_at_utc')) and _parse_capture(x.get('captured_at_utc')) < current_dt]
    daily_candidates = [
        x for x in prior
        if _parse_capture(x.get('captured_at_utc')) <= current_dt - DAILY_REFERENCE_MIN_AGE
    ]
    previous = daily_candidates[-1] if daily_candidates else None
    weekly_candidates = [
        x for x in prior
        if _parse_capture(x.get('captured_at_utc')) <= current_dt - WEEKLY_REFERENCE_MIN_AGE
    ]
    weekly = weekly_candidates[-1] if weekly_candidates else None
    changes = {}
    for h in HORIZONS:
        cur = ((row.get('horizons') or {}).get(h) or {}).get('rate')
        prev_rate = None if previous is None else ((previous.get('horizons') or {}).get(h) or {}).get('rate')
        week_rate = None if weekly is None else ((weekly.get('horizons') or {}).get(h) or {}).get('rate')
        changes[h] = {
            'change_1d_bp': _bp_delta(cur, prev_rate),
            'change_1w_bp': _bp_delta(cur, week_rate),
        }
    return {
        'previous_reference': None if previous is None else previous.get('captured_at_utc'),
        'weekly_reference': None if weekly is None else weekly.get('captured_at_utc'),
        'change_1d_available': previous is not None and any(v['change_1d_bp'] is not None for v in changes.values()),
        'change_1w_available': weekly is not None and any(v['change_1w_bp'] is not None for v in changes.values()),
        'horizon_changes': changes,
    }


def build():
    official = json.loads(OIS.read_text(encoding='utf-8'))['currencies']
    estimated = json.loads(EST.read_text(encoding='utf-8'))['currencies']
    history = load_history(HISTORY)
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
            usable = any(((e.get('horizons') or {}).get(h) or {}).get('rate') is not None for h in HORIZONS)
            if not usable:
                out['currencies'][ccy] = {
                    'operational_status': 'WITHHELD',
                    'withheld_reason': (
                        'SECONDARY_QUOTE_CONFLICT_QUARANTINED'
                        if e.get('input_mode') == 'QUARANTINED_SECONDARY_NO_FALLBACK'
                        else 'NO_USABLE_OFFICIAL_OR_ESTIMATED_PRICING'
                    ),
                    'quality': 'UNAVAILABLE',
                    'confidence': 'C',
                    'official_status': o.get('status', 'WITHHELD'),
                    'input_mode': e.get('input_mode'),
                    'method_id': e.get('method_id'),
                    'as_of': e.get('as_of'),
                    'policy_rate': e.get('policy_rate'),
                    'source': e.get('source'),
                    'horizons': {h: {'rate': None, 'policy_delta_bp': None,
                                     'change_1d_bp': None, 'change_1w_bp': None}
                                 for h in HORIZONS},
                    'direction_vs_policy': None,
                    'market_direction_proxy': e.get('market_direction_proxy'),
                    'change_1d_available': False,
                    'change_1w_available': False,
                    'backtest_eligible_as_official': False
                }
                continue
            # Conflicting daily-bar prints may remain useful indicative levels,
            # but must never become computed day/week repricing evidence.
            conflict = e.get('source_conflict_status') == (
                'UNRESOLVED_SECONDARY_SOURCE_SAME_DAY_CONFLICT')
            repricing = _empty_repricing() if conflict else _estimated_repricing(ccy, e, history)
            horizons = {}
            for h in HORIZONS:
                base = dict(((e.get('horizons') or {}).get(h) or {}))
                base.update(repricing['horizon_changes'][h])
                horizons[h] = base
            out['currencies'][ccy] = {
                'operational_status': 'GREEN_ESTIMATED',
                'quality': 'ESTIMATED_INFORMATIONAL',
                'confidence': e.get('confidence_grade'),
                'official_status': o.get('status'),
                'input_mode': e.get('input_mode'),
                'method_id': e.get('method_id'),
                'as_of': e.get('as_of'),
                'policy_rate': e.get('policy_rate'),
                'source': e.get('source'),
                'horizons': horizons,
                'direction_vs_policy': e.get('direction_vs_policy'),
                'market_direction_proxy': e.get('market_direction_proxy'),
                'change_1d_available': repricing['change_1d_available'],
                'change_1w_available': repricing['change_1w_available'],
                'conflicted_source_eligible_for_repricing': False if conflict else None,
                'repricing_reference': {
                    'method_id': method_id(e),
                    'previous_observation_captured_at_utc': repricing['previous_reference'],
                    'weekly_reference_captured_at_utc': repricing['weekly_reference'],
                    'daily_min_age_hours': int(DAILY_REFERENCE_MIN_AGE.total_seconds() / 3600),
                    'weekly_min_age_days': WEEKLY_REFERENCE_MIN_AGE.days,
                    'missing_reference_policy': 'NULL_NOT_ZERO',
                    'homogeneous_method_required': True,
                },
                'backtest_eligible_as_official': False
            }
    # Read optional secondary source only for provenance of individual non-OIS quotes.
    try:
        live_quotes = json.loads(LIVE_QUOTES.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        live_quotes = {}

    # Downgrade stale or incomplete operational rows rather than aborting G8 refresh.
    sys.path.insert(0, str(ROOT / 'validation'))
    from validate_ois_operational_freshness import check
    from datetime import date
    for issue in check(out, datetime.now(timezone.utc).date()):
        row=out['currencies'][issue['currency']]
        row['operational_status']='WITHHELD'
        row['withheld_reason']='STALE_OR_INCOMPLETE_PRICING'
        row['direction_vs_policy']=None
        row['change_1d_available']=False
        row['change_1w_available']=False
        for horizon in row.get('horizons',{}).values():
            horizon['rate']=None
            horizon['policy_delta_bp']=None
            horizon['change_1d_bp']=None
            horizon['change_1w_bp']=None
    for ccy in ('USD', 'EUR', 'CHF'):
        row = out['currencies'][ccy]
        if row['operational_status'] == 'WITHHELD':
            context = _secondary_verified_quotes(ccy, live_quotes, datetime.now(timezone.utc).date())
            if context:
                row['secondary_quote_context'] = context

    out['status']='PARTIAL_WITHHELD' if any(v['operational_status']=='WITHHELD' for v in out['currencies'].values()) else 'GREEN_8_OF_8'
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
    from validate_ois_operational_freshness import check
    assert not check(out, datetime.now(timezone.utc).date()), 'withheld downgrade failed'
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(out['summary'], sort_keys=True))


if __name__ == '__main__':
    main()
