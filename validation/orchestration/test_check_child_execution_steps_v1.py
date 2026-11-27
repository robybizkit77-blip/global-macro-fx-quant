#!/usr/bin/env python3
"""Regression: required child work must execute even if workflow status is green."""
from __future__ import annotations

import json
import re
from pathlib import Path

from check_child_execution_steps_v1 import inspect, REQUIRED_STEPS, MACRO_PR_ONLY_JOBS

root = Path(__file__).resolve().parents[2]
orchestrator = json.loads((root / "validation/orchestration/DAILY_DATA_ORCHESTRATOR_V2_2026-10-15.json").read_text())
children = {c for phase in orchestrator["phases"].values() for c in phase}
assert children == set(REQUIRED_STEPS), (children - set(REQUIRED_STEPS), set(REQUIRED_STEPS) - children)

# Ensure the required step labels actually exist in the named live child files.
for workflow, names in REQUIRED_STEPS.items():
    w = (root / ".github/workflows" / workflow).read_text(encoding="utf-8")
    for name in names:
        assert "      - name: " + name in w, (workflow, name)
    executed = {
        "total_count": 1,
        "jobs": [{
            "name": "actual-worker",
            "status": "completed",
            "conclusion": "success",
            "steps": [
                {"name": name, "status": "completed", "conclusion": "success"}
                for name in names
            ],
        }],
    }
    good = inspect(workflow, executed)
    assert good["status"] == "PASS_EXECUTED", good
    assert len(good["required_steps"]) == len(names)
    # Deliberately no new market observations: no-op is legitimate when the
    # collector really ran and verified its source.
    for status in ("skipped", "cancelled", "failure", None):
        skipped = json.loads(json.dumps(executed))
        skipped["jobs"][0]["steps"][0]["conclusion"] = status
        bad = inspect(workflow, skipped)
        assert bad["status"] == "FAIL_SKIPPED_OR_INCOMPLETE", (workflow, bad)
        assert any("REQUIRED_STEP_NOT_EXECUTED:" in x for x in bad["problems"])
    missing = json.loads(json.dumps(executed))
    missing["jobs"][0]["steps"] = []
    assert "REQUIRED_STEP_MISSING:" + names[0] in inspect(workflow, missing)["problems"]
    # A skipped job has a green-ish workflow UI on GitHub; never approve it.
    skipped_job = json.loads(json.dumps(executed))
    skipped_job["jobs"][0]["conclusion"] = "skipped"
    assert inspect(workflow, skipped_job)["status"] == "FAIL_SKIPPED_OR_INCOMPLETE"
    assert inspect(workflow, {"jobs": []})["status"] == "FAIL_SKIPPED_OR_INCOMPLETE"
    # Multiple or duplicated required steps must not magically validate each other.
    duplicate = json.loads(json.dumps(executed))
    duplicate["jobs"][0]["steps"].append(duplicate["jobs"][0]["steps"][0])
    assert inspect(workflow, duplicate)["status"] == "FAIL_SKIPPED_OR_INCOMPLETE"


# Reproduce the production Macro job list: historical PR-only proofs are
# intentionally skipped on every non-PR run. Never relax the real worker.
macro = "macro-persistent-daily-v1.yml"
macro_yaml = (root / ".github/workflows" / macro).read_text(encoding="utf-8")
job_blocks = re.split(r"(?m)^  ([a-z0-9-]+):\n", macro_yaml.split("\njobs:\n", 1)[1])
pr_only = {
    name for name, block in zip(job_blocks[1::2], job_blocks[2::2])
    if re.search(r"(?m)^    if: github\.event_name == 'pull_request' && ", block)
    and not re.search(r"(?m)^    name:", block)
}
assert pr_only == MACRO_PR_ONLY_JOBS, (pr_only - MACRO_PR_ONLY_JOBS, MACRO_PR_ONLY_JOBS - pr_only)
macro_worker = {
    "name": "persist-macro", "status": "completed", "conclusion": "success",
    "steps": [{"name": n, "status": "completed", "conclusion": "success"}
              for n in REQUIRED_STEPS[macro]],
}
expected_skips = [{"name": n, "status": "completed", "conclusion": "skipped", "steps": None}
                  for n in sorted(pr_only)]
macro_proof = inspect(macro, {"jobs": [macro_worker, *expected_skips]})
assert macro_proof["status"] == "PASS_EXECUTED", macro_proof
assert set(macro_proof["expected_pr_only_jobs_skipped"]) == pr_only
assert inspect(macro, {"jobs": expected_skips})["status"] == "FAIL_SKIPPED_OR_INCOMPLETE"
for unexpected in (
    {"name": "unexpected-production-job", "status": "completed", "conclusion": "skipped", "steps": None},
    dict(expected_skips[0], conclusion="failure"),
    dict(expected_skips[0], steps=macro_worker["steps"]),
    dict(expected_skips[0], status="in_progress"),
):
    assert inspect(macro, {"jobs": [macro_worker, unexpected]})["status"] == "FAIL_SKIPPED_OR_INCOMPLETE"
assert inspect(macro, {"jobs": [dict(macro_worker, conclusion="skipped"), *expected_skips]})["status"] == "FAIL_SKIPPED_OR_INCOMPLETE"
print("MACRO_PR_ONLY_EXPECTED_SKIP_PROOF_PASS", len(pr_only))

# Actual 12 Nov night incident: GitHub successfully verified a mirror no-op
# and exact public HTTP bytes (43/43), but the write-only branch check was
# intentionally skipped. That is NOT a failed child execution. Conversely,
# an HTTP skipped/failure is never accepted merely because branches match.
pages="publish-dashboard-pages-v1.yml"
required=REQUIRED_STEPS[pages]
assert "Refresh main and gh-pages to detect unchanged published content" in required
assert "Verify published files against validated main" not in required
noop={
 "jobs":[{
  "name":"publish-pages","status":"completed","conclusion":"success",
  "steps":[
   {"name":name,"status":"completed","conclusion":"success"}
   for name in required
  ]+[
   {"name":"Verify published files against validated main",
    "status":"completed","conclusion":"skipped"},
   {"name":"Publish dashboard runtime and operational assets to gh-pages with lease",
    "status":"completed","conclusion":"skipped"},
  ]
 }]
}
assert inspect(pages,noop)["status"]=="PASS_EXECUTED", "Verified already-current pages must not cause false orchestrator failure"
for critical in required:
 broken=json.loads(json.dumps(noop))
 step=next(x for x in broken["jobs"][0]["steps"] if x["name"]==critical)
 step["conclusion"]="skipped"
 finding=inspect(pages,broken)
 assert finding["status"]=="FAIL_SKIPPED_OR_INCOMPLETE", (critical,finding)
 assert "REQUIRED_STEP_NOT_EXECUTED:"+critical in finding["problems"]

try:
    inspect("unapproved-producer.yml", {"jobs": []})
except ValueError:
    pass
else:
    raise AssertionError("Unknown child workflows must fail closed")

print("ORCHESTRATED_CHILD_STEP_EVIDENCE_ALL_PHASES_PASS")
