#!/usr/bin/env python3
"""Read-only weekly source audit for USD/EUR/CHF secondary quotes and NZD ASX Bank Bills.

Never interprets secondary futures or bank-bill rates as official OIS or policy
probabilities. Same contract, same expiry, exact source dates; missing stays null.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
from pathlib import Path

from collect_nzd_asx_directional_proxy_v1 import (
    _fetch, _parse_bb_rows, _report_url, _select_horizons,
)
from ois_same_contract_history_v1 import HISTORY, load_history

TENORS = ("3m", "6m", "12m")
CURRENCIES = ("USD", "EUR", "CHF")
SOURCE_NAME = "TradingView archived, exchange-labelled dated futures daily bars"


def confirmed_fridays(start: str | None, end: str | None) -> tuple[dt.date, dt.date]:
    if bool(start) != bool(end):
        raise ValueError("Provide both first and second Fridays, or neither")
    today = dt.datetime.now(dt.timezone.utc).date()
    if start:
        a, b = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    else:
        b = today - dt.timedelta(days=(today.weekday() - 4) % 7)
        if b >= today:
            b -= dt.timedelta(days=7)
        a = b - dt.timedelta(days=7)
    if a.weekday() != 4 or b.weekday() != 4 or (b - a).days != 7 or b >= today:
        raise ValueError(f"Two consecutive completed Fridays required: {a} {b}")
    return a, b


def checked_secondary_pair(rows: list[dict], first: str, second: str) -> dict:
    result = {}
    for currency in CURRENCIES:
        records = [x for x in rows if x["currency"] == currency]
        later = [x for x in records if x["observation_date"] == second]
        earlier = {(x["symbol"], x["expiration"]): x for x in records
                   if x["observation_date"] == first}
        tenors: dict = {}
        for tenor in TENORS:
            choices = [x for x in later if x["observed_under_horizon"] == tenor]
            if len(choices) != 1:
                tenors[tenor] = {
                    "status": "UNAVAILABLE", "reason": "No unique later-date contract for tenor",
                    "change_bp": None,
                }
                continue
            current = choices[0]
            past = earlier.get((current["symbol"], current["expiration"]))
            if past is None:
                tenors[tenor] = {
                    "status": "UNAVAILABLE", "reason": "No first-date observation of identical listed contract",
                    "contract": current["symbol"], "change_bp": None,
                }
                continue
            assert current["official_ois_quote"] is False
            assert past["official_ois_quote"] is False
            assert current["source_method"] == past["source_method"]
            assert current["expiration"] == past["expiration"]
            assert current["contract"] == past["contract"]
            delta = round((current["implied_rate"] - past["implied_rate"]) * 100, 4)
            tenors[tenor] = {
                "status": "SECONDARY_SAME_CONTRACT_OBSERVED",
                "instrument": "Exchange-labelled overnight-rate futures (secondary source)",
                "source": SOURCE_NAME,
                "contract": current["symbol"],
                "contract_expiry": current["expiration"],
                "first_rate_pct": past["implied_rate"],
                "second_rate_pct": current["implied_rate"],
                "first_source_date": first, "second_source_date": second,
                "change_bp": delta, "official_ois": False,
                "policy_rate_repricing_certified": False,
            }
        result[currency] = {
            "classification": "SECONDARY_INDICATIVE_NOT_OIS",
            "horizons": tenors,
            "policy_pricing_eligible": False,
        }
    return result


def exact_asx_bank_bill_rows(day: dt.date) -> tuple[str, list[dict]]:
    url = _report_url(day)
    page = _fetch(url)
    cleaned = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page)))
    match = re.search(r"close\s+of\s+trade\s+date\s*[:\-]?\s*(\d{2}/\d{2}/\d{2,4})",
                      cleaned, re.IGNORECASE)
    if not match:
        raise ValueError(f"ASX report has no verifiable close-of-trade date for {day}")
    raw = match.group(1)
    parsed = dt.datetime.strptime(raw, "%d/%m/%y" if len(raw) == 8 else "%d/%m/%Y").date()
    if parsed != day:
        raise ValueError(f"ASX date mismatch {parsed} != {day}")
    return url, _parse_bb_rows(page)


def nzd_official_bank_bill_proxy(first: dt.date, second: dt.date) -> dict:
    try:
        url_a, earlier_rows = exact_asx_bank_bill_rows(first)
        url_b, later_rows = exact_asx_bank_bill_rows(second)
    except Exception as exc:
        return {
            "classification": "EXCHANGE_SOURCE_UNAVAILABLE",
            "policy_pricing_eligible": False,
            "error": f"{type(exc).__name__}: {str(exc)[:420]}",
            "horizons": {t: {"status": "UNAVAILABLE", "change_bp": None}
                         for t in TENORS},
        }
    selection = _select_horizons(later_rows, second)
    earlier = {(x["expiry_label"], x["expiration"]): x for x in earlier_rows}
    result = {}
    for tenor, point in selection.items():
        key = (point["expiry_label"], dt.date.fromisoformat(point["expiration"]))
        old = earlier.get(key)
        if old is None:
            result[tenor] = {
                "status": "UNAVAILABLE", "reason": "No matching prior bank bill futures contract",
                "contract": point["expiry_label"], "change_bp": None,
            }
            continue
        result[tenor] = {
            "status": "OFFICIAL_EXCHANGE_BANK_BILL_PROXY",
            "instrument": "ASX NZ 90-Day Bank Bill futures (bank credit/basis included)",
            "source": "ASX official EOD trade reports",
            "contract": point["expiry_label"],
            "contract_expiry": key[1].isoformat(),
            "first_rate_pct": old["implied_bank_bill_rate"],
            "second_rate_pct": point["implied_bank_bill_rate"],
            "first_source_date": first.isoformat(),
            "second_source_date": second.isoformat(),
            "change_bp": round(
                (point["implied_bank_bill_rate"] - old["implied_bank_bill_rate"]) * 100, 4),
            "official_ois": False,
            "policy_rate_repricing_certified": False,
        }
    return {
        "classification": "OFFICIAL_EXCHANGE_DIRECTIONAL_PROXY_NOT_OIS",
        "source_urls": [url_a, url_b],
        "policy_pricing_eligible": False,
        "horizons": result,
    }


def build(start: str | None = None, end: str | None = None) -> dict:
    first, second = confirmed_fridays(start, end)
    historical = load_history(HISTORY)
    sources = checked_secondary_pair(historical, first.isoformat(), second.isoformat())
    sources["NZD"] = nzd_official_bank_bill_proxy(first, second)
    valid = sum(
        point.get("change_bp") is not None
        for section in sources.values() for point in section["horizons"].values()
    )
    return {
        "schema": "GMFQ_WEEKLY_FOUR_EXTRA_RESEARCH_AUDIT_V1",
        "dates": [first.isoformat(), second.isoformat()],
        "status": "RESEARCH_ONLY_NO_OFFICIAL_OIS_PROMOTION",
        "validated_observed_contract_changes": valid,
        "currencies": sources,
        "controls": {
            "no_production_changes": True,
            "policy_repricing_certified": False,
            "signals_eligible": False,
            "macro_scores_eligible": False,
            "backtest_eligible_as_official": False,
            "mixed_instruments_comparable_as_policy_curves": False,
            "missing_observations_are_zero": False,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--first")
    parser.add_argument("--second")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build(args.first, args.second)
    raw = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    print(f"FOUR_EXTRA_RESEARCH_AUDIT {report['dates']} observed={report['validated_observed_contract_changes']}")
    for currency, section in report["currencies"].items():
        print(f"{currency} [{section['classification']}]")
        for tenor, point in section["horizons"].items():
            value = point.get("change_bp")
            print(f"  {tenor}: {'UNAVAILABLE' if value is None else f'{value:+.2f} bp'} "
                  f"{point.get('contract', '')} ({point['status']})")
        if section.get("error"):
            print(f"  SOURCE_ERROR: {section['error']}")


if __name__ == "__main__":
    main()
