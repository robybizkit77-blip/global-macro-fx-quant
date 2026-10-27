#!/usr/bin/env python3
"""Research-only Eurostat membership / Swiss SECO-to-SNB precision safeguards.

The 105 pinned Eurostat first flashes span EA19/EA20/EA21. 24 prior-month
robust z is clean ONLY if all 24 months plus current have same membership.
SECO's 3.1% SA registered unemployment is rounded to one decimal: cannot
certify the exact SNB contemporaneous rate or the API publication instant.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.macro.v2_eur_aud_archival_first_web_overlay_v1 import rows_and_events

SCHEMA = "GMFQ_MACRO_V2_EUR_MEMBERSHIP_CHF_PRECISION_QUALITY_V1"
REGIMES = (
    ("EA19", "2018-01", "2022-12",
     "https://ec.europa.eu/eurostat/documents/2995521/15725194/2-31012023-AP-EN.pdf/d6c60a83-0dc6-04aa-774d-0fefc772ef68"),
    ("EA20", "2023-01", "2025-12",
     "https://www.ecb.europa.eu/press/economic-bulletin/focus/2023/html/ecb.ebbox202208_02~15fd36600a.en.html"),
    ("EA21", "2026-01", "2026-09",
     "https://ec.europa.eu/eurostat/en/web/products-euro-indicators/w/2-25022026-ap"),
)
SWISS_SEPT_2026 = {
    "reported_rounded_sa_unemployment_pct": 3.1,
    "current_SNB_revised_exact_pct": 3.1249882357461,
    "official_release_day": "2026-10-06",
    "sa_unemployed_count_in_september_report": 147411,
    "august_count_as_first_published_in_august_report": 147970,
    "august_count_revised_in_september_report": 147886,
    "official_september": "https://www.konsum.admin.ch/it/newnsb/Cdju9-o8WGML",
    "official_august": "https://www.seco-cooperation.admin.ch/de/newnsb/OfSdV0mM5gUa",
    "snb_api": "https://data.snb.ch/api/cube/amarbma/data/json/en",
}


def require(ok, msg):
    if not ok:
        raise ValueError("MACRO_V2_MEMBERSHIP_PRECISION_REJECTED: " + msg)


def utc(raw):
    d = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    require(d.tzinfo is not None and d.utcoffset() == timedelta(0),
            "UTC offset-aware cutoff required")
    return d


def label(reference_month):
    require(isinstance(reference_month, str) and len(reference_month) == 7,
            "canonical economic month required")
    for name, first, last, _ in REGIMES:
        if first <= reference_month <= last:
            return name
    raise ValueError("MACRO_V2_MEMBERSHIP_PRECISION_REJECTED: outside pinned EA period")


def euro_quality(*, source=None, cutoff="2026-10-27T00:00:00Z"):
    cutoff_utc = utc(cutoff)
    record = source if source is not None else rows_and_events("EUR.inflation")
    events = record["events"]
    require(len(events) == 105 and all(
        e["currency"] == "EUR" and e["pillar"] == "inflation"
        and e["canonical_series_id"] == "EA_HICP_HEADLINE_YOY"
        and e["stage"] == "FIRST_WEB"
        and e["PIT_history_replay_for_trading_authorized"] is False
        for e in events), "full 105 first-flash EUR archive contract")
    rows = []
    for e in events:
        ref = e["reference_period"]
        rows.append({
            "reference_month": ref, "membership": label(ref),
            "first_flash_yoy_pct": e["reported_value"],
            "first_web_gate_utc": e["visible_from_utc"],
            "visible_at_cutoff": utc(e["visible_from_utc"]) <= cutoff_utc,
            "source_url": e["source_url"],
        })
    expected = [
        f"{y:04d}-{m:02d}" for y in range(2018, 2027)
        for m in range(1, 13)
        if "2018-01" <= f"{y:04d}-{m:02d}" <= "2026-09"
    ]
    require([r["reference_month"] for r in rows] == expected,
            "EUR archived flash economic period missing or unordered")
    counts = {name: sum(r["membership"] == name for r in rows)
              for name, _, _, _ in REGIMES}
    require(counts == {"EA19": 60, "EA20": 36, "EA21": 9},
            "Eurostat 3-regime period counts drift")
    windows = []
    for i, row in enumerate(rows):
        prior = rows[max(i-24, 0):i]
        homogeneous = (
            len(prior) == 24 and all(
                p["membership"] == row["membership"] for p in prior))
        require(all(utc(p["first_web_gate_utc"]) <
                    utc(row["first_web_gate_utc"]) for p in prior),
                "future first flash leaked into prior training")
        z = None
        if homogeneous:
            vals = [p["first_flash_yoy_pct"] for p in prior]
            median = statistics.median(vals)
            mad = statistics.median(abs(v-median) for v in vals)
            if mad > 1e-9:
                z = max(-3.0, min(3.0,
                    (row["first_flash_yoy_pct"]-median)/(1.4826*mad)))
        windows.append({
            "reference_month": row["reference_month"],
            "membership": row["membership"],
            "prior_24_same_membership": homogeneous,
            "research_robust_z_if_homogeneous": z,
            "GDP_or_FX_growth_approval": False,
        })
    require(sum(w["prior_24_same_membership"] for w in windows) == 48,
            "Eurozone 24-month cohort windows expected 36 EA19 + 12 EA20")
    visible = [r for r in rows if r["visible_at_cutoff"]]
    latest = visible[-1] if visible else None
    idx = rows.index(latest) if latest else -1
    prior_same = sum(r["membership"] == latest["membership"]
                     and r["visible_at_cutoff"] for r in rows[:idx]) if latest else 0
    return {
        "schema": "GMFQ_MACRO_V2_EUR_105_FIRST_WEB_POPULATION_QUALITY_V1",
        "as_of_utc": cutoff_utc.isoformat(),
        "regime_counts": counts,
        "membership_provenance": {name: {"first": first, "last": last,
                                         "official_reference_url": url}
                                  for name, first, last, url in REGIMES},
        "period_quality": windows,
        "homogeneous_24_prior_month_windows": 48,
        "nonhomogeneous_or_insufficient_24m_windows": 57,
        "last_visible_first_flash": ({
            "period": latest["reference_month"],
            "membership": latest["membership"],
            "value_yoy_pct": latest["first_flash_yoy_pct"],
            "first_publisher_gate_utc": latest["first_web_gate_utc"],
            "prior_visible_same_membership_months": prior_same,
            "same_membership_24m_reference_sufficient": (
                windows[idx]["prior_24_same_membership"]),
            "research_z_homogeneous": windows[idx]["research_robust_z_if_homogeneous"],
            "mixed_membership_24m_reference_must_be_estimate": (
                not windows[idx]["prior_24_same_membership"]),
        } if latest else None),
        "membership_homogeneity_not_same_as_historically_independent_PIT_archive": True,
        "safe_for_macro_score": False,
        "safe_for_FX_backtest": False,
    }


def swiss_quality(*, cutoff="2026-10-27T00:00:00Z"):
    cutoff_utc = utc(cutoff)
    source = SWISS_SEPT_2026
    report_day = date.fromisoformat(source["official_release_day"])
    rounded_gate = datetime.combine(report_day + timedelta(days=1),
                                    time.min, timezone.utc)
    visible = cutoff_utc >= rounded_gate
    published = Decimal(str(source["reported_rounded_sa_unemployment_pct"]))
    lower, upper = published-Decimal("0.05"), published+Decimal("0.05")
    current_exact = Decimal(str(source["current_SNB_revised_exact_pct"]))
    require(lower <= current_exact < upper,
            "SNB currently revised exact rate outside SECO one-decimal consistency interval")
    require(source["sa_unemployed_count_in_september_report"] == 147411 and
            source["august_count_as_first_published_in_august_report"] == 147970 and
            source["august_count_revised_in_september_report"] == 147886,
            "SECO original revised count evidence drift")
    return {
        "schema": "GMFQ_MACRO_V2_CHF_SECO_SNB_NO_PSEUDO_EXACT_V1",
        "reference_period": "2026-09",
        "official_SECO_report_date": source["official_release_day"],
        "SECO_rounded_first_report_consistently_visible_from_utc":
            rounded_gate.isoformat(),
        "source_clock_quality": "NEXT_UTC_DAY_CONSERVATIVE_NOT_ACTUAL_PUBLISHING_CLOCK",
        "rounded_SECO_sa_rate_pct_visible": float(published) if visible else None,
        "reported_rounding_precision_decimal_places": 1,
        "rounding_consistency_interval_pct": ({
            "lower_inclusive": float(lower),
            "upper_exclusive": float(upper),
        } if visible else None),
        "current_SNB_exact_observation_pct_NOT_FIRST_RELEASE_VINTAGE":
            float(current_exact),
        "original_exact_SNB_value_on_official_SECO_release_unverified": True,
        "exact_SNB_release_timestamp_utc": None,
        "rounded_3p1_cannot_prove_an_exact_number": True,
        "august_first_SECO_sa_count": 147970,
        "august_count_revision_visible_only_after_sep_release": (
            -84 if visible else None),
        "sep_SA_registered_count": 147411 if visible else None,
        "seco_august_and_september_rounded_rate_same_despite_revision": True,
        "official_SECO_august_url": source["official_august"],
        "official_SECO_september_url": source["official_september"],
        "snb_exact_cube_url": source["snb_api"],
        "SNB_exact_historic_release_PIT_approved": False,
        "no_imputation_of_exact_SNB_vintage": True,
        "safe_for_macro_score": False,
    }


def audit(*, as_of="2026-10-27T00:00:00Z"):
    e = euro_quality(cutoff=as_of)
    s = swiss_quality(cutoff=as_of)
    result = {
        "schema": SCHEMA,
        "status": "EA19_EA20_EA21_CHF_ROUNDING_RESEARCH_GUARDS_ACTIVE",
        "as_of_utc": utc(as_of).isoformat(),
        "eurozone_inflation": e, "swiss_labour": s,
        "summary": {
            "eur_first_flash_months": 105,
            "ea19": 60, "ea20": 36, "ea21": 9,
            "eur_homogeneous_24_prior_month_windows": 48,
            "eur_current_24m_same_membership_reference_sufficient": bool(
                e["last_visible_first_flash"] and
                e["last_visible_first_flash"]["same_membership_24m_reference_sufficient"]),
            "chf_exact_first_release_vintage_recovered": False,
            "macro_strength_scores_approved": 0,
            "FX_pair_rankings_changed": 0,
        },
        "safe_to_publish_new_D": False, "safe_to_change_28_pairs": False,
        "safe_for_beta": False, "safe_for_forward": False,
        "writes_live_data": False,
    }
    result["receipt_sha256"] = hashlib.sha256(json.dumps(
        {"eur": e, "chf": s}, sort_keys=True,
        separators=(",", ":")).encode()).hexdigest()
    return result


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--as-of")
    cli.add_argument("--output", type=Path)
    args = cli.parse_args()
    if args.output:
        require(args.output.resolve().is_relative_to(Path("/tmp")),
                "research output only /tmp")
    result = audit(as_of=args.as_of or
                   datetime.now(ZoneInfo("Europe/Rome")).astimezone(timezone.utc).isoformat())
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
    print(json.dumps({"status": result["status"], **result["summary"],
                      "safe_to_publish_new_D": False}, sort_keys=True))
