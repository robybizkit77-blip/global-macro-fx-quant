"""Read-only market inputs and prospective weekly observations for a Macro challenger."""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from inspect import getsource
from itertools import combinations
import json
import math
from pathlib import Path
import re
import subprocess

from validation.forward.check_frozen_core_macro_directions_v1 import direction, side
from validation.forward.observe_official_ecb_reference_outcomes_v1 import (
    FX_PATH, HORIZONS, ROOT, ROME, SOURCE_URL, cross, digest, source_map, stamp,
)
from validation.macro.score_formula_provenance_v1 import FROZEN_MACRO_ASOF

SCHEMA = "GMFQ_STRUCTURAL_MACRO_CHALLENGER_WEEKLY_V1"
ARCHIVE = ROOT / "research/macro-challenger-weekly-v1"
G8 = {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"}
SOURCES = {
    "macro": ROOT / "site/control-room-preview/macro-v3-current-evidence.json",
    "rates": ROOT / "live_data/sections/NATIVE_RATES_DATA.json",
    "core": ROOT / "live_data/sections/D.json",
    "prices": FX_PATH,
}
METHOD = {
    "growth_basis": "MATCHED_QUARTER_ACCELERATION_WHEN_BOTH_AVAILABLE_ELSE_MATCHED_QUARTER_GDP_LEVEL",
    "growth_acceleration_deadband_pp": 0.10, "growth_level_deadband_pct": 0.20,
    "unemployment_deadband_pp": 0.10, "unemployment_max_observation_lag_months": 1,
    "government_2y_change_threshold_bp": 5, "government_2y_max_quote_age_days": 7,
    "policy_rule": "YIELDS_CAN_CONFIRM_OR_VETO_A_MACRO_DIRECTION_BUT_CANNOT_CREATE_ONE",
    "inflation": "CONTEXT_ONLY_NO_ASSUMED_DIRECTION", "fx": "BENCHMARK_ONLY",
    "horizon": "FIRST_ECB_FIXING_AFTER_CAPTURE_TO_FIRST_AFTER_SEVEN_CALENDAR_DAYS",
}


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def vote(value, band):
    return 1 if value > band else -1 if value < -band else 0


def quarter_index(q):
    return 4 * int(q[:4]) + int(q[-1]) if isinstance(q, str) and re.fullmatch(r"[0-9]{4}Q[1-4]", q) else None


def growth_history(row, today):
    results = {}
    for item in (row, row.get("prior_documented_quarter") or {}):
        q = quarter_index(item.get("reference_quarter"))
        rate = item.get("nonannualized_qoq_descriptive_pct")
        if (q is not None and item.get("is_growth_strength_score") is False and finite(rate)
                and date.fromisoformat(item["publisher_release_day"]) <= today):
            results[q] = rate
    return results


def observation_month(period):
    if isinstance(period, str) and re.fullmatch(r"[0-9]{4}-(?:0[1-9]|1[0-2])(?:-[0-9]{2})?", period):
        return 12 * int(period[:4]) + int(period[5:7])
    return None


def rate_window(row, today):
    summary = row.get("weekly2_validation")
    if (not isinstance(summary, dict)
            or row.get("freshness_status") not in
            {"CURRENT_OFFICIAL_SAME_BASIS", "CURRENT_OFFICIAL_SAME_BASIS_MANUAL_VERIFIED"}):
        return None
    start, end = date.fromisoformat(summary["start_date"]), date.fromisoformat(summary["end_date"])
    a, b, change = (summary.get(k) for k in ("start_value", "end_value", "change_bp"))
    if (start >= end or not 0 <= (today - end).days <= METHOD["government_2y_max_quote_age_days"]
            or row.get("date") != end.isoformat() or summary.get("source") != row.get("source")
            or not all(finite(x) for x in (a, b, change, row.get("2Y")))
            or not math.isclose(row["2Y"], b) or abs((b - a) * 100 - change) > 0.11):
        return None
    return (start.isoformat(), end.isoformat(), change)


def compare_pair(base, quote, macro, rates, today):
    gb, gq = (growth_history(macro[c]["growth"], today) for c in (base, quote))
    common = gb.keys() & gq.keys()
    growth = None
    basis = None
    if common:
        q = max(common)
        if q - 1 in common:
            band = METHOD["growth_acceleration_deadband_pp"]
            growth = direction(vote(round(gq[q] - gq[q - 1], 8), band),
                               vote(round(gb[q] - gb[q - 1], 8), band))
            basis = "GDP_ACCELERATION"
        else:
            band = METHOD["growth_level_deadband_pct"]
            growth = direction(vote(gq[q], band), vote(gb[q], band))
            basis = "GDP_LEVEL"
        basis += f"_{(q - 1) // 4}Q{(q - 1) % 4 + 1}"

    a, b = (macro[c]["labour"] for c in (base, quote))
    am, bm = observation_month(a["observation_period"]), observation_month(b["observation_period"])
    av, bv = (item.get("change_over_three_observation_intervals_pp") for item in (a, b))
    labour = None
    if (am is not None and bm is not None and abs(am - bm) <= METHOD["unemployment_max_observation_lag_months"]
            and max(am, bm) <= today.year * 12 + today.month and finite(av) and finite(bv)):
        band = METHOD["unemployment_deadband_pp"]
        labour = direction(vote(-bv, band), vote(-av, band))

    rb, rq = (rate_window(rates.get(c, {}), today) for c in (base, quote))
    gap = round(rb[2] - rq[2], 8) if rb and rq and rb[:2] == rq[:2] else None
    policy = vote(gap, METHOD["government_2y_change_threshold_bp"]) if gap is not None else None
    macro_side = vote(sum(x for x in (growth, labour) if x is not None), 0)
    conflict = policy is not None and macro_side * policy < 0
    fav = 0 if conflict else macro_side
    return {"candidate": fav, "growth": growth, "growth_basis": basis, "labour": labour,
            "yield_spread_week_change_bp": gap, "rates_window": list(rb[:2]) if gap is not None else None,
            "rates_confirmed": bool(fav and policy == fav), "rates_contradicted": conflict}


def build(inputs, hashes, now, input_commit):
    captured = stamp(now.isoformat())
    today = captured.astimezone(ROME).date()
    context, core = inputs["macro"], inputs["core"]
    countries = context["countries"]
    if (context.get("schema") != "GMFQ_MACRO_V3_G8_28PAIR_PUBLIC_OBSERVED_CONTEXT_V1"
            or context.get("safe_to_republish_D") is not False
            or not 0 <= (today - date.fromisoformat(context["generated_europe_rome_day"])).days <= 7
            or set(countries) != G8 or core["asOf"] != FROZEN_MACRO_ASOF):
        raise ValueError("Missing or stale G8 observation, or frozen Core reference changed")
    pair_names = [entry["pair"] for entry in core["pairs"]]
    if (len(pair_names) != 28 or {frozenset(p.split("/")) for p in pair_names}
            != {frozenset(p) for p in combinations(G8, 2)}):
        raise ValueError("Expected exactly the canonical 28 pair orientations")
    official = source_map(inputs["prices"])
    fixing_days = list(official)
    last = fixing_days[-1]
    # Intraday: a same-date ECB file on main has already been retrieved by the
    # collector. The source is used only as a benchmark, not in the candidate.
    if len(fixing_days) < 6 or not 0 <= (today - last).days <= 5:
        raise ValueError("No recent five-fixing ECB benchmark")
    start = fixing_days[-6]
    pairs = {}
    for pair in sorted(pair_names):
        base, quote = pair.split("/")
        detail = compare_pair(base, quote, countries, inputs["rates"], today)
        detail["core"] = side(core["pairStates"][pair]["convergence_winner"], base, quote)
        detail["momentum"] = direction(cross(official[start], base, quote), cross(official[last], base, quote))
        pairs[pair] = detail
    source = [getsource(f) for f in (build, compare_pair, rate_window, observation_month, growth_history,
                                    quarter_index, vote, direction, side)]
    body = {
        "schema": SCHEMA, "method": METHOD, "capture_at_utc": captured.isoformat(),
        "formula_sha256": digest({"method": METHOD, "source": source}),
        "capture_day": today.isoformat(), "input_commit": input_commit, "source_sha256": hashes,
        "macro_public_snapshot_day": context["generated_europe_rome_day"], "core_as_of": FROZEN_MACRO_ASOF,
        "benchmark_from": start.isoformat(), "benchmark_through": last.isoformat(),
        "inflation_context": {c: {k: countries[c]["inflation"].get(k)
                                  for k in ("observation_period", "change_direction")}
                              for c in sorted(G8)},
        "pairs": pairs, "safe_to_publish_new_core": False, "historical_vintages_certified": False,
    }
    return {**body, "snapshot_sha256": digest(body)}


def evaluate(files, official, now):
    instant = stamp(now.isoformat())
    local = instant.astimezone(ROME)
    latest = local.date() if local.hour >= 19 else local.date() - timedelta(days=1)
    rates = source_map(official)
    dates = [d for d in rates if d <= latest]
    result = []
    end_by_method = {}
    summaries = defaultdict(lambda: dict.fromkeys(("windows", "candidate", "core", "momentum", "comparable_pairs"), 0))
    for path, row, commit_time in files:
        if (row["schema"] != SCHEMA or row["method"] != METHOD or row.get("safe_to_publish_new_core") is not False
                or row["snapshot_sha256"] != digest({k: v for k, v in row.items() if k != "snapshot_sha256"})):
            raise ValueError("Archived challenger snapshot does not match its frozen contract")
        capture = stamp(row["capture_at_utc"])
        anchor = max(capture, stamp(commit_time))
        if (path.stem != row["capture_day"] or len(row["pairs"]) != 28 or anchor > instant
                or capture.astimezone(ROME).date().isoformat() != row["capture_day"]):
            raise ValueError("Invalid challenger archive date or pair coverage")
        capture_day = anchor.astimezone(ROME).date()
        due = (anchor + timedelta(days=HORIZONS["1W"])).astimezone(ROME).date()
        ai, bi = bisect_right(dates, capture_day), bisect_right(dates, due)
        method = row["formula_sha256"]
        if not re.fullmatch(r"[0-9a-f]{64}", method):
            raise ValueError("Missing frozen formula fingerprint")
        summary = summaries[method]
        window = {"capture_day": row["capture_day"], "formula_sha256": method,
                  "status": "WAITING_FOR_WEEKLY_ECB_OUTCOME"}
        result.append(window)
        if dates and capture_day < dates[0]:
            window["status"] = "OUTSIDE_RETAINED_ECB_HISTORY"
            continue
        if ai >= bi or bi >= len(dates):
            continue
        start, end = dates[ai], dates[bi]
        if (end - due).days > 4:
            window["status"] = "SOURCE_GAP"
            continue
        scores = {"candidate": 0, "core": 0, "momentum": 0, "comparable_pairs": 0}
        for pair, value in row["pairs"].items():
            base, quote = pair.split("/")
            outcome = direction(cross(rates[start], base, quote), cross(rates[end], base, quote))
            names = ("candidate", "core", "momentum")
            if outcome in (-1, 1) and all(value[k] in (-1, 1) for k in names):
                scores["comparable_pairs"] += 1
                for name in names:
                    scores[name] += int(value[name] == outcome)
        last_end = end_by_method.get(method)
        nonoverlap = bool(scores["comparable_pairs"] and (last_end is None or start >= last_end))
        if nonoverlap:
            end_by_method[method] = end
            summary["windows"] += 1
            for key in scores:
                summary[key] += scores[key]
        window.update(scores, status="OBSERVED", start_fixing=start.isoformat(), end_fixing=end.isoformat(),
                      selected_nonoverlapping=nonoverlap)
    return {"schema": SCHEMA, "checked_at_utc": instant.isoformat(), "reference_source": SOURCE_URL,
            "windows": result, "nonoverlapping_by_formula": dict(summaries),
            "predictive_validation_established": False}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("operation", choices=("capture", "evaluate"))
    ap.add_argument("--receipt", type=Path, required=True)
    args = ap.parse_args()
    now = datetime.now(timezone.utc)
    if not args.receipt.resolve().is_relative_to(Path("/tmp")):
        ap.error("research receipt must be under /tmp")
    if args.operation == "capture":
        raw = {key: p.read_bytes() for key, p in SOURCES.items()}
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        snap = build({k: json.loads(v) for k, v in raw.items()},
                     {k: sha256(v).hexdigest() for k, v in raw.items()}, now, head)
        path = ARCHIVE / (snap["capture_day"] + ".json")
        status = "WEEKEND_PREVIEW"
        if now.astimezone(ROME).weekday() < 5:
            status = "ALREADY_FROZEN"
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("x", encoding="utf-8") as f:
                    f.write(json.dumps(snap, indent=2, sort_keys=True) + "\n")
                status = "RECORDED"
        report = {"status": status, "preview": snap}
        print(status, snap["capture_day"], "directions", sum(v["candidate"] != 0 for v in snap["pairs"].values()),
              "rates confirmed", sum(v["rates_confirmed"] for v in snap["pairs"].values()))
    else:
        paths = sorted(ARCHIVE.glob("*.json"))
        frozen = [
            (p, json.loads(p.read_bytes()), subprocess.check_output(
                ["git", "log", "-1", "--diff-filter=A", "--format=%cI", "--", str(p.relative_to(ROOT))],
                cwd=ROOT, text=True).strip()) for p in paths
        ]
        report = evaluate(frozen, json.loads(FX_PATH.read_bytes()), now)
        print("WEEKLY_ECB", json.dumps(report["windows"], sort_keys=True))
    args.receipt.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
