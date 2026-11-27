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
        # A proven no-op skips the write-only branch comparison: requiring
        # that conditional step incorrectly marks a fully verified
        # publish-as-already-current workflow as failed. This guard is
        # unconditional for dispatches and validates main/gh-pages parity.
        "Refresh main and gh-pages to detect unchanged published content",
        "Block incomplete morning sources before any Pages write",
        # Mandatory EVEN after a no-op: exact public bytes, not just SHA
        # equality between branches. A mismatch keeps the child non-green.
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


# These jobs are explicitly restricted to pull_request events in the macro
# workflow. They must be skipped on the orchestrator's workflow_dispatch.
# A regression test checks this exact allowlist against the live workflow.
MACRO_PR_ONLY_JOBS = frozenset((
    "jpy-employment-lfs-source-proof",
    "jpy-new-loans-source-proof",
    "core-jpy-chf-canonical-proof",
    "chf-balance-yield-rates-source-proof",
    "chf-neer-daily-source-proof",
    "jpy-chf-stock-identity-proof",
    "gbp-paye-rti-source-proof",
    "aud-twi-source-proof",
    "gbp-dmp-monthly-source-proof",
    "gbp-mortgage-rate-source-proof",
    "cad-ceer-source-proof",
    "chf-snb-source-proof",
    "aud-abs-cpi-context-source-proof",
    "eur-ecb-daily-source-proof",
    "eur-ecb-bsi-monthly-source-proof",
    "gbp-boe-iadb-source-proof",
    "us-quarterly-cfnai-source-proof",
    "jpy-bis-neer-source-proof",
    "jpy-boj-assets-fred-source-proof",
    "chf-seco-index-source-proof",
    "eur-ecfin-bcs-monthly-source-proof",
    "eur-native-liquidity-parity-source-proof",
    "g8-native-liquidity-parity-source-proof",
    "aud-abs-activity-source-proof",
    "us-initial-claims-source-proof",
    "cad-boc-source-proof",
    "cad-boc-quarterly-source-proof",
    "cad-boc-lending-source-proof",
    "cad-retail-volume-source-proof",
    "nz-retail-volume-source-proof",
    "jpy-tankan-actual-source-proof",
    "jpy-boj-source-proof",
    "jpy-boj-base-source-proof",
    "aud-rba-source-proof",
    "cad-monthly-source-proof",
    "eur-gbp-source-proof",
    "us-market-source-proof",
    "us-monthly-source-proof",
    "eur-activity-source-proof",
))


def inspect(workflow: str, payload: dict) -> dict:
    if workflow not in REQUIRED_STEPS:
        raise ValueError(f"Unknown orchestrator child: {workflow}")
    expected = REQUIRED_STEPS[workflow]
    jobs = payload.get("jobs") if isinstance(payload, dict) else None
    problems: list[str] = []
    observed_steps: dict[str, list[dict]] = {}
    expected_pr_only_skips: list[str] = []
    if not isinstance(jobs, list) or not jobs:
        problems.append("NO_COMPLETED_CHILD_JOBS")
    else:
        for job in jobs:
            if not isinstance(job, dict):
                problems.append("MALFORMED_CHILD_JOB")
                continue
            name = str(job.get("name") or "unnamed")
            if (workflow == "macro-persistent-daily-v1.yml"
                    and name in MACRO_PR_ONLY_JOBS
                    and job.get("status") == "completed"
                    and job.get("conclusion") == "skipped"
                    and job.get("steps") in (None, [])):
                expected_pr_only_skips.append(name)
                continue
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
        "expected_pr_only_jobs_skipped": sorted(expected_pr_only_skips),
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
