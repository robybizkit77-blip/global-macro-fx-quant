#!/usr/bin/env python3
"""Report the morning phase deadline and the separate public Pages receipt."""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import urlencode
import zipfile
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
PHASES = {"prebrief", "premorning"}
TARGET = dt.time(hour=8, minute=0)
MORNING_WINDOW_END = dt.time(hour=10, minute=0)
PUBLISHER = "publish-dashboard-pages-v1.yml"
PROOF_NAME = "pages-delivery-proof"
PROOF_FILE = "pages-0800-delivery-sla.json"


def rome_time(value: object) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        stamp = dt.datetime.fromisoformat(value)
        return stamp.astimezone(ROME) if stamp.utcoffset() is not None else None
    except ValueError:
        return None


def confirmed_pages_receipt(run: dict, receipt: dict, now: dt.datetime) -> dict | None:
    local = now.astimezone(ROME)
    deadline = dt.datetime.combine(local.date(), TARGET, tzinfo=ROME)
    created = rome_time(run.get("created_at"))
    checked = rome_time(receipt.get("source_checked_at_rome"))
    verified = rome_time(receipt.get("public_verified_at_rome"))
    evaluated = rome_time(receipt.get("evaluated_at_rome"))
    count = receipt.get("verified_file_count")
    if not (
        type(run.get("id")) is int
        and run.get("path") == f".github/workflows/{PUBLISHER}"
        and run.get("head_branch") == "main"
        and run.get("event") in {"push", "workflow_run", "workflow_dispatch"}
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
        and local.weekday() < 5
        and created is not None and created.date() == local.date()
        and checked is not None and verified is not None and evaluated is not None
        and created <= checked <= verified <= min(deadline, evaluated)
        and evaluated <= local
        and rome_time(receipt.get("target_rome")) == deadline
        and receipt.get("schema") == "GMFQ_INDEPENDENT_PAGES_0800_SLA_V1"
        and receipt.get("scope") == "EXACT_PUBLIC_HTTP_FILES_AND_MORNING_SOURCE_GATE_ONLY"
        and receipt.get("status") == "PASS_PUBLIC_HTTP_BY_0800"
        and receipt.get("on_time_delivery_proven") is True
        and receipt.get("source_pass") is True
        and receipt.get("public_exact_bytes_pass") is True
        and type(count) is int and count > 0
    ):
        return None
    return {
        "status": "PASS_PUBLIC_HTTP_BY_0800",
        "publisher_run_id": run["id"],
        "public_verified_at_rome": verified.isoformat(timespec="seconds"),
        "verified_file_count": count,
    }


def github_api(path: str) -> bytes:
    return subprocess.check_output(["gh", "api", path], timeout=15)


def find_pages_receipt(repo: str, now: dt.datetime) -> dict:
    """Read same-day production artifacts, even if this phase ran much later."""
    local = now.astimezone(ROME)
    start = dt.datetime.combine(local.date(), dt.time(), tzinfo=ROME)
    deadline = dt.datetime.combine(local.date(), TARGET, tzinfo=ROME)
    lower, upper = (d.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    for d in (start, min(deadline, local)))
    query = urlencode({"branch": "main", "status": "success", "created": f"{lower}..{upper}",
                       "per_page": 100})
    base = f"repos/{repo}/actions"
    errors = (subprocess.SubprocessError, OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile)
    try:
        runs = json.loads(github_api(f"{base}/workflows/{PUBLISHER}/runs?{query}"))["workflow_runs"]
    except errors:
        return {"status": "PUBLISHER_EVIDENCE_LOOKUP_FAILED"}
    lookup_failed = False
    for run in runs:
        try:
            artifacts = json.loads(github_api(f"{base}/runs/{run['id']}/artifacts?name={PROOF_NAME}"))["artifacts"]
            for artifact in artifacts:
                if artifact.get("name") != PROOF_NAME or artifact.get("expired") is not False:
                    continue
                data = github_api(f"{base}/artifacts/{artifact['id']}/zip")
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    receipt = json.loads(archive.read(PROOF_FILE))
                if not isinstance(receipt, dict):
                    continue
                confirmed = confirmed_pages_receipt(run, receipt, now)
                if confirmed:
                    return confirmed
        except errors:
            lookup_failed = True
    return {"status": "PUBLISHER_EVIDENCE_LOOKUP_FAILED" if lookup_failed else "PUBLIC_BY_0800_UNPROVEN"}


def evaluate(phase: str, report: dict | None, now: dt.datetime, pages: dict | None = None) -> dict:
    if phase not in PHASES:
        raise ValueError(f"unsupported morning phase: {phase}")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    local = now.astimezone(ROME)
    deadline = dt.datetime.combine(local.date(), TARGET, tzinfo=ROME)
    weekday_delivery = local.weekday() < 5
    time_met = local <= deadline
    checked_local = rome_time(report.get("checked_at_rome")) if isinstance(report, dict) else None
    same_date_and_not_future = bool(
        checked_local is not None
        and checked_local.date() == local.date()
        and checked_local <= local
    )
    source_ok = bool(
        isinstance(report, dict)
        and report.get("schema") == "GMFQ_MORNING_READINESS_V1"
        and report.get("operational_state") == "DAILY_READY_WITH_DOCUMENTED_GAPS"
        and report.get("refresh_pipeline_outcome") == "success"
        and report.get("critical_daily_problems") == []
        and same_date_and_not_future
    )
    documented_gaps = (
        report.get("documented_nonblocking_gaps", [])
        if isinstance(report, dict) and isinstance(report.get("documented_nonblocking_gaps"), list)
        else []
    )
    if not weekday_delivery:
        status = "FAIL_OUTSIDE_WEEKDAY_DELIVERY_WINDOW"
    elif not source_ok:
        status = "FAIL_INCOMPLETE_OR_UNVERIFIED"
    elif not time_met:
        status = "PHASE_COMPLETED_AFTER_0800"
    else:
        status = "PASS_PHASE_COMPLETED_BY_0800"
    return {
        "schema": "GMFQ_MORNING_0800_DELIVERY_SLA_V1",
        "phase": phase,
        "target_timezone": "Europe/Rome",
        "target_rome": deadline.isoformat(timespec="seconds"),
        "evaluated_at_rome": local.isoformat(timespec="seconds"),
        "morning_source_checked_at_rome": checked_local.isoformat(timespec="seconds") if checked_local else None,
        "source_evidence_current_day": same_date_and_not_future,
        "source_and_publication_sequence_successful": source_ok,
        "weekday_delivery_window": weekday_delivery,
        "on_time": bool(source_ok and time_met and weekday_delivery),
        "pages_public_delivery": pages if pages is not None else {"status": "PUBLIC_BY_0800_UNPROVEN"},
        "documented_nonblocking_gaps": documented_gaps,
        "seconds_from_deadline": int((local - deadline).total_seconds()),
        "status": status,
        "data_policy": "READ_ONLY_NO_SOURCE_MUTATION",
        "note": "Phase timing tracks this orchestration. Pages delivery tracks the dashboard publisher's source gate and exact public HTTP files.",
    }


def late_scheduled_guard(phase: str, event: str, now: dt.datetime, repo: str | None) -> dict:
    """Skip only an expired scheduled morning attempt with independent on-time HTTP proof."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    local = now.astimezone(ROME)
    eligible = (event == "schedule" and phase in PHASES and local.weekday() < 5
                and local.time().replace(tzinfo=None) >= MORNING_WINDOW_END)
    pages = (find_pages_receipt(repo, now) if eligible and repo else
             {"status": "PUBLIC_BY_0800_UNPROVEN" if eligible else "NOT_APPLICABLE"})
    superseded = eligible and pages.get("status") == "PASS_PUBLIC_HTTP_BY_0800"
    return {
        "schema": "GMFQ_LATE_SCHEDULED_MORNING_GUARD_V1",
        "phase": phase, "event": event, "evaluated_at_rome": local.isoformat(timespec="seconds"),
        "target_rome": dt.datetime.combine(local.date(), TARGET, tzinfo=ROME).isoformat(timespec="seconds"),
        "morning_window_end_rome": MORNING_WINDOW_END.isoformat(timespec="minutes"),
        "status": ("PHASE_SUPERSEDED_AFTER_MORNING_WINDOW" if superseded else
                   "LATE_RECOVERY_REQUIRED_NO_ON_TIME_PROOF" if eligible else "NORMAL_PHASE"),
        "skip_obsolete_phase": superseded,
        "on_time": False if eligible else None,
        "pages_public_delivery": pages,
        "source_audit_performed": False,
        "new_acquisition_claimed": False,
        "new_publication_claimed": False,
        "data_policy": "READ_ONLY_NO_SOURCE_MUTATION",
        "note": ("Independent historical delivery is not current-data certification. "
                 "The late phase never claims its own on-time completion. "
                 "Without exact same-day on-time HTTP proof, retain existing recovery and all source gates."),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--phase", choices=sorted(PHASES), required=True)
    p.add_argument("--readiness")
    p.add_argument("--late-scheduled-guard", action="store_true")
    p.add_argument("--event", default="workflow_dispatch")
    p.add_argument("--output")
    p.add_argument("--as-of", help="ISO-8601 aware evaluation instant, deterministic testing only")
    args = p.parse_args()
    try:
        now = dt.datetime.fromisoformat(args.as_of) if args.as_of else dt.datetime.now(dt.timezone.utc)
        if now.utcoffset() is None:
            p.error("--as-of requires an explicit timezone")
    except ValueError:
        p.error("--as-of requires a valid ISO-8601 timestamp")
    if args.late_scheduled_guard:
        result = late_scheduled_guard(args.phase, args.event, now, os.getenv("GITHUB_REPOSITORY"))
        if args.output:
            Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\\n", encoding="utf-8")
        print("LATE_SCHEDULED_MORNING_GUARD", json.dumps(result, sort_keys=True))
        return 0
    if not args.readiness:
        p.error("--readiness is required outside late scheduled guard mode")
    try:
        path = Path(args.readiness)
        report = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    except (ValueError, OSError):
        report = None
    repo = os.getenv("GITHUB_REPOSITORY")
    pages = find_pages_receipt(repo, now) if repo else None
    result = evaluate(args.phase, report, now, pages)
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("MORNING_0800_SLA", json.dumps(result, sort_keys=True))
    return int(result["status"] != "PASS_PHASE_COMPLETED_BY_0800")


if __name__ == "__main__":
    raise SystemExit(main())
