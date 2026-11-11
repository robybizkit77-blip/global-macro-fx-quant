"""Bounded retry planning for a genuine GitHub Pages publication race.

Only explicit evidence that the validated main SHA or gh-pages lease moved
can cause a dispatch of the EXISTING publisher. An unrelated failed check
must never be auto-retried or silently reclassified as successful.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

MARKERS = {"MAIN_MOVED", "PAGES_MOVED"}
MAX_REDISPATCHES = 2


def plan(marker: str | None, attempt: str) -> dict:
    if marker not in MARKERS:
        return {"status": "NO_VERIFIED_SOURCE_RACE", "dispatch": False}
    if not isinstance(attempt, str) or attempt not in ("0", "1", "2"):
        return {"status": "INVALID_RECOVERY_COUNT", "dispatch": False}
    count = int(attempt)
    if count >= MAX_REDISPATCHES:
        return {"status": "RETRY_BUDGET_EXHAUSTED", "dispatch": False,
                "attempt": count, "cause": marker}
    return {"status": "RETRY_CURRENT_MAIN_REQUIRED", "dispatch": True,
            "attempt": count, "next_attempt": count + 1, "cause": marker}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--marker", type=Path, required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--github-output", type=Path, required=True)
    parser.add_argument("--github-summary", type=Path, required=True)
    args = parser.parse_args()
    marker = args.marker.read_text().strip() if args.marker.is_file() else None
    decision = plan(marker, args.attempt)
    with args.github_output.open("a", encoding="utf-8") as output:
        output.write("should_dispatch=" + str(decision["dispatch"]).lower() + "\n")
        output.write("next_attempt=" + str(decision.get("next_attempt", "")) + "\n")
    with args.github_summary.open("a", encoding="utf-8") as summary:
        summary.write("\n### Pages source-race bounded recovery\n")
        summary.write("- Status: **" + decision["status"] + "**\n")
        summary.write("- Source race: " + str(marker or "none verified") + "\n")
        summary.write("- No claimed publication or HTTP delivery from a retry request.\n")
    print("PAGES_RACE_RECOVERY", json.dumps(decision, sort_keys=True))


if __name__ == "__main__":
    main()
