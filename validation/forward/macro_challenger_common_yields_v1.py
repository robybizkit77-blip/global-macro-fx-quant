"""Prospective Macro challenger variant with independently dated common 2Y endpoints."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from hashlib import sha256
from inspect import getsource
import json
from math import isclose
from pathlib import Path
import subprocess

from validation.forward import macro_challenger_v1 as base
from validation.forward.observe_official_ecb_reference_outcomes_v1 import ROOT, ROME, cross, digest, source_map

ARCHIVE = ROOT / "research/macro-challenger-common-yields-v1"
METHOD = {
    "source": "OFFICIAL_NATIVE_GOVERNMENT_2Y_HISTORY_WITHIN_VERIFIED_WEEKLY_WINDOW",
    "target_span_days": 7, "min_span_days": 6, "max_span_days": 10,
    "end": "LATEST_COMMON_OBSERVATION", "start_tie_break": "MOST_RECENT",
}


def approved_history(row, today):
    window = base.rate_window(row, today)
    if window is None:
        return {}
    start, end, _ = window
    history = row.get("history2") or {}
    days, values = history.get("dates"), history.get("values")
    if not isinstance(days, list) or not isinstance(values, list) or len(days) != len(values) or not days:
        return {}
    window_rows = [(d, v) for d, v in zip(days, values)
                   if isinstance(d, str) and len(d) == 10 and start <= d <= end]
    window_dates = [d for d, _ in window_rows]
    if len(window_dates) != len(set(window_dates)) or window_dates != sorted(window_dates):
        return {}
    actual = {d: v for d, v in window_rows if base.finite(v)}
    checked = row["weekly2_validation"]
    if (start not in actual or end not in actual
            or not isclose(actual[start], checked["start_value"], rel_tol=0, abs_tol=1e-10)
            or not isclose(actual[end], checked["end_value"], rel_tol=0, abs_tol=1e-10)):
        return {}
    return {date.fromisoformat(d): v for d, v in actual.items()}


def matched_window(left, right):
    common = left.keys() & right.keys()
    if not common:
        return None
    end = max(common)
    span = lambda d: (end - d).days
    possible = [d for d in common if METHOD["min_span_days"] <= span(d) <= METHOD["max_span_days"]]
    if not possible:
        return None
    start = min(possible, key=lambda d: (abs(span(d) - METHOD["target_span_days"]), -d.toordinal()))
    delta = round(100 * ((left[end] - left[start]) - (right[end] - right[start])), 8)
    return start, end, delta


def build(original, rates, today):
    histories = {c: approved_history(rates.get(c, {}), today) for c in base.G8}
    proof = [getsource(f) for f in (approved_history, matched_window, build)]
    variant = {
        **original,
        "rates_window_method": METHOD,
        "base_formula_sha256": original["formula_sha256"],
        "formula_sha256": digest({"baseline": original["formula_sha256"], "rules": METHOD, "code": proof}),
        "pairs": {},
    }
    variant.pop("snapshot_sha256")
    for pair, evidence in original["pairs"].items():
        a, b = pair.split("/")
        window = matched_window(histories[a], histories[b])
        detail = dict(evidence)
        macro = base.vote(sum(v for v in (evidence["growth"], evidence["labour"]) if v is not None), 0)
        dates = None
        spread = None
        policy = None
        if window is not None:
            start, end, spread = window
            dates = [start.isoformat(), end.isoformat()]
            policy = base.vote(spread, base.METHOD["government_2y_change_threshold_bp"])
        conflict = policy is not None and macro * policy < 0
        detail.update(baseline_candidate=evidence["candidate"], candidate=0 if conflict else macro,
                      yield_spread_week_change_bp=spread, rates_window=dates,
                      rates_confirmed=bool(macro and macro == policy), rates_contradicted=conflict)
        variant["pairs"][pair] = detail
    return {**variant, "snapshot_sha256": digest(variant)}


def capture(now):
    raw = {key: path.read_bytes() for key, path in base.SOURCES.items()}
    inputs = {key: json.loads(contents) for key, contents in raw.items()}
    checkout = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    baseline = base.build(inputs, {key: sha256(contents).hexdigest() for key, contents in raw.items()}, now, checkout)
    today = now.astimezone(ROME).date()
    estimate = build(baseline, inputs["rates"], today)
    archive = ARCHIVE / (today.isoformat() + ".json")
    status = "WEEKEND_PREVIEW"
    if today.weekday() < 5:
        status = "ALREADY_FROZEN"
        if not archive.exists():
            archive.parent.mkdir(parents=True, exist_ok=True)
            with archive.open("x", encoding="utf-8") as f:
                f.write(json.dumps(estimate, indent=2, sort_keys=True) + "\n")
            status = "RECORDED"
    summary = {
        "baseline_comparable_2y": sum(v["rates_window"] is not None for v in baseline["pairs"].values()),
        "common_dates_comparable_2y": sum(v["rates_window"] is not None for v in estimate["pairs"].values()),
        "direction_changes": sum(v["candidate"] != baseline["pairs"][p]["candidate"]
                                 for p, v in estimate["pairs"].items()),
        "rates_confirmed": sum(v["rates_confirmed"] for v in estimate["pairs"].values()),
        "rates_contradicted": sum(v["rates_contradicted"] for v in estimate["pairs"].values()),
    }
    return {"status": status, "coverage": summary, "preview": estimate}


def evaluate(now):
    snapshots = [
        (p, json.loads(p.read_bytes()), subprocess.check_output(
            ["git", "log", "-1", "--diff-filter=A", "--format=%cI", "--", str(p.relative_to(ROOT))],
            cwd=ROOT, text=True).strip()) for p in sorted(ARCHIVE.glob("*.json"))
    ]
    official = json.loads(base.FX_PATH.read_bytes())
    report = base.evaluate(snapshots, official, now)
    archived = {s["capture_day"]: s["pairs"] for _, s, _ in snapshots}
    history = source_map(official)
    for window in report["windows"]:
        if window["status"] != "OBSERVED":
            continue
        start, end = (history[date.fromisoformat(window[k])] for k in ("start_fixing", "end_fixing"))
        comparison = dict.fromkeys(("comparable_pairs", "original_rule_correct", "common_date_rule_correct"), 0)
        for pair, signal in archived[window["capture_day"]].items():
            a, b = pair.split("/")
            actual = base.direction(cross(start, a, b), cross(end, a, b))
            original, synchronized = signal["baseline_candidate"], signal["candidate"]
            if actual in (-1, 1) and original in (-1, 1) and synchronized in (-1, 1):
                comparison["comparable_pairs"] += 1
                comparison["original_rule_correct"] += int(original == actual)
                comparison["common_date_rule_correct"] += int(synchronized == actual)
        window["comparison_to_original_rule_same_inputs"] = comparison
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("capture", "evaluate"))
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if not args.receipt.resolve().is_relative_to(Path("/tmp")):
        parser.error("research receipt must be under /tmp")
    now = datetime.now(timezone.utc)
    report = capture(now) if args.operation == "capture" else evaluate(now)
    print("MACRO_COMMON_YIELDS", json.dumps({key: report[key] for key in
          ("status", "coverage", "windows") if key in report}, sort_keys=True))
    args.receipt.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
