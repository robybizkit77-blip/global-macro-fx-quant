"""Independent, read-only proof of the 08:00 Europe/Rome site delivery.

A green workflow or structural E2E gate is NOT evidence that fresh feeds reached
GitHub Pages by 08:00. Require actual production runs, completed morning SLA
steps, current dated sources, branch parity, and public HTTP byte parity.
This auditor has a different schedule and does not dispatch producers.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request
from zoneinfo import ZoneInfo

from validation.orchestration.check_morning_readiness_v1 import inspect, read_feeds

ROME = ZoneInfo("Europe/Rome")
WORKFLOW = "daily-data-orchestrator-v2.yml"
SITE = "https://robybizkit77-blip.github.io/global-macro-fx-quant/"
PATHS = (
    "site/fx-quant-v2/next/index.html",
    "site/control-room-preview/index.html",
    "live_data/sections/ECB_G8_PRICE_HISTORY.json",
    "live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json",
    "live_data/sections/NEWS_PULSE_OPERATIONAL.json",
    "live_data/sections/CALENDAR_OPERATIONAL_VIEW.json",
    "live_data/sections/D.json",
)
REQUIRED_STEPS = (
    "Run serialized refresh sequence",
    "Audit true source dates for the morning study",
    "Certify 08:00 morning delivery deadline",
    "Retain morning source readiness evidence",
)


def aware(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(ROME)


def schedule_applies(cron: str, now: dt.datetime) -> bool:
    """Dual UTC schedules: one 08:08 in CEST, one 08:08 in CET."""
    offset = int(now.astimezone(ROME).utcoffset().total_seconds() // 3600)
    return (cron, offset) in {
        ("08 6 * * 1-5", 2),
        ("08 7 * * 1-5", 1),
    }


def eligible(run: dict, jobs: list[dict], cutoff: dt.datetime) -> bool:
    try:
        start = aware(run["created_at"])
        if not (start.date() == cutoff.date() and start <= cutoff):
            return False
        if run.get("event") not in ("schedule", "workflow_dispatch") or run.get("head_branch") != "main":
            return False
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            return False
        for job in jobs:
            if job.get("name") != "orchestrate" or job.get("conclusion") != "success":
                continue
            if aware(job["completed_at"]) > cutoff:
                continue
            steps = {s.get("name"): s.get("conclusion") for s in job.get("steps", [])}
            if all(steps.get(name) == "success" for name in REQUIRED_STEPS):
                return True
        return False
    except (KeyError, ValueError, TypeError, AttributeError):
        return False


def evaluate(now: dt.datetime, runs: list[dict], jobs: dict[int, list[dict]],
             readiness: dict, parity: dict[str, bool], public: dict[str, bool]) -> dict:
    local = now.astimezone(ROME)
    cutoff = dt.datetime.combine(local.date(), dt.time(8, 0), tzinfo=ROME)
    problems = []
    today = []
    for run in runs:
        try:
            if run.get("event") in ("schedule", "workflow_dispatch") and aware(run["created_at"]).date() == local.date():
                today.append(run)
        except (KeyError, ValueError, TypeError):
            continue
    # GitHub's scheduled run can arrive hours late. Never count one that
    # only started or finished after the 08:00 deadline.
    early = [r for r in today if aware(r["created_at"]) <= cutoff]
    if local < cutoff:
        problems.append("AUDIT_BEFORE_0800_CANNOT_CERTIFY")
    # A fully completed prebrief OR verified 07:45 recovery is sufficient.
    # The original 07:45 cron can be absent when independently recovered,
    # but an actual on-time successful production + source proof is mandatory.
    ontime = [r for r in early if eligible(r, jobs.get(r.get("id"), []), cutoff)]
    if not ontime:
        problems.append("NO_COMPLETED_SUCCESSFUL_MORNING_SLA_BY_0800")
    if (readiness.get("operational_state") != "DAILY_READY_WITH_DOCUMENTED_GAPS"
            or readiness.get("critical_daily_problems") != []):
        problems.append("LATEST_MAIN_DAILY_SOURCES_NOT_READY")
    for path in PATHS:
        if parity.get(path) is not True:
            problems.append("MAIN_GH_PAGES_MISMATCH:" + path)
        if public.get(path) is not True:
            problems.append("PUBLIC_HTTP_MISMATCH:" + path)
    return {
        "schema": "GMFQ_INDEPENDENT_0800_AUDIT_V1",
        "checked_at_rome": local.isoformat(timespec="seconds"),
        "target_rome": cutoff.isoformat(timespec="seconds"),
        "status": "PASS_INDEPENDENT_0800_PROOF" if not problems else "FAIL_NOT_CERTIFIED",
        "problems": problems,
        "production_run_ids_today": [r.get("id") for r in today],
        "recovery_run_ids_today": [r.get("id") for r in today if r.get("event") == "workflow_dispatch"],
        "on_time_certified_run_ids": [r.get("id") for r in ontime],
        "source_expected_previous_weekday": readiness.get("expected_previous_weekday"),
        "source_problems": readiness.get("critical_daily_problems"),
        "public_paths_verified": [p for p in PATHS if parity.get(p) and public.get(p)],
        "limitations": ("This is an independent GitHub workflow, not an external scheduler. "
                        "Current HTTP parity cannot by itself prove the CDN was current at 08:00; "
                        "on-time proof comes from the completed production SLA job."),
    }


def get_json(path: str, token: str, repo: str) -> dict:
    url = "https://api.github.com/repos/" + repo + path
    request = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "User-Agent": "gmfq-independent-0800-audit-v1",
    })
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def git_bytes(ref: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", ref + ":" + path], timeout=20)


def read_public(path: str, today: dt.date) -> bytes:
    request = urllib.request.Request(
        SITE + path + "?independent_audit=" + today.isoformat(),
        headers={"Cache-Control": "no-cache",
                 "User-Agent": "GMFQ-Independent-Morning-Audit/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise ValueError("HTTP status " + str(response.status))
        return response.read()


def live(now: dt.datetime, token: str, repo: str) -> dict:
    # Every external failure is a hard audit failure, never a green fallback.
    failures = []
    runs, jobs, parity, public = [], {}, {}, {}
    try:
        obj = get_json("/actions/workflows/" + WORKFLOW +
                       "/runs?per_page=100", token, repo)
        runs = obj.get("workflow_runs", [])
        if not isinstance(runs, list):
            raise ValueError("missing workflow runs list")
        for run in runs:
            if (run.get("event") in ("schedule", "workflow_dispatch") and
                    aware(run["created_at"]).date() == now.astimezone(ROME).date()):
                jobs[run["id"]] = get_json(
                    "/actions/runs/" + str(run["id"]) + "/jobs?per_page=100",
                    token, repo).get("jobs", [])
    except Exception as ex:
        failures.append("GITHUB_PRODUCTION_RUN_EVIDENCE_UNAVAILABLE:" + str(ex)[:140])
    try:
        readiness = inspect(read_feeds(), now, pipeline_outcome="success")
    except Exception as ex:
        readiness = {}
        failures.append("SOURCE_READINESS_UNAVAILABLE:" + str(ex)[:140])
    for path in PATHS:
        try:
            main = git_bytes("origin/main", path)
            pages = git_bytes("origin/gh-pages", path)
            parity[path] = hashlib.sha256(main).digest() == hashlib.sha256(pages).digest()
            public[path] = hashlib.sha256(read_public(path, now.astimezone(ROME).date())).digest() == hashlib.sha256(pages).digest()
        except Exception as ex:
            parity[path] = False
            public[path] = False
            failures.append("PUBLIC_FETCH_ERROR:" + path + ":" + str(ex)[:120])
    result = evaluate(now, runs, jobs, readiness, parity, public)
    if failures:
        result["problems"].extend(failures)
        result["status"] = "FAIL_NOT_CERTIFIED"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--schedule", default="")
    args = parser.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    if args.schedule and not schedule_applies(args.schedule, now):
        result = {"schema": "GMFQ_INDEPENDENT_0800_AUDIT_V1",
                  "status": "SKIPPED_DST_COUNTERPART_NO_CERTIFICATION",
                  "checked_at_rome": now.astimezone(ROME).isoformat(timespec="seconds"),
                  "problems": [], "on_time_certified_run_ids": []}
    else:
        result = live(now, os.environ["GITHUB_TOKEN"], os.environ["GITHUB_REPOSITORY"])
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
    print("INDEPENDENT_0800_AUDIT", json.dumps(result, ensure_ascii=False))
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as out:
            out.write("## Independent 08:00 delivery audit\n")
            out.write("- Status: **" + result["status"] + "**\n")
            out.write("- Checked: " + result.get("checked_at_rome", "") + "\n")
            out.write("- True on-time runs: " + str(result["on_time_certified_run_ids"]) + "\n")
            out.write("- Blockers: " + ", ".join(result["problems"] or ["none"]) + "\n")
    return 0 if result["status"] in ("PASS_INDEPENDENT_0800_PROOF",
                                    "SKIPPED_DST_COUNTERPART_NO_CERTIFICATION") else 1


if __name__ == "__main__":
    raise SystemExit(main())
