#!/usr/bin/env python3
"""NZD bank-bill research scenarios: stringent ASX source checks + sensitivity.

NOT NZBO/OIS, NOT a policy-rate forecast or a statistical confidence interval.
The monthly RBNZ 90-day spot-bill-minus-OCR basis is NOT an observable futures
bill/OIS basis. In particular a single basis for all expiries is a strong and
untested restriction. Historical Q3 2026 holdout is NOT available for a second
independent validation after using it to select an expanded range or stress.
Read-only diagnostic: runs on current signed ASX daily report and frozen
manually transcribed RBNZ research data. Never publishes official OIS levels.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
ASX = ROOT / "live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json"
CAL = ROOT / "validation/cb_pricing/NZD_BB_CASH_RESEARCH_CALIBRATION_V1_2026-10-21.json"
TENORS = {"3m": 90, "6m": 180, "12m": 365}
SCHEMA = "GMFQ_NZD_ASX_BANKBILL_SCENARIO_SENSITIVITY_V2_RESEARCH"
ASX_SCHEMA = "GMFQ_NZD_CB_PRICING_DIRECTIONAL_PROXY_V1"
CAL_SCHEMA = "GMFQ_NZD_BB_VS_CASH_EMPIRICAL_CALIBRATION_RESEARCH_V1"
SOURCE = "OFFICIAL_EXCHANGE_DIRECTIONAL_PROXY"
TARGET_TOLERANCE_DAYS = 65


def require(condition, message: str):
    if not condition:
        raise ValueError("NZD_SCENARIO_RESEARCH_FAIL_CLOSED: " + message)


def numeric(value):
    return type(value) in (int, float) and abs(value) < 1e7 and value == value


def expiry_for(label: str) -> str:
    require(isinstance(label, str) and re.fullmatch(
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) 20\d\d", label
    ) is not None, "invalid ASX listed expiry label")
    m, y = label.split()
    month = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug",
             "Sep", "Oct", "Nov", "Dec").index(m) + 1
    candidate = date(int(y), month, 10)
    while candidate.weekday() != 2:
        candidate += timedelta(days=1)
    return candidate.isoformat()


def check_asx(feed: dict, asof: date) -> dict:
    require(isinstance(feed, dict) and feed.get("schema") == ASX_SCHEMA
            and feed.get("currency") == "NZD"
            and feed.get("status") == "LIVE_DIRECTIONAL_PROXY_READY",
            "source identity/status")
    quality = feed.get("source_quality")
    require(quality == SOURCE and
            feed.get("source") == "ASX official NZ futures end-of-day total traded report"
            and feed.get("instrument") ==
            "ASX New Zealand 90 Day Bank Accepted Bill Futures (BB)",
            "unverified bank-bill source")
    require(isinstance(feed.get("as_of"), str)
            and re.fullmatch(r"\d{4}-\d\d-\d\d", feed["as_of"]) is not None,
            "missing source date")
    asx_day = date.fromisoformat(feed["as_of"])
    require(asx_day.weekday() < 5 and 0 <= (asof - asx_day).days <= 5,
            "stale/future/weekend source day")
    require(feed.get("source_url") ==
            "https://www.asx.com.au/data/futures/reports/EODWebMarketSummary"
            + asx_day.strftime("%y%m%d") + "ZFT.htm", "ASX report/date mismatch")
    gov = feed.get("governance") or {}
    require(gov.get("informational_only") is True
            and gov.get("substitutes_for_ois_level") is False
            and gov.get("policy_delta_from_proxy_allowed") is False
            and gov.get("backtest_eligible_as_official_ois") is False
            and all(gov.get(k) == "NONE" for k in (
                "core_score_effect", "bias_effect", "sizing_effect",
                "pair_engine_effect")), "proxy promotion to official/model")
    rows = feed.get("horizons")
    require(isinstance(rows, dict) and set(rows) == set(TENORS),
            "3m/6m/12m missing or extra horizon")
    used = set()
    weekly_days = set()
    validated = {}
    for h, days in TENORS.items():
        p = rows[h]
        require(isinstance(p, dict), h + " missing contract details")
        expiration = expiry_for(p.get("expiry_label"))
        require(p.get("expiration") == expiration and expiration not in used,
                h + " wrong/duplicate ASX expiry")
        used.add(expiration)
        expday = date.fromisoformat(expiration)
        require(expday > asx_day and
                abs((expday - asx_day).days - days) <= TARGET_TOLERANCE_DAYS,
                h + " expiration cannot represent target window")
        require(p.get("mapping") ==
                f"nearest listed expiry to trade_date+{days}d; no interpolation",
                h + " invalid contract selection convention")
        price, rate = p.get("settlement_price"), p.get("implied_bank_bill_rate")
        require(numeric(price) and numeric(rate) and
                80 < price < 105 and -5 <= rate <= 25 and
                abs((100 - price) - rate) <= 0.0002,
                h + " bank-bill price/100-rate arithmetic mismatch")
        # Daily settlement change is a SAME CONTRACT secondary monetary-rate
        # observation, not a 1D OIS repricing. Do not silently trust 1D label.
        change, change_bp = p.get("settlement_change"), p.get("change_1d_bp")
        require((change is None and change_bp is None) or
                (numeric(change) and numeric(change_bp) and
                 abs(round(-change * 100, 1) - change_bp) < 0.051),
                h + " source daily settlement change inconsistent")
        weekly_date = p.get("weekly_reference_trade_date")
        weekly_bp = p.get("change_1w_bp")
        if weekly_bp is not None:
            require(numeric(weekly_bp) and isinstance(weekly_date, str)
                    and re.fullmatch(r"\d{4}-\d\d-\d\d", weekly_date)
                    and 4 <= (asx_day - date.fromisoformat(weekly_date)).days <= 12,
                    h + " weekly reference missing/dated outside reasonable window")
            weekly_days.add(weekly_date)
        else:
            require(weekly_date is None, h + " unpaired weekly reference")
        validated[h] = {
            "asx_listed_expiry": p["expiry_label"],
            "expiry_date": expiration,
            "bankbill_implied_pct": rate,
            "verified_source_as_of": feed["as_of"],
            "source_settlement_day_change_bp": change_bp,
            "source_same_contract_week_change_bp": weekly_bp,
            "observation_is_ois": False,
            "policy_repricing_signal": False,
        }
    require(len(weekly_days) <= 1,
            "different weekly report days across NZD contracts")
    if weekly_days:
        week = date.fromisoformat(next(iter(weekly_days)))
        require(feed.get("weekly_reference_source_url") ==
                "https://www.asx.com.au/data/futures/reports/EODWebMarketSummary"
                + week.strftime("%y%m%d") + "ZFT.htm",
                "ASX weekly report does not match same-contract comparison date")
    return validated


def calibration(cal: dict) -> dict:
    require(isinstance(cal, dict) and cal.get("schema") == CAL_SCHEMA,
            "unrecognised historical research calibration")
    require(cal.get("reviewed_as_of") == "2026-10-21"
            and cal.get("source", {}).get("data_type") ==
            "MANUALLY_TRANSCRIBED_OFFICIAL_PUBLIC_TABLE_NOT_SOURCE_BYTES_HASHED",
            "unverified revised historical calibration")
    method = cal.get("method") or {}
    require(method.get("weighted_reference_median") == 0.3
            and method.get("weighted_recent_median") == 0.7
            and method.get("all_contract_horizons_same_basis_assumption") is True
            and method.get("allow_official_ois") is False
            and method.get("allow_bias_core_signals") is False,
            "unstated change to registered source method")
    def row_bases(block, count, start, end):
        rows = block.get("rows") if isinstance(block, dict) else None
        require(isinstance(rows, list) and len(rows) == count and
                block.get("month_count") == count, "wrong number of source observations")
        require(rows[0]["month"] == start and rows[-1]["month"] == end,
                "historical training/test boundary changed")
        bases = []
        months = set()
        for row in rows:
            m, ocr, bill = row.get("month"), row.get("ocr_pct"), row.get("bank_bill_90d_pct")
            require(isinstance(m, str) and re.fullmatch(r"20\d\d-\d\d", m)
                    and m not in months and numeric(ocr) and numeric(bill)
                    and 0 < ocr < 15 and 0 < bill < 15,
                    "invalid/duplicate source month or rate")
            months.add(m)
            bases.append(round((bill - ocr)*100, 2))
        return bases
    old = row_bases(cal.get("reference_plateau"), 13, "2023-06", "2024-06")
    recent = row_bases(cal.get("recent_plateau"), 6, "2026-01", "2026-06")
    holdout = row_bases(cal.get("holdout_2026_q3"), 3, "2026-07", "2026-09")
    require(set(old).issubset(set(old + recent)) and
            len(old + recent) == 19 and len(holdout) == 3,
            "calibration segment mismatch")
    central = round(.3 * median(old) + .7 * median(recent))
    # The old 24bp and 10-50bp are DESIGN-registered, not reoptimised here.
    # The 2026Q3 holdout WAS USED to widen 10-50bp ex post.
    lo = int(min(old + recent) - 2)
    hi = int(max(max(old + recent) + 2, max(holdout) + 2))
    q3_stress = median(holdout)
    errors = [abs(x - central) for x in holdout]
    require(central == 24 and lo == 10 and hi == 50
            and round(sum(errors)/3, 2) == 16.33 and
            q3_stress == 38,
            "frozen 24bp basis / ex-post envelope / Q3 test drift")
    return {
        "central_basis_bp": central,
        "lower_empirical_basis_bp": lo,
        "upper_empirical_basis_bp": hi,
        "stress_recent_q3_basis_bp": q3_stress,
        "stress_shift_from_original_bp": q3_stress - central,
        "historical_training_observations": len(old) + len(recent),
        "historical_holdout_observations": len(holdout),
        "pre_registered_point_test_mae_bp": round(sum(errors)/3, 2),
        "pre_registered_point_test_max_error_bp": max(errors),
        "interval_50bp_selected_after_holdout": True,
        "q3_stress_is_not_out_of_sample": True,
        "source_bytes_cryptographically_certified": False,
        "historical_point_in_time_coverage_certified": False,
        "no_tenor_specific_basis_identified": True,
        "not_a_statistical_forecast_interval": True,
        "not_a_bill_ois_forward_basis": True,
        "not_a_direct_ois_observation": True,
    }


def build(feed: dict, cal: dict, *, asof: date) -> dict:
    verified = check_asx(feed, asof)
    fit = calibration(cal)
    points = {}
    for h, q in verified.items():
        raw = q["bankbill_implied_pct"]
        point = round(raw - fit["central_basis_bp"] / 100, 2)
        stress = round(raw - fit["stress_recent_q3_basis_bp"]/100, 2)
        lower = round(raw - fit["upper_empirical_basis_bp"]/100, 2)
        upper = round(raw - fit["lower_empirical_basis_bp"]/100, 2)
        require(lower <= min(point, stress) <= max(point, stress) <= upper,
                "non-monotonic empirical research stress")
        points[h] = {
            **q,
            "central_non_ois_scenario_pct": point,
            "stress_q3_basis_non_ois_scenario_pct": stress,
            "descriptive_ex_post_lower_pct": lower,
            "descriptive_ex_post_upper_pct": upper,
            "point_vs_stress_abs_bp": round(abs(point-stress)*100, 2),
            "official_ois_eligible": False,
            "policy_delta_eligible": False,
            "model_fx_effect": "NONE",
        }
    return {
        "schema": SCHEMA, "status": "PASS_SCENARIO_SENSITIVITY_RESEARCH_ONLY",
        "as_of": feed["as_of"], "check_date": asof.isoformat(),
        "source": feed["source"], "method": "BANK_BILL_MINUS_FROZEN_RBNZ_CASH_BASIS",
        "calibration": fit, "horizons": points,
        "source_evidence_grade": "ASX_OFFICIAL_EXCHANGE_FUTURES_NOT_OIS",
        "scenario_not_market_quote": True,
        "policy_or_fx_signal_allowed": False,
        "historical_point_in_time_model_certified": False,
        "out_of_sample_interval_coverage_certified": False,
        "official_ois_runtime_mutated": False,
        "live_runtime_mutated": False,
        "risk_note": (
            "Cash bank bill minus month-end OCR is not futures bill/OIS basis. "
            "Same 24bp central basis is assumed for 3M/6M/12M; the Q3 38bp "
            "stress is ex-post and not independently validated. The 10-50bp "
            "envelope was expanded after Q3 and is not a statistical interval."
        ),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, default=ASX)
    p.add_argument("--calibration", type=Path, default=CAL)
    p.add_argument("--asof", type=date.fromisoformat,
                   default=datetime.now(timezone.utc).date())
    p.add_argument("--output", type=Path,
                   default=Path("/tmp/nzd-bankbill-scenario-sensitivity-v2.json"))
    args = p.parse_args()
    require(args.output.resolve().is_relative_to(Path("/tmp")),
            "research proof must remain in /tmp")
    result = build(json.loads(args.source.read_text(encoding="utf-8")),
                   json.loads(args.calibration.read_text(encoding="utf-8")),
                   asof=args.asof)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "status":result["status"],"as_of":result["as_of"],
        "central_basis_bp":result["calibration"]["central_basis_bp"],
        "q3_stress_bp":result["calibration"]["stress_recent_q3_basis_bp"],
        "horizons": {h:p["central_non_ois_scenario_pct"]
                    for h,p in result["horizons"].items()},
        "promoted_to_ois":False, "output":str(args.output)
    }, sort_keys=True))


if __name__ == "__main__":
    main()
