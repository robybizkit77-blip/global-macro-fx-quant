"""Compare the existing Next estimate, frozen Core and momentum on identical
future ECB windows. Read-only research; no scores, rankings or signals written.
Git commit times are conservative archive anchors, not independently verified
publication timestamps. Recover rolled-out snapshots from main's history.
"""
from __future__ import annotations
import argparse
from bisect import bisect_right
from datetime import date, datetime, timedelta, timezone
from functools import cache
from itertools import combinations
import json
from pathlib import Path
import re
import subprocess

from validation.forward.check_frozen_core_macro_directions_v1 import (
    direction, side, input_price_history,
)
from validation.forward.observe_official_ecb_reference_outcomes_v1 import (
    ROOT, FX_PATH, ROME, SOURCE_URL, cross, source_map, stamp,
)
from validation.macro.score_formula_provenance_v1 import FROZEN_MACRO_ASOF

ARCHIVE = "site/fx-quant-v2/next/pair-estimate-history-v1.json"
CORE = "live_data/sections/D.json"
SCHEMA = "GMFQ_NEXT_ESTIMATE_CORE_WEEKLY_COMPARISON_V1"
G8 = set("USD EUR GBP JPY CHF CAD AUD NZD".split())


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def day(value):
    d = date.fromisoformat(value)
    if d.isoformat() != value:
        raise ValueError("Invalid date")
    return d


def recover(revisions):
    """First commit containing each exact snapshot; reject changed duplicates."""
    seen = {}
    for archive, commit_time in revisions:
        if archive["schema"] != "GMFQ_NEXT_ESTIMATED_FX_THESIS_HISTORY_V1":
            raise ValueError("Unknown estimated archive")
        for snap in archive["snapshots"]:
            key = snap["capturedAt"]
            stamp(key)
            if key in seen:
                if seen[key][0] != snap:
                    raise ValueError("Previously recorded estimate changed")
            else:
                seen[key] = (snap, commit_time)
    return list(seen.values())


def read_archive():
    commits = git("log", "--first-parent", "--reverse", "--format=%H", "--", ARCHIVE).decode().splitlines()
    if not commits:
        raise ValueError("No Git archive history")
    return recover((json.loads(git("show", f"{c}:{ARCHIVE}")),
                    git("show", "-s", "--format=%cI", c).decode().strip())
                   for c in commits)


@cache
def origin(commit, price_sha):
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Invalid source commit")
    return (input_price_history(commit, price_sha),
            json.loads(git("show", f"{commit}:{CORE}")),
            git("show", "-s", "--format=%cI", commit).decode().strip())


def evaluate(entries, official, read_origin, now):
    instant = stamp(now.isoformat())
    local = instant.astimezone(ROME)
    limit = local.date() - timedelta(days=int(local.hour < 19))
    current = source_map(official)
    dates = [d for d in current if d <= limit]
    prepared = []
    for snap, first_seen in entries:
        captured = stamp(snap["capturedAt"])
        anchor = max(captured, stamp(first_seen))
        if anchor > instant or day(snap["macroAsOf"]) > captured.astimezone(ROME).date():
            raise ValueError("Future estimate")
        method = snap["method"]
        if not re.fullmatch(r"[a-f0-9]{64}", method):
            raise ValueError("Missing method fingerprint")
        original, core, source_time = read_origin(snap["commit"], snap["sourceHashes"]["prices"])
        odates = list(original)
        if (stamp(source_time) > anchor or len(odates) < 6 or odates[-1] != day(snap["fixing"])
                or odates[-1] > captured.astimezone(ROME).date()
                or core["asOf"] != FROZEN_MACRO_ASOF):
            raise ValueError("Invalid original benchmark or Core vintage")
        names = [p["pair"] for p in core["pairs"]]
        if (len(names) != 28 or {frozenset(p.split("/")) for p in names} !=
                {frozenset(p) for p in combinations(G8, 2)}
                or set(snap["pairs"]) != {p.replace("/", "") for p in names}):
            raise ValueError("Invalid canonical pair coverage")
        votes = {}
        for p in names:
            a, b = p.split("/")
            favored = snap["pairs"][p.replace("/", "")]["favored"]
            if favored not in (None, a, b):
                raise ValueError("Invalid estimated pair orientation")
            votes[p] = (side(favored, a, b), side(core["pairStates"][p]["convergence_winner"], a, b),
                        direction(cross(original[odates[-6]], a, b), cross(original[odates[-1]], a, b)))
        prepared.append((anchor, captured, method, votes))

    windows, summaries, seen_days, last_end = [], {}, set(), {}
    for anchor, captured, method, votes in sorted(prepared, key=lambda x: (x[0], x[1])):
        capture_day = anchor.astimezone(ROME).date()
        key = (method, capture_day)
        if key in seen_days:
            continue
        seen_days.add(key)
        due = (anchor + timedelta(days=7)).astimezone(ROME).date()
        ai, bi = bisect_right(dates, capture_day), bisect_right(dates, due)
        summary = summaries.setdefault(method, dict.fromkeys(
            ("windows", "comparable_pairs", "estimate_correct", "core_correct", "momentum_correct"), 0))
        row = {"anchor_day": capture_day.isoformat(), "method": method,
               "estimate_directional_pairs": sum(v[0] != 0 for v in votes.values()),
               "status": "WAITING_FOR_WEEKLY_ECB_OUTCOME"}
        windows.append(row)
        if dates and capture_day < dates[0]:
            row["status"] = "OUTSIDE_RETAINED_ECB_HISTORY"
            continue
        if ai >= bi or bi >= len(dates):
            continue
        start, end = dates[ai], dates[bi]
        if (end - due).days > 4:
            row["status"] = "SOURCE_GAP"
            continue
        counts = dict.fromkeys(("comparable_pairs", "estimate_correct", "core_correct", "momentum_correct"), 0)
        for p, preds in votes.items():
            a, b = p.split("/")
            outcome = direction(cross(current[start], a, b), cross(current[end], a, b))
            if outcome in (-1, 1) and all(v in (-1, 1) for v in preds):
                counts["comparable_pairs"] += 1
                for label, pred in zip(("estimate_correct", "core_correct", "momentum_correct"), preds):
                    counts[label] += int(pred == outcome)
        selected = bool(counts["comparable_pairs"] and (method not in last_end or start >= last_end[method]))
        if selected:
            last_end[method] = end
            summary["windows"] += 1
            for k, v in counts.items():
                summary[k] += v
        row.update(counts, status="OBSERVED", start_fixing=start.isoformat(), end_fixing=end.isoformat(),
                   selected_nonoverlapping=selected)
    return {"schema": SCHEMA, "checked_at_utc": instant.isoformat(), "source": SOURCE_URL,
            "archive_snapshots": len(entries), "windows": windows, "nonoverlapping_by_method": summaries,
            "pair_rows_are_independent_trials": False, "historical_pit_certified": False,
            "predictive_validation_established": False, "eligible_to_replace_core": False,
            "live_model_changed": False, "reference_prices_not_executable": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    a = parser.parse_args()
    if not a.receipt.resolve().is_relative_to(Path("/tmp")):
        parser.error("Read-only receipt must be under /tmp")
    result = evaluate(read_archive(), json.loads(FX_PATH.read_bytes()), origin, datetime.now(timezone.utc))
    a.receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("NEXT_ESTIMATE_CORE_WEEKLY", json.dumps(result["nonoverlapping_by_method"], sort_keys=True))


if __name__ == "__main__":
    main()
