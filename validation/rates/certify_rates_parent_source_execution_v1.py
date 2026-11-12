#!/usr/bin/env python3
"""Fail-closed proof that the *upstream* Rates workflow really collected sources.

A GitHub Actions green workflow is not proof: the schedule gate may skip ALL
source steps. Source-executed means the dated official-source audit and its
candidate validation actually finished. It does NOT certify fresher quotes.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

REQUIRED = (
    "Resolve Rates schedule from UTC cron and Rome offset",
    "Build official Rates candidate",
    "Verify current and candidate 2Y/10Y weekly reference dates before any live publication",
)
FINISHERS = (
    "Validate no-update identity",
    "Apply validated Rates candidate",
)


def certify(payload: object) -> dict:
    fail = lambda reason: {
        "schema": "GMFQ_FXV2_RATES_PARENT_SOURCE_EXECUTION_V1",
        "source_verified": False,
        "reason": reason,
        "new_market_observations_certified": False,
    }
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        return fail("JOBS_RESPONSE_NOT_VERIFIABLE")
    jobs = [x for x in payload["jobs"] if isinstance(x, dict)
            and x.get("name") == "persist-rates"]
    if len(jobs) != 1:
        return fail("PERSIST_RATES_JOB_MISSING_OR_AMBIGUOUS")
    job = jobs[0]
    if job.get("status") != "completed" or job.get("conclusion") != "success":
        return fail("PERSIST_RATES_JOB_NOT_SUCCESSFULLY_COMPLETED")
    steps = job.get("steps")
    if not isinstance(steps, list) or len(steps) < len(REQUIRED) + 1:
        return fail("RATES_STEPS_MISSING")
    status = {}
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get("name"), str):
            return fail("MALFORMED_RATES_STEP")
        name = step["name"]
        if name in status:
            return fail("DUPLICATED_RATES_STEP_NAME")
        status[name] = (step.get("status"), step.get("conclusion"))
    for name in REQUIRED:
        if status.get(name) != ("completed", "success"):
            return fail("SOURCE_STEP_NOT_EXECUTED_" + name.replace(" ", "_")[:65])
    if not any(status.get(name) == ("completed", "success") for name in FINISHERS):
        return fail("RATES_CANDIDATE_NOT_VALIDATED")
    return {
        "schema": "GMFQ_FXV2_RATES_PARENT_SOURCE_EXECUTION_V1",
        "source_verified": True,
        "reason": "UPSTREAM_RATES_SOURCE_AUDIT_ACTUALLY_EXECUTED",
        "new_market_observations_certified": False,
        "note": "Acquisition and validation were executed; freshness and changed observations are separate questions.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs-file", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--summary", type=Path)
    args = ap.parse_args()
    try:
        report = certify(json.loads(args.jobs_file.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError) as exc:
        report = certify(None)
        report["reason"] = "UNREADABLE_PARENT_JOBS_" + type(exc).__name__
    if args.output:
        with args.output.open("a", encoding="utf-8") as f:
            f.write("source_verified=" + str(report["source_verified"]).lower() + "\n")
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as f:
            f.write("- Parent Rates source-executed proof: **" +
                    ("VERIFIED" if report["source_verified"] else "NOT VERIFIED") +
                    "** (" + report["reason"] + "). No freshness claim.\n")
    print("FXV2_RATES_PARENT_SOURCE_CERTIFICATION", json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
