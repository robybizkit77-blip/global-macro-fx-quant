"""Observe archived Next directions against official ECB reference fixings."""
from __future__ import annotations

import argparse
from bisect import bisect_right
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

from validation.forward.observe_official_ecb_reference_outcomes_v1 import (
    FX_PATH, ROOT, ROME, SOURCE_URL, cross, source_map, stamp,
)

ARCHIVE = "site/fx-quant-v2/next/pair-estimate-history-v1.json"
PAIR_PATH = "live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json"
ARCHIVE_SCHEMA = "GMFQ_NEXT_ESTIMATED_FX_THESIS_HISTORY_V1"
SCHEMA = "GMFQ_NEXT_ESTIMATED_THESIS_ECB_FORWARD_OBSERVATION_V1"
PROSPECTIVE_FROM = date(2026, 11, 23)


def archived_snapshots(doc):
    if doc.get("schema") != ARCHIVE_SCHEMA or not isinstance(doc.get("snapshots"), list):
        raise ValueError("Invalid Next thesis archive")
    return doc["snapshots"]


def verify_first_archive_commits(snapshots, history):
    """Recover previous captures after they roll off the browser archive."""
    archived = {s["capturedAt"]: s for s in snapshots}
    if len(archived) != len(snapshots):
        raise ValueError("Duplicate capture time")
    first = {}
    for commit, committed_at, items in history:
        for row in items:
            key = row["capturedAt"]
            if row != archived.setdefault(key, row):
                raise ValueError(f"Archived thesis was rewritten at {key}")
            first.setdefault(key, (commit, committed_at))
    return sorted(archived.values(), key=lambda s: stamp(s["capturedAt"])), first


def git_history():
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT)

    history = git("log", "--first-parent", "--reverse", "--format=%H%x09%cI", "HEAD", "--", ARCHIVE)
    raw_path = Path(git("rev-parse", "--path-format=absolute", "--git-path", "shallow").decode().strip())
    shallow_roots = set(raw_path.read_text().splitlines()) if raw_path.exists() else set()
    for line in history.decode().splitlines():
        commit, committed_at = line.split("\t")
        if commit in shallow_roots:
            continue
        # A snapshot present at a shallow boundary has no provable introduction.
        parents = git("show", "-s", "--format=%P", commit).decode().split()
        if parents and parents[0] in shallow_roots:
            raise ValueError("Need the original Next thesis archive history")
        raw = git("show", f"{commit}:{ARCHIVE}")
        yield commit, committed_at, archived_snapshots(json.loads(raw))


def original_price_window(snapshot):
    commit = snapshot["commit"]
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Invalid original Next input commit")
    raw = subprocess.check_output(
        ["git", "show", f"{commit}:{FX_PATH.relative_to(ROOT)}"], cwd=ROOT,
    )
    if sha256(raw).hexdigest() != snapshot["sourceHashes"]["prices"]:
        raise ValueError("Archived ECB input bytes differ from the stored hash")
    return source_map(json.loads(raw))


def direction(before, after):
    if before is None or after is None:
        return None
    return (after > before) - (after < before)


def assess(snapshots, canonical_pairs, archive_commits, official, read_origin, now):
    instant = stamp(now.isoformat())
    local = instant.astimezone(ROME)
    # Today's fixing is admitted only at the existing conservative EOD cutoff.
    latest_allowed = local.date() if local.hour >= 19 else local.date() - timedelta(days=1)
    rates = source_map(official)
    observed = [d for d in rates if d <= latest_allowed]
    seen_days, used_intervals, reports = set(), set(), []
    previous = None
    for snap in snapshots:
        captured = stamp(snap["capturedAt"])
        fixing = date.fromisoformat(snap["fixing"])
        macro_day = date.fromisoformat(snap["macroAsOf"])
        capture_day = captured.astimezone(ROME).date()
        if (captured > instant or (previous is not None and captured <= previous)
                or max(fixing, macro_day) > capture_day
                or set(snap["pairs"]) != canonical_pairs
                or not re.fullmatch(r"[0-9a-f]{64}", snap["method"])):
            raise ValueError("Invalid chronology, method or pair universe in Next archive")
        for pair, item in snap["pairs"].items():
            if item["favored"] not in (None, pair[:3], pair[3:]):
                raise ValueError(f"Archived direction does not belong to {pair}")
        previous = captured
        report = {"capture_at_utc": snap["capturedAt"], "capture_day_rome": capture_day.isoformat(),
                  "original_fixing": snap["fixing"], "method": snap["method"],
                  "cohort": "PILOT" if capture_day < PROSPECTIVE_FROM else "POST_PROTOCOL",
                  "canonical_pairs": len(canonical_pairs)}
        reports.append(report)
        first = archive_commits.get(snap["capturedAt"])
        if not first:
            report["status"] = "ARCHIVE_PROVENANCE_PENDING"
            continue
        commit, committed_at = first
        admitted = max(captured, stamp(committed_at))
        if admitted > instant:
            raise ValueError("First archive commit is in the future")
        report["first_archive_commit"] = commit
        report["eligible_from_utc"] = admitted.isoformat()
        if capture_day in seen_days:
            report["status"] = "LATER_CAPTURE_SAME_DAY"
            continue
        seen_days.add(capture_day)
        start_date = admitted.astimezone(ROME).date()
        if observed and start_date < observed[0]:
            report["status"] = "OUTSIDE_RETAINED_ECB_HISTORY"
            continue
        start = bisect_right(observed, start_date)
        if start + 1 >= len(observed):
            report["status"] = "WAITING_FOR_TWO_LATER_ECB_FIXINGS"
            continue
        start_day, end_day = observed[start:start + 2]
        if (start_day, end_day) in used_intervals:
            report["status"] = "DUPLICATE_OUTCOME_INTERVAL"
            continue
        used_intervals.add((start_day, end_day))
        origin = read_origin(snap)
        initial = list(origin)
        if initial[-1] != fixing:
            raise ValueError("Snapshot fixing does not match its archived ECB input")
        if len(initial) < 6:
            raise ValueError("Five prior ECB intervals are required for the momentum benchmark")
        scores = []
        for pair, item in sorted(snap["pairs"].items()):
            base, quote = pair[:3], pair[3:]
            forecast = 0 if item["favored"] is None else (1 if item["favored"] == base else -1)
            momentum = direction(cross(origin[initial[-6]], base, quote),
                                 cross(origin[fixing], base, quote))
            outcome = direction(cross(rates[start_day], base, quote), cross(rates[end_day], base, quote))
            comparable = forecast != 0 and momentum in (-1, 1) and outcome in (-1, 1)
            scores.append({
                "pair": pair, "forecast": forecast, "momentum": momentum, "outcome": outcome,
                "head_to_head": comparable,
            })
        comparable = [row for row in scores if row["head_to_head"]]
        report.update({
            "status": "OBSERVED_ECB_INTERVAL",
            "start_fixing": start_day.isoformat(), "end_fixing": end_day.isoformat(),
            "directions_issued": sum(row["forecast"] != 0 for row in scores),
            "comparable_pairs": len(comparable),
            "next_correct": sum(row["forecast"] == row["outcome"] for row in comparable),
            "momentum_correct": sum(row["momentum"] == row["outcome"] for row in comparable),
            "missing_outcome_pairs": sum(row["outcome"] is None for row in scores),
            "pairs": scores,
        })
    return {
        "schema": SCHEMA, "status": "DESCRIPTIVE_ECB_OBSERVATION_ONLY",
        "checked_at_utc": instant.isoformat(), "ecb_last_eligible_fixing": observed[-1].isoformat() if observed else None,
        "prospective_captures_from_rome": PROSPECTIVE_FROM.isoformat(),
        "official_price_source": SOURCE_URL,
        "outcome_interval": "FIRST_TO_SECOND_ECB_FIXING_STRICTLY_AFTER_CAPTURE_AND_ARCHIVAL_DAY",
        "benchmark": "DIRECTION_OVER_FIVE_FIXING_INTERVALS_IN_ORIGINAL_ECB_INPUT",
        "comparison_sample": "DIRECTIONAL_NEXT_AND_MOMENTUM_WITH_NONFLAT_OBSERVED_MOVE",
        "predictive_validation_established": False,
        "site_or_core_scores_changed": False,
        "decision_days_not_pairs_are_the_observation_unit": True,
        "captures": reports,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    snapshots = archived_snapshots(json.loads((ROOT / ARCHIVE).read_bytes()))
    canonical_pairs = set(json.loads((ROOT / PAIR_PATH).read_bytes())["pairs"])
    if len(canonical_pairs) != 28:
        raise ValueError("Expected all 28 canonical pairs")
    snapshots, first_commits = verify_first_archive_commits(snapshots, git_history())
    result = assess(snapshots, canonical_pairs, first_commits, json.loads(FX_PATH.read_bytes()),
                    original_price_window, datetime.now(timezone.utc))
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for report in result["captures"]:
        if report["status"] == "OBSERVED_ECB_INTERVAL":
            print(f'{report["cohort"]} {report["capture_day_rome"]} {report["start_fixing"]} → '
                  f'{report["end_fixing"]}: Next {report["next_correct"]}/{report["comparable_pairs"]}, '
                  f'momentum {report["momentum_correct"]}/{report["comparable_pairs"]}')
        else:
            print(f'{report["cohort"]} {report["capture_day_rome"]}: {report["status"]}')


if __name__ == "__main__":
    main()
