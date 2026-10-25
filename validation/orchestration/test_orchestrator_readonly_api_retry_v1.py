#!/usr/bin/env python3
"""Exercise bounded retries for GitHub read-only API response failures.

The workflow dispatch POST is intentionally never retried: ambiguous POST
failures cannot be distinguished from successful-but-unreported dispatches.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
workflow = (ROOT / ".github/workflows/daily-data-orchestrator-v2.yml").read_text()

post = 'dispatch_result=$(gh api --method POST'
run_get = 'if ! json=$(gh api "repos/${GITHUB_REPOSITORY}/actions/runs/${run_id}"); then'
jobs_get = 'if gh api "repos/${GITHUB_REPOSITORY}/actions/runs/${run_id}/jobs?per_page=100" > "$child_jobs_file"; then'
assert workflow.count(post) == 1, "POST should not be retried"
assert workflow.count(run_get) == 1
assert workflow.count(jobs_get) == 1
assert workflow.index(post) < workflow.index(run_get) < workflow.index(jobs_get)
get_block = workflow.split(run_get, 1)[1].split('status=$(jq', 1)[0]
assert "CHILD_RUN_API_TRANSIENT" in get_block
assert "sleep 10" in get_block and "continue" in get_block

begin = '                for attempt in 1 2 3 4 5; do'
stop = '                echo "CHILD_REQUIRED_STEPS_NOT_EXECUTED'
assert workflow.count(begin) == 1
assert workflow.count(stop) == 1
retry_block = workflow.split(begin, 1)[1].split(stop, 1)[0]
assert "rm -f" in retry_block
assert "CHILD_JOBS_API_TRANSIENT" in retry_block
assert "if gh api" in retry_block
assert "return 0" in retry_block
assert 'if [[ "$attempt" -lt 5 ]]; then sleep 3; fi' in retry_block

# Include the original production loop in Bash, rather than rewriting its
# logic in the tests. The mock first returns a nonzero HTTP status and a
# partial bogus body; then a valid job response.
loop = begin + retry_block
for failures, success in ((2, True), (5, False)):
    with tempfile.TemporaryDirectory() as tmp:
        jobs = Path(tmp) / "jobs.json"
        proof = Path(tmp) / "proof.json"
        count_path = Path(tmp) / "calls.txt"
        summary = Path(tmp) / "summary.txt"
        env = dict(os.environ,
                   GITHUB_REPOSITORY="robybizkit77-blip/global-macro-fx-quant",
                   GITHUB_STEP_SUMMARY=str(summary))
        valid = (
            '{"jobs":[{"name":"refresh","status":"completed",'
            '"conclusion":"success","steps":['
            '{"name":"Build operational Calendar and News Pulse",'
            '"status":"completed","conclusion":"success"},'
            '{"name":"Validate operational outputs",'
            '"status":"completed","conclusion":"success"}]}]}'
        )
        script = r"""set -euo pipefail
wf=calendar-news-operational-refresh-v1.yml
run_id=90001
child_jobs_file=__JOBS__
child_proof_file=__PROOF__
counter=0
gh() {
  counter=$((counter+1))
  printf '%s' "$counter" > __COUNT__
  if (( counter <= __FAILURES__ )); then
    printf '{broken-body}'
    return 22
  fi
  printf '%s' '__VALID__'
}
sleep() { :; }
test_loop() {
__LOOP__
  return 1
}
test_loop
"""
        script = (script.replace("__JOBS__",str(jobs))
                        .replace("__PROOF__",str(proof))
                        .replace("__COUNT__",str(count_path))
                        .replace("__FAILURES__",str(failures))
                        .replace("__VALID__",valid)
                        .replace("__LOOP__",loop))
        proc = subprocess.run(["bash", "-c", script], cwd=ROOT, env=env,
                              capture_output=True, text=True, check=False)
        assert (proc.returncode == 0) is success, (
            failures, proc.returncode, proc.stdout, proc.stderr)
        assert int(count_path.read_text()) == (3 if success else 5)
        if success:
            assert '"status": "PASS_EXECUTED"' in proof.read_text()
            assert "EXECUTED" in summary.read_text()
        else:
            # The last failed API call must not leave an apparently valid
            # jobs receipt from an earlier attempt.
            assert not jobs.exists()
            assert "CHILD_JOBS_API_TRANSIENT" in proc.stderr

print("ORCHESTRATOR_READONLY_API_RETRY_CONTRACT_PASS")
