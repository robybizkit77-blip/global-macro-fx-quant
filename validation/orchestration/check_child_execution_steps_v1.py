#!/usr/bin/env python3
"""Prevent green orchestration receipts from masking skipped core child steps.

An actual no-change candidate is legitimate when its acquisition/validation
step completed successfully. A skipped acquisition (schedule gate, event
condition, job skip) is NOT a successful daily refresh. Read-only job audit.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# Workflow filenames are the existing, approved orchestrator child workflows.
# Keep requirements limited to steps that MUST run even for no-change updates.
REQUIRED_STEPS: dict[str, tuple[str, ...]] = {
    "macro-persistent-daily-v1.yml": (
        "Fetch and PIT-verify all 16 core series independently",
    ),
    "rates-persistent-daily-v1.yml": (
        "Build official Rates candidate",
    ),
    "cb-pricing-persistent-daily-v1.yml": (
        "Run per-currency certified dry-run preflight",
        "Enforce semantic and tracked scope",
    ),
    "ois-estimated-snapshot-repricing-v1.yml": (
        "Collect live secondary USD EUR CHF curves",
        "Self-test and governance checks",
    ),
    "calendar-news-operational-refresh-v1.yml": (
        "Build operational Calendar and News Pulse",
        "Validate operational outputs",
    ),
    "vix-persistent-apply-v1.yml": (
        "Fetch official Cboe candidate and build replacement",
    ),
    "final-e2e-certification-gate-v3.yml": (
        "Run final system alignment gate V3",
        "Verify receipt and official zero-mutation",
    ),
    "publish-dashboard-pages-v1.yml": (
        "Block incomplete morning sources before any Pages write",
        "Verify published files against validated main",
        "Verify public Pages HTTP delivery after bounded CDN propagation",
    ),
    "liquidity-jpy-m3-persistent-daily-v1.yml": (
        "Fetch official revision-aware BOJ candidate",
    ),
    "chf-residual-proxy-refresh-v1.yml": (
        "Refresh CHF official residual proxies",
        "Validate governance and proxy semantics",
    ),
    "jpy-reserve-balances-proxy-refresh-v1.yml": (
        "Refresh JPY reserve-balances official proxy",
        "Validate governance and continuity anchors",
    ),
    "price-persistent-daily-v1.yml": (
        "Fetch and validate official ECB Price candidate",
    ),
    "wti-persistent-rebuild-v1.yml": (
        "Fetch official EIA candidate and build replacement",
    ),
    "brent-market-proxy-refresh-v1.yml": (
        "Refresh Brent secondary market proxy",
        "Validate governance and output",
    ),
}


def inspect(workflow: str, payload: dict) -> dict:
    if workflow not in REQUIRED_STEPS:
        raise ValueError(f"Unknown orchestrator child: {workflow}")
    expected = REQUIRED_STEPS[workflow]
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    problems: list[str] = []
    observed_steps: dict[str, list[dict]] = {}
    if not isinstance(jobs, list) or not jobs:
        problems.append("NO_COMPLETED_CHILD_JOBS")
    else:
        for job in jobs:
            if not isinstance(job, dict):
                problems.append("MALFORMED_CHILD_JOB")
                continue
            name = str(job.get("name") or "unnamed")
            if job.get("status") != "completed" or job.get("conclusion") != "success":
                problems.append(f"CHILD_JOB_NOT_SUCCESS:{name}:{job.get('conclusion')}")
            steps = job.get("steps")
            if isinstance(steps, list):
                for step in steps:
                    if isinstance(step, dict) and isinstance(step.get("name"), str):
                        observed_steps.setdefault(step["name"], []).append(
                            {"job": name, "status": step.get("status"), "conclusion": step.get("conclusion")}
                        )
            else:
                problems.append(f"CHILD_JOB_NO_STEPS:{name}")
    proof = {}
    for step in expected:
        observed = observed_steps.get(step, [])
        if not observed:
            problems.append("REQUIRED_STEP_MISSING:" + step)
        elif len(observed) != 1 or observed[0]["conclusion"] != "success" or observed[0]["status"] != "completed":
            problems.append("REQUIRED_STEP_NOT_EXECUTED:" + step)
        proof[step] = observed
    return {
        "schema": "GMFQ_CHILD_RUN_STEPS_V1",
        "workflow": workflow,
        "status": "PASS_EXECUTED" if not problems else "FAIL_SKIPPED_OR_INCOMPLETE",
        "required_steps": list(expected),
        "step_evidence": proof,
        "problems": problems,
        "meaning": "A no-change producer can PASS only after its essential acquire/validate steps ran.",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--workflow", choices=sorted(REQUIRED_STEPS), required=True)
    p.add_argument("--jobs-file", type=Path, required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    try:
        data = json.loads(args.jobs_file.read_text(encoding="utf-8"))
        report = inspect(args.workflow, data)
    except (OSError, ValueError, TypeError) as exc:
        report = {
            "schema": "GMFQ_CHILD_RUN_STEPS_V1",
            "workflow": args.workflow,
            "status": "FAIL_SKIPPED_OR_INCOMPLETE",
            "problems": [f"JOBS_RECEIPT_INVALID:{type(exc).__name__}"],
        }
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("CHILD_RUN_STEP_PROOF", json.dumps(report, sort_keys=True, ensure_ascii=False))
    return int(report["status"] != "PASS_EXECUTED")


if __name__ == "__main__":
    raise SystemExit(main())
