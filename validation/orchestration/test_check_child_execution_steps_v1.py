#!/usr/bin/env python3
"""Regression: required child work must execute even if workflow status is green."""
from __future__ import annotations

import json
from pathlib import Path

from check_child_execution_steps_v1 import inspect, REQUIRED_STEPS

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

try:
    inspect("unapproved-producer.yml", {"jobs": []})
except ValueError:
    pass
else:
    raise AssertionError("Unknown child workflows must fail closed")

print("ORCHESTRATED_CHILD_STEP_EVIDENCE_ALL_PHASES_PASS")
