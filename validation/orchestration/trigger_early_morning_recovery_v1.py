"""Separate early trigger for a missing pre-08:00 data refresh.

The 05:00 Rome opening admits already observed 05:04 operational source
completion events while retaining the same strict max-two manual recovery
budget, active-run guard and 07:30 cutoff.

No market-data changes here. Check actual run steps; never infer completion from
a green workflow whose production job was skipped (e.g. CET/CEST counterpart).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
SCRIPT = "daily-data-orchestrator-v2.yml"
ESSENTIAL = (
    "Run serialized refresh sequence",
    "Audit true source dates for the morning study",
    "Certify 08:00 morning delivery deadline",
)


def local(stamp: str) -> dt.datetime:
    return dt.datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(ROME)


def choose(now: dt.datetime, runs: list[dict], jobs: dict[int, list[dict]]) -> dict:
    t = now.astimezone(ROME)
    if t.weekday() >= 5 or not (dt.time(5, 0) <= t.time() <= dt.time(7, 30)):
        return {"action": "SKIP_OUTSIDE_RECOVERY_WINDOW"}
    existing_manual = 0
    active = False
    successful = False
    for r in runs:
        try:
            created = local(r["created_at"])
        except (KeyError, TypeError, ValueError):
            continue
        if (r.get("head_branch") != "main" or created.date() != t.date()
                or created.time() < dt.time(4, 15) or created > t):
            continue
        if r.get("event") not in ("schedule", "workflow_dispatch"):
            continue
        if r["event"] == "workflow_dispatch" and created.time() >= dt.time(5, 0):
            existing_manual += 1
        # A queued/in-progress manual recovery already owns the work. A
        # scheduled run only blocks if it entered the actual production step.
        if r.get("status") != "completed":
            if r.get("event") == "workflow_dispatch":
                active = True
            else:
                for j in jobs.get(r["id"], []):
                    if j.get("name") == "orchestrate":
                        for s in j.get("steps", []):
                            if (s.get("name") == ESSENTIAL[0]
                                    and s.get("status") in ("in_progress", "queued")):
                                active = True
            continue
        if r.get("conclusion") != "success":
            continue
        for j in jobs.get(r["id"], []):
            if j.get("name") != "orchestrate" or j.get("conclusion") != "success":
                continue
            steps = {s.get("name"): s.get("conclusion") for s in j.get("steps", [])}
            if all(steps.get(name) == "success" for name in ESSENTIAL):
                successful = True
    if successful:
        return {"action": "SKIP_ALREADY_VERIFIED_MORNING"}
    if active:
        return {"action": "SKIP_PRODUCTION_ACTIVE"}
    if existing_manual >= 2:
        return {"action": "SKIP_RECOVERY_LIMIT_REACHED"}
    return {"action": "DISPATCH", "phase": "prebrief" if t.time() < dt.time(6, 35)
            else "premorning"}


def gh_get(endpoint: str) -> dict:
    return json.loads(subprocess.check_output(
        ["gh", "api", endpoint], text=True, timeout=35))


def main() -> None:
    repo = os.environ["GITHUB_REPOSITORY"]
    now = dt.datetime.now(dt.timezone.utc)
    runs = gh_get(f"repos/{repo}/actions/workflows/{SCRIPT}/runs?per_page=100")["workflow_runs"]
    jobs = {}
    for r in runs:
        if r.get("event") in ("schedule", "workflow_dispatch"):
            try:
                if local(r["created_at"]).date() == now.astimezone(ROME).date():
                    jobs[r["id"]] = gh_get(f"repos/{repo}/actions/runs/{r['id']}/jobs?per_page=100")["jobs"]
            except (KeyError, ValueError, TypeError):
                pass
    result = choose(now, runs, jobs)
    print("MORNING_EARLY_RECOVERY", json.dumps(result, sort_keys=True))
    if result["action"] == "DISPATCH":
        # Deliberately one POST, no automatic retry on ambiguous API errors.
        # A subsequent independent trigger can re-evaluate actual run state.
        args = ["gh", "api", "--method", "POST",
                f"repos/{repo}/actions/workflows/{SCRIPT}/dispatches",
                "-f", "ref=main", "-f", "phase=" + result["phase"]]
        subprocess.run(args, check=True, timeout=35)
        print("MORNING_RECOVERY_DISPATCHED", result["phase"])
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
        f.write("## Independent early morning recovery\n")
        f.write("- Decision: **" + result["action"] + "**\n")
        if result.get("phase"):
            f.write("- Phase dispatched: **" + result["phase"] + "**\n")


if __name__ == "__main__":
    main()
