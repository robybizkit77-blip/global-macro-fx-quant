"""Compare the archived September Core and its macro vote with later ECB prices."""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from functools import cache
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import subprocess

from validation.forward.observe_official_ecb_reference_outcomes_v1 import (
    DECISIONS, FX_PATH, HORIZONS, REFERENCE_LOG, ROOT, ROME, SCHEMA as REF_SCHEMA,
    SOURCE_URL, cross, digest, eligible_decision, rows, source_map, stamp,
)
from validation.macro.score_formula_provenance_v1 import FROZEN_MACRO_ASOF

HORIZON = "1W"
SCHEMA = "GMFQ_FROZEN_CORE_MACRO_DIRECTIONS_ECB_COMPARISON_V1"


@cache
def input_price_history(commit, expected_sha):
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Invalid original ECB input commit")
    raw = subprocess.check_output(["git", "show", f"{commit}:{FX_PATH.relative_to(ROOT)}"], cwd=ROOT)
    if sha256(raw).hexdigest() != expected_sha:
        raise ValueError("Original ECB input checksum mismatch")
    return source_map(json.loads(raw))


def direction(before, after):
    if before is None or after is None:
        return None
    return (after > before) - (after < before)


def side(seed, base, quote):
    return 1 if seed == base else -1 if seed == quote else 0


def summarize(windows):
    result = {"windows": len(windows)}
    for name in ("macro", "core"):
        result[name] = {
            key: sum(w[name][key] for w in windows)
            for key in ("comparable_pairs", "correct", "momentum_correct")
        }
    return result


def assess(decisions, references, official, canonical_pairs, read_origin, now):
    instant = stamp(now.isoformat())
    local = instant.astimezone(ROME)
    latest_allowed = local.date() if local.hour >= 19 else local.date() - timedelta(days=1)
    current = source_map(official)
    dates = [day for day in current if day <= latest_allowed]
    snapshots, grouped, forecast_sets = {}, defaultdict(list), set()

    for row in decisions:
        if row.get("capture_class") != "FROZEN_CORE_BASELINE_OBSERVATION":
            continue
        sid = row["snapshot_id"]
        if sid in snapshots:
            raise ValueError("Duplicate frozen decision")
        snapshots[sid] = (row, eligible_decision(row, current))
        grouped[row["decision_cutoff"]].append(row)
    capture_days = set()
    for cutoff, batch in grouped.items():
        decision_time = stamp(cutoff)
        capture_day = decision_time.astimezone(ROME).date()
        if (decision_time > instant or capture_day in capture_days or len(batch) != len(canonical_pairs)
                or {r["pair"] for r in batch} != canonical_pairs):
            raise ValueError("Unexpected date or pair coverage in frozen Core capture")
        capture_days.add(capture_day)
        vector = []
        for row in sorted(batch, key=lambda r: r["pair"]):
            state = row["inputs"]["core_pair_state"]
            if (state["state"] != "AVAILABLE" or state["observed_or_as_of"] != FROZEN_MACRO_ASOF
                    or state["value"]["convergence_winner"] != row["core_signal"]):
                raise ValueError("Archived pair state does not support the frozen direction")
            vote = state["value"]["layers"]["macro"]
            vector.append((row["pair"], vote, row["core_signal"]))
        forecast_sets.add(tuple(vector))

    windows = {}
    seen = set()
    for ref in references:
        if ref.get("horizon") != HORIZON:
            continue
        sid = ref["snapshot_id"]
        if (sid in seen or sid not in snapshots or ref["schema"] != REF_SCHEMA
                or ref["observation_sha256"] != digest({k: v for k, v in ref.items() if k != "observation_sha256"})):
            raise ValueError("Duplicate, orphaned or changed weekly ECB record")
        seen.add(sid)
        row, capture = snapshots[sid]
        if capture is None:
            raise ValueError("Weekly ECB record has no archived anchor")
        cutoff, day, pair, base, quote, t0_rate = capture
        due = (cutoff + timedelta(days=HORIZONS[HORIZON])).astimezone(ROME).date()
        # Compare the first ECB fixing AFTER the capture with the existing
        # observer's week-end fixing. The same-day anchor was already known.
        start_index = bisect_right(dates, day)
        end_index = bisect_right(dates, due)
        if start_index >= end_index or end_index >= len(dates):
            raise ValueError("Weekly outcome lies outside the eligible ECB window")
        start, end = dates[start_index], dates[end_index]
        end_rate = cross(current[end], base, quote)
        if (ref["pair"] != pair or stamp(ref["decision_cutoff_utc"]) != cutoff
                or date.fromisoformat(ref["t0_fixing_date"]) != day
                or date.fromisoformat(ref["target_due_date"]) != due
                or date.fromisoformat(ref["observed_reference_date"]) != end
                or ref["reference_source"] != SOURCE_URL or (end - due).days > 4
                or end_rate is None or not math.isclose(ref["observed_ecb_rate"], end_rate)
                or not math.isclose(ref["t0_ecb_rate"], t0_rate)):
            raise ValueError("Weekly ECB record does not match its dates, prices and archive")

        original = read_origin(row["source_commit"], row["t0_fx_reference"]["source_sha256"])
        original_dates = list(original)
        if len(original_dates) < 6 or original_dates[-1] != day:
            raise ValueError("Missing five-fixing momentum history as observed at capture")
        bench = direction(cross(original[original_dates[-6]], base, quote),
                          cross(original[day], base, quote))
        outcome = direction(cross(current[start], base, quote), end_rate)
        window = windows.setdefault(day, {
            "capture_day": day.isoformat(), "start_fixing": start.isoformat(), "end_fixing": end.isoformat(),
            "reference_rows": 0, "macro": dict.fromkeys(("comparable_pairs", "correct", "momentum_correct"), 0),
            "core": dict.fromkeys(("comparable_pairs", "correct", "momentum_correct"), 0),
        })
        window["reference_rows"] += 1
        votes = {"macro": row["inputs"]["core_pair_state"]["value"]["layers"]["macro"],
                 "core": row["core_signal"]}
        for name, vote in votes.items():
            prediction = side(vote, base, quote)
            if prediction and bench in (-1, 1) and outcome in (-1, 1):
                out = window[name]
                out["comparable_pairs"] += 1
                out["correct"] += int(prediction == outcome)
                out["momentum_correct"] += int(bench == outcome)

    complete = [w for _, w in sorted(windows.items()) if w["reference_rows"] == len(canonical_pairs)]
    nonoverlap = []
    for w in complete:
        if not nonoverlap or w["start_fixing"] >= nonoverlap[-1]["end_fixing"]:
            nonoverlap.append(w)
    return {
        "schema": SCHEMA, "status": "FROZEN_BASELINE_REFERENCE_DIAGNOSTIC_ONLY",
        "checked_at_utc": instant.isoformat(), "baseline_as_of": FROZEN_MACRO_ASOF,
        "captured_days": len(grouped), "unique_frozen_direction_vectors": len(forecast_sets),
        "official_reference_source": SOURCE_URL, "outcome_horizon": HORIZON,
        "benchmark": "FIVE_FIXINGS_MOMENTUM_SAME_CASES",
        "all_complete_windows": summarize(complete),
        "nonoverlapping_windows": summarize(nonoverlap),
        "nonoverlapping_capture_dates": [w["capture_day"] for w in nonoverlap],
        "observed_windows": [w for _, w in sorted(windows.items())],
        "pair_rows_are_independent_trials": False,
        "new_macro_calibration_or_trading_performance_established": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    opts = parser.parse_args()
    if not opts.receipt.resolve().is_relative_to(Path("/tmp")):
        parser.error("research receipt must be under /tmp")
    core = json.loads((ROOT / "live_data/sections/D.json").read_bytes())
    pairs = {row["pair"] for row in core["pairs"]}
    if len(pairs) != 28:
        raise ValueError("Expected 28 canonical Core pairs")
    result = assess(rows(DECISIONS), rows(REFERENCE_LOG), json.loads(FX_PATH.read_bytes()),
                    pairs, input_price_history, datetime.now(timezone.utc))
    opts.receipt.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "baseline_as_of", "captured_days", "unique_frozen_direction_vectors",
        "all_complete_windows", "nonoverlapping_windows",
    )}, sort_keys=True))


if __name__ == "__main__":
    main()
