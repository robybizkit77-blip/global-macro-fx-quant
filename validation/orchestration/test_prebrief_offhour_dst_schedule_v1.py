#!/usr/bin/env python3
"""Guard the Rome schedule, phase routing and production queue."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/daily-data-orchestrator-v2.yml"

# The overnight phase follows a weekday session, so its local trigger falls
# Tuesday through Saturday after midnight.
SCHEDULES = {
    "43 4 * * 1-5": "prebrief",
    "45 7 * * 1-5": "premorning",
    "10 9 * * 1-5": "morning",
    "30 18 * * 1-5": "close",
    "50 0 * * 2-6": "night",
}


def check():
    text = WORKFLOW.read_text(encoding="utf-8")
    schedule = text.split("  schedule:\n", 1)[1].split("\npermissions:", 1)[0]
    entries = re.findall(r"^    - cron: '([^']+)'\n      timezone: '([^']+)'$", schedule, re.M)
    assert entries == [(cron, "Europe/Rome") for cron in SCHEDULES], entries
    assert schedule.count("- cron:") == len(SCHEDULES)

    resolver = text.split(
        "      - name: Resolve phase from the Rome schedule or manual input\n", 1
    )[1].split("      # EVERY active phase", 1)[0]
    script = dedent(resolver.split("        run: |\n", 1)[1])
    fixtures = [
        ("schedule", cron, "", phase) for cron, phase in SCHEDULES.items()
    ] + [
        ("workflow_dispatch", "", phase, phase)
        for phase in (*SCHEDULES.values(), "full")
    ] + [
        ("schedule", "43 2 * * 1-5", "", None),
        ("workflow_dispatch", "", "unknown", None),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "github_output"
        for event, cron, requested, expected in fixtures:
            output.write_text("")
            run = subprocess.run(
                ["bash", "-c", script],
                env={
                    **os.environ,
                    "EVENT_NAME": event,
                    "SCHEDULE": cron,
                    "REQUESTED_PHASE": requested,
                    "GITHUB_OUTPUT": str(output),
                },
                check=False,
                capture_output=True,
                text=True,
            )
            assert (run.returncode == 0) == (expected is not None), (event, cron, run.stderr)
            assert output.read_text() == (f"phase={expected}\n" if expected else "")

    # Only schedule/manual dispatch belong to the serialized production queue.
    queue = text.split("\nconcurrency:\n", 1)[1].split("\nenv:\n", 1)[0]
    assert "github.event_name == 'pull_request'" in queue
    assert "github.event.pull_request.number" in queue
    assert "github.event_name == 'push'" in queue
    assert "daily-data-orchestrator-v2-ci-pr-{0}" in queue
    assert "daily-data-orchestrator-v2-ci-push" in queue
    assert "|| 'daily-data-orchestrator-v2' }}" in queue
    assert "queue: max" in queue
    assert "cancel-in-progress: false" in queue
    assert ("if: ${{ github.event_name == 'schedule' || github.event_name == 'workflow_dispatch' }}"
            in text)
    print("ROME_SCHEDULES_AND_PHASE_RESOLUTION_PASS")


if __name__ == "__main__":
    check()
