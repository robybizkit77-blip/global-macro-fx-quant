#!/usr/bin/env python3
"""Read-only CB Pricing fallback gate: no extra cron, no blind dispatch.

Existing independent workflow_run events can execute CB Pricing only after the
Rome morning retries, and only if no completed *substantive* CB producer has
succeeded today. API failures raise and NEVER silently approve a duplicate.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
WORKFLOW_FILE = "cb-pricing-persistent-daily-v1.yml"
ELIGIBLE_EVENTS = frozenset(("schedule", "workflow_dispatch", "workflow_run"))
REQUIRED_STEPS = frozenset((
    "Run per-currency certified dry-run preflight",
    "Apply independently certified source candidates only",
))
START_TIME = dt.time(7, 23)
END_TIME = dt.time(10, 30)


def parse_utc(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def substantive_success(jobs: list[dict]) -> bool:
    for job in jobs:
        if job.get("name") != "persist-cb-pricing" or job.get("conclusion") != "success":
            continue
        successful_steps = {
            step.get("name") for step in job.get("steps", [])
            if step.get("conclusion") == "success"
        }
        if REQUIRED_STEPS <= successful_steps:
            return True
    return False


def decide(
    now: dt.datetime,
    runs: list[dict],
    jobs_for_run,
    current_run_id: int,
) -> dict:
    if now.tzinfo is None:
        raise ValueError("AWARE_TIMESTAMP_REQUIRED")
    rome = now.astimezone(ROME)
    local_date = rome.date()
    result = {
        "rome_checked_at": rome.isoformat(),
        "local_date": local_date.isoformat(),
        "eligible_window": False,
        "scheduled_runs_today": 0,
        "qualified_success_runs_today": [],
        "status": "SKIP",
        "reason": "",
    }
    if rome.weekday() >= 5:
        result["reason"] = "ROME_WEEKEND"
        return result
    if not (START_TIME <= rome.time().replace(tzinfo=None) < END_TIME):
        result["reason"] = "OUTSIDE_ROME_RECOVERY_WINDOW"
        return result
    result["eligible_window"] = True
    candidates = []
    for run in runs:
        if run.get("head_branch") != "main" or run.get("event") not in ELIGIBLE_EVENTS:
            continue
        run_id = run.get("id")
        if not isinstance(run_id, int) or run_id == current_run_id:
            continue
        stamp = run.get("run_started_at") or run.get("created_at")
        if not stamp:
            raise ValueError("RUN_TIMESTAMP_MISSING")
        started = parse_utc(stamp).astimezone(ROME)
        if started.date() != local_date or started.time() < dt.time(5, 45):
            continue
        if run["event"] == "schedule":
            result["scheduled_runs_today"] += 1
        candidates.append(run)

    # A run currently executing is serialized with this job by concurrency,
    # so only a *verified successful* earlier producer prevents recovery.
    for run in candidates:
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            continue
        if substantive_success(jobs_for_run(run["id"])):
            result["qualified_success_runs_today"].append(run["id"])
    if result["qualified_success_runs_today"]:
        result["reason"] = "ALREADY_PRODUCED_TODAY"
    else:
        result["status"] = "RUN"
        result["reason"] = (
            "NO_SCHEDULE_DELIVERED_RECOVER" if result["scheduled_runs_today"] == 0
            else "NO_SUCCESSFUL_PRODUCER_RECOVER"
        )
    return result


def github_get(repo: str, api_path: str) -> dict:
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise ValueError("GH_TOKEN_MISSING_READ_ONLY_FAIL_CLOSED")
    if not repo or "/" not in repo or not api_path.startswith("/"):
        raise ValueError("GITHUB_API_PATH_INVALID")
    url = f"https://api.github.com/repos/{repo}{api_path}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "gmfq-cb-pricing-recovery-gate",
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                return json.load(response)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            # Never approve recovery when GitHub cannot prove prior attempts.
            if attempt == 2 or (isinstance(exc, urllib.error.HTTPError) and exc.code not in (429, 500, 502, 503, 504)):
                raise
            time.sleep(attempt + 1)
    raise RuntimeError("UNREACHABLE")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--current-run-id", required=True, type=int)
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()
    run_data = github_get(args.repo, f"/actions/workflows/{WORKFLOW_FILE}/runs?per_page=100")
    if not isinstance(run_data.get("workflow_runs"), list):
        raise ValueError("GITHUB_RUN_HISTORY_INVALID")

    def get_jobs(run_id: int) -> list[dict]:
        payload = github_get(args.repo, f"/actions/runs/{run_id}/jobs?per_page=100")
        if not isinstance(payload.get("jobs"), list):
            raise ValueError("GITHUB_JOBS_HISTORY_INVALID")
        return payload["jobs"]

    receipt = decide(dt.datetime.now(dt.timezone.utc), run_data["workflow_runs"], get_jobs, args.current_run_id)
    with Path(args.output).open("a", encoding="utf-8") as out:
        out.write("should_run=" + ("true" if receipt["status"] == "RUN" else "false") + "\n")
        out.write("gate_reason=" + receipt["reason"] + "\n")
    with Path(args.summary).open("a", encoding="utf-8") as out:
        out.write("### CB Pricing missed-cron recovery\n\n")
        out.write("**" + receipt["status"] + "**: " + receipt["reason"] + "\n\n")
        out.write("Successful substantive earlier producers: " + str(receipt["qualified_success_runs_today"]) + "\n")
    print("CB_PRICING_RECOVERY_RECEIPT", json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
