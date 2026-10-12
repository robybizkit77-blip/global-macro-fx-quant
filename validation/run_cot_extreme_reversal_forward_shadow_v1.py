#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import math
import pathlib
import statistics
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date, datetime

import build_cot_ultraconservative_pit_calendar_v1 as pit
import discover_cot_conservative_availability_calendar_v1 as cotbase
from validate_cot_flow_fx_price_readiness_v1 import fetch_one

CONTRACT_PATH = pathlib.Path('validation/COT_EXTREME_REVERSAL_FORWARD_SHADOW_V1_2026-10-12.json')
PRICE_CONTRACT_PATH = pathlib.Path('validation/COT_FLOW_FX_PRICE_SOURCE_CONTRACT_V1_2026-10-11.json')
OUTDIR = pathlib.Path('/tmp/cot-extreme-reversal-forward-shadow')
IDX_REPORT_DATE = 2
IDX_CFTC_CODE = 3
IDX_OPEN_INTEREST = 7
IDX_NC_LONG = 8
IDX_NC_SHORT = 9


def fnum(s: str) -> float:
    return float(s.strip().strip('"').replace(',', ''))


def load_cot_positions(currencies: list[str]) -> dict[str, list[dict]]:
    wanted = {cotbase.CODES[c]: c for c in currencies}
    out = {c: [] for c in currencies}
    for year in cotbase.YEARS:
        req = urllib.request.Request(
            cotbase.BASE.format(year=year),
            headers={'User-Agent': cotbase.UA, 'Accept': 'application/zip,*/*;q=0.8'},
        )
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read()
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            members = [n for n in z.namelist() if not n.endswith('/')]
            if len(members) != 1:
                raise RuntimeError(f'{year}: unexpected ZIP members {members}')
            text = z.read(members[0]).decode('latin-1')
        seen = set()
        for row in csv.reader(io.StringIO(text)):
            if len(row) <= IDX_NC_SHORT:
                continue
            code = row[IDX_CFTC_CODE].strip().strip('"')
            if code not in wanted:
                continue
            ccy = wanted[code]
            report = datetime.strptime(row[IDX_REPORT_DATE].strip().strip('"'), '%Y-%m-%d').date()
            oi = fnum(row[IDX_OPEN_INTEREST])
            nc_long = fnum(row[IDX_NC_LONG])
            nc_short = fnum(row[IDX_NC_SHORT])
            if not (oi > 0 and nc_long >= 0 and nc_short >= 0):
                raise RuntimeError(f'{ccy} {report}: invalid CFTC fields')
            key = (ccy, report)
            if key in seen:
                raise RuntimeError(f'{year}: duplicate {key}')
            seen.add(key)
            out[ccy].append({'report_date': report, 'net_oi': (nc_long - nc_short) / oi})
    for ccy, rows in out.items():
        rows.sort(key=lambda x: x['report_date'])
        if len(rows) < 400:
            raise RuntimeError(f'{ccy}: insufficient COT rows')
    sets = [{r['report_date'] for r in out[c]} for c in currencies]
    if any(s != sets[0] for s in sets[1:]):
        raise RuntimeError('COT currency date sets differ')
    return out


def build_pit_map(report_dates: list[date]) -> dict[date, dict]:
    rows = [pit.transform(cotbase.candidate_row(d.isoformat())) for d in report_dates]
    withheld = [r for r in rows if not r['research_pit_eligible']]
    expected_withheld = {
        '2018-12-24', '2018-12-31', '2019-01-08', '2019-01-15', '2019-01-22',
        '2019-01-29', '2019-02-05', '2019-02-12', '2019-02-19', '2019-02-26',
    }
    if {r['report_date'] for r in withheld} != expected_withheld:
        raise RuntimeError('unexpected PIT-withheld report-date set')
    return {date.fromisoformat(r['report_date']): r for r in rows}


def load_fx_prices(price_contract: dict) -> tuple[dict[str, list[tuple[date, float]]], dict]:
    gate = price_contract['readiness_gate']
    prices = {}
    diagnostics = {}
    latest = []
    for ccy, spec in price_contract['series'].items():
        got, url, rows = fetch_one((ccy, spec))
        if got != ccy:
            raise RuntimeError('FX source mismatch')
        if not rows:
            raise RuntimeError(f'{ccy}: empty H.10 source')
        transformed = []
        for d, v in rows:
            p = v if spec['transform_to_local_currency_vs_usd'] == 'identity' else 1.0 / v
            if not (math.isfinite(p) and p > 0):
                raise RuntimeError(f'{ccy}: invalid transformed H.10 price')
            transformed.append((d, p))
        if transformed[0][0] > date.fromisoformat(gate['each_series_first_nonmissing_on_or_before']):
            raise RuntimeError(f'{ccy}: H.10 starts too late')
        if len(transformed) < gate['each_series_minimum_nonmissing_observations_2018_onward']:
            raise RuntimeError(f'{ccy}: insufficient H.10 observations')
        prices[ccy] = transformed
        latest.append(transformed[-1][0])
        diagnostics[ccy] = {
            'board_history_url': url,
            'transform': spec['transform_to_local_currency_vs_usd'],
            'nonmissing_count': len(transformed),
            'first_nonmissing': transformed[0][0].isoformat(),
            'latest_nonmissing': transformed[-1][0].isoformat(),
        }
    common_latest = min(latest)
    if common_latest < date.fromisoformat(gate['minimum_latest_common_nonmissing_date']):
        raise RuntimeError('H.10 common latest date below frozen readiness minimum')
    return prices, {'common_latest_nonmissing_date': common_latest.isoformat(), 'series': diagnostics}


def first_index_on_or_after(rows: list[tuple[date, float]], target: date):
    lo, hi = 0, len(rows)
    while lo < hi:
        mid = (lo + hi) // 2
        if rows[mid][0] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo if lo < len(rows) else None


def percentile_midrank(window: list[float], x: float) -> float:
    less = sum(v < x for v in window)
    equal = sum(v == x for v in window)
    return 100.0 * (less + 0.5 * equal) / len(window)


def sample_sharpe(xs: list[float]):
    if len(xs) < 2:
        return None
    sd = statistics.stdev(xs)
    return None if sd == 0 else statistics.mean(xs) / sd * math.sqrt(52)


def max_drawdown(log_returns: list[float]):
    wealth = peak = 1.0
    mdd = 0.0
    for r in log_returns:
        wealth *= math.exp(r)
        peak = max(peak, wealth)
        mdd = min(mdd, wealth / peak - 1.0)
    return mdd


def forward_metrics(matured: list[dict], currencies: list[str]) -> dict:
    weekly = defaultdict(list)
    for r in matured:
        iso = r['entry_date'].isocalendar()
        weekly[(iso.year, iso.week)].append(r['observation_return'])
    weekly_series = [sum(weekly[k]) / len(weekly[k]) for k in sorted(weekly)]
    by_ccy = {c: [r for r in matured if r['currency'] == c] for c in currencies}
    represented = [c for c, rows in by_ccy.items() if rows]
    means = {c: (statistics.mean([r['observation_return'] for r in rows]) if rows else None) for c, rows in by_ccy.items()}
    shares = {c: (len(rows) / len(matured) if matured else 0.0) for c, rows in by_ccy.items()}
    return {
        'matured_signal_observations': len(matured),
        'weekly_panel_observations': len(weekly_series),
        'currencies_represented': represented,
        'currency_count_represented': len(represented),
        'panel_annualized_sharpe': sample_sharpe(weekly_series),
        'directional_accuracy': (sum(r['observation_return'] > 0 for r in matured) / len(matured) if matured else None),
        'panel_total_log_return': sum(weekly_series),
        'panel_max_drawdown': max_drawdown(weekly_series) if weekly_series else None,
        'currency_mean_return': means,
        'positive_currency_mean_return_count': sum(v is not None and v > 0 for v in means.values()),
        'currency_share': shares,
        'max_single_currency_share': max(shares.values()) if matured else None,
        'extreme_long_side_count': sum(r['percentile'] >= 80 for r in matured),
        'extreme_short_side_count': sum(r['percentile'] <= 20 for r in matured),
    }


def evaluate_gate(metrics: dict, gate: dict) -> dict:
    enough = metrics['matured_signal_observations'] >= gate['minimum_matured_signal_observations']
    checks = {
        'minimum_matured_signal_observations': enough,
        'minimum_currencies_represented': metrics['currency_count_represented'] >= gate['minimum_currencies_represented'],
        'panel_annualized_sharpe': metrics['panel_annualized_sharpe'] is not None and metrics['panel_annualized_sharpe'] >= gate['panel_annualized_sharpe_min'],
        'directional_accuracy': metrics['directional_accuracy'] is not None and metrics['directional_accuracy'] >= gate['directional_accuracy_min'],
        'positive_currency_mean_return_count': metrics['positive_currency_mean_return_count'] >= gate['positive_currency_mean_return_min_count'],
        'max_single_currency_share': metrics['max_single_currency_share'] is not None and metrics['max_single_currency_share'] <= gate['max_single_currency_share'],
        'both_extreme_sides_represented': metrics['extreme_long_side_count'] > 0 and metrics['extreme_short_side_count'] > 0,
    }
    if not enough:
        verdict = 'WAITING_FOR_UNSEEN_OBSERVATIONS'
    else:
        verdict = 'PASS_FORWARD_CONFIRMATION_GATE' if all(checks.values()) else 'FAIL_FORWARD_CONFIRMATION_GATE'
    return {'verdict': verdict, 'checks': checks, 'all_required': True}


def serializable_row(r: dict) -> dict:
    return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in r.items()}


def main() -> int:
    execution_date = date.today()
    contract = json.loads(CONTRACT_PATH.read_text(encoding='utf-8'))
    price_contract = json.loads(PRICE_CONTRACT_PATH.read_text(encoding='utf-8'))
    assert contract['schema'] == 'GMFQ_COT_EXTREME_REVERSAL_FORWARD_SHADOW_V1'
    assert contract['status'] == 'FROZEN_WAITING_FOR_UNSEEN_CONFIRMATION'
    s = contract['frozen_signal']
    assert s['lookback_weeks'] == 104
    assert s['extreme_long_threshold_percentile'] == 80
    assert s['extreme_short_threshold_percentile'] == 20
    assert s['fx_horizon_trading_days'] == 5
    currencies = s['currencies']
    boundary = date.fromisoformat(contract['forward_eligibility']['report_date_must_be_strictly_after'])

    positions = load_cot_positions(currencies)
    all_dates = [r['report_date'] for r in positions[currencies[0]]]
    pit_map = build_pit_map(all_dates)
    prices, fx_receipt = load_fx_prices(price_contract)

    forward_signals = []
    counters = defaultdict(int)
    for ccy in currencies:
        rows = positions[ccy]
        for i in range(103, len(rows)):
            cur = rows[i]
            if cur['report_date'] <= boundary:
                continue
            pcur = pit_map[cur['report_date']]
            if not pcur['research_pit_eligible']:
                counters['current_report_withheld'] += 1
                continue
            available = date.fromisoformat(pcur['research_available_from'])
            if available > execution_date:
                counters['not_yet_research_available'] += 1
                continue
            lookback = rows[i - 103:i + 1]
            if len(lookback) != 104:
                raise RuntimeError('lookback length drift')
            if any(not pit_map[r['report_date']]['research_pit_eligible'] for r in lookback):
                counters['lookback_contains_withheld_report'] += 1
                continue
            pct = percentile_midrank([r['net_oi'] for r in lookback], cur['net_oi'])
            if pct >= 80:
                signal = -1
                side = 'EXTREME_LONG_REVERSAL'
            elif pct <= 20:
                signal = 1
                side = 'EXTREME_SHORT_REVERSAL'
            else:
                counters['non_extreme_no_position'] += 1
                continue

            px = prices[ccy]
            idx = first_index_on_or_after(px, available)
            row = {
                'currency': ccy,
                'report_date': cur['report_date'],
                'research_available_from': available,
                'net_oi': cur['net_oi'],
                'percentile': pct,
                'signal': signal,
                'side': side,
                'entry_date': None,
                'entry_price': None,
                'exit_date': None,
                'exit_price': None,
                'fx_log_return': None,
                'observation_return': None,
                'outcome_status': 'UNMATURED',
            }
            if idx is None:
                row['outcome_status'] = 'WAITING_FOR_ENTRY_FX_PRICE'
                counters['waiting_for_entry_fx_price'] += 1
            else:
                entry_d, entry_p = px[idx]
                row['entry_date'] = entry_d
                row['entry_price'] = entry_p
                if idx + 5 < len(px):
                    exit_d, exit_p = px[idx + 5]
                    raw = math.log(exit_p / entry_p)
                    row.update({
                        'exit_date': exit_d,
                        'exit_price': exit_p,
                        'fx_log_return': raw,
                        'observation_return': signal * raw,
                        'outcome_status': 'MATURED',
                    })
                else:
                    counters['waiting_for_fifth_subsequent_fx_trading_day'] += 1
            forward_signals.append(row)

    forward_signals.sort(key=lambda r: (r['report_date'], r['currency']))
    matured = [r for r in forward_signals if r['outcome_status'] == 'MATURED']
    metrics = forward_metrics(matured, currencies)
    gate_eval = evaluate_gate(metrics, contract['confirmation_gate'])

    report_dates_post_boundary = sorted(d for d in all_dates if d > boundary)
    result = {
        'schema': 'GMFQ_COT_EXTREME_REVERSAL_FORWARD_SHADOW_RESULT_V1',
        'execution_date': execution_date.isoformat(),
        'contract_schema': contract['schema'],
        'historical_boundary_report_date': boundary.isoformat(),
        'latest_cftc_report_date_present': max(all_dates).isoformat(),
        'post_boundary_cftc_report_dates_present': len(report_dates_post_boundary),
        'latest_post_boundary_cftc_report_date_present': report_dates_post_boundary[-1].isoformat() if report_dates_post_boundary else None,
        'fx_source_receipt': fx_receipt,
        'signal_snapshot': {
            'signals_total': len(forward_signals),
            'matured': len(matured),
            'unmatured': len(forward_signals) - len(matured),
            'counters': dict(sorted(counters.items())),
        },
        'forward_metrics': metrics,
        'confirmation_gate': gate_eval,
        'governance': {
            'historical_candidate_reestimated': False,
            'parameter_tuning': False,
            'threshold_changed': False,
            'currency_exclusion': False,
            'horizon_changed': False,
            'partial_results_authorize_production': False,
            'production_signal_authorized': False,
            'sizing_authorized': False,
            'promotion_requires_separate_review_after_gate_pass': True,
            'repository_write_performed': False,
        },
    }

    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / 'result.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    (OUTDIR / 'signal_snapshot.json').write_text(
        json.dumps([serializable_row(r) for r in forward_signals], indent=2, sort_keys=True) + '\n', encoding='utf-8'
    )
    fields = [
        'currency', 'report_date', 'research_available_from', 'net_oi', 'percentile', 'signal', 'side',
        'entry_date', 'entry_price', 'exit_date', 'exit_price', 'fx_log_return', 'observation_return', 'outcome_status',
    ]
    with (OUTDIR / 'signal_snapshot.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in forward_signals:
            w.writerow(serializable_row(r))

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
