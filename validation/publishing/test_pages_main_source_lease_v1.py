#!/usr/bin/env python3
"""Ensure every Pages gh-pages write is fenced by the exact checkout main SHA."""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[2]
workflow = (root / ".github/workflows/publish-dashboard-pages-v1.yml").read_text()
assert "queue: max" in workflow.split("concurrency:", 1)[1].split("jobs:", 1)[0], "PAGES_PENDING_RUN_REPLACEMENT_RISK"
begin = "      - name: Publish dashboard runtime and operational assets to gh-pages with lease"
end = "      - name: Ensure actual Pages build follows automated gh-pages push"
assert workflow.count(begin) == workflow.count(end) == 1
publisher = workflow.split(begin, 1)[1].split(end, 1)[0]

assert 'SOURCE_MAIN_SHA="$(git rev-parse HEAD)"' in publisher
assert 'observed_main="$(git ls-remote origin refs/heads/main | awk' in publisher
assert "PAGES_SOURCE_MAIN_MOVED" in publisher
assert 'Publish dashboard runtime from validated main ${SOURCE_MAIN_SHA}' in publisher
assert publisher.count("assert_source_main_current\n") == 3
assert publisher.index("SOURCE_MAIN_SHA=") < publisher.index("git fetch origin gh-pages")
assert publisher.index("assert_source_main_current\n") < publisher.index("git fetch origin gh-pages")
assert publisher.index("if git diff --cached --quiet") < publisher.index(
    "assert_source_main_current\n", publisher.index("if git diff --cached --quiet"))
assert publisher.rindex("assert_source_main_current\n") < publisher.index(
    "git push --force-with-lease=")
assert publisher.rindex("assert_source_main_current\n") > publisher.index(
    "git commit -m")

match = re.search(
    r"(?ms)^          assert_source_main_current\(\) \{\n(.*?)^          \}",
    publisher,
)
assert match, "Missing shell function"
function_source = "assert_source_main_current() {\n" + match.group(1) + "}"
test_shell = (
    function_source
    + "\n"
    + """git() {
  [[ "$1" == "ls-remote" && "$2" == "origin" && "$3" == "refs/heads/main" ]] || return 2
  printf '%s\\trefs/heads/main\\n' "${MOCK_MAIN_SHA:-}"
}
SOURCE_MAIN_SHA=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
assert_source_main_current
"""
)
subprocess.run(["bash", "-n"], input=test_shell, text=True, check=True)

for remote, should_pass in (
    ("a" * 40, True),
    ("b" * 40, False),
    ("", False),
):
    env = dict(os.environ, MOCK_MAIN_SHA=remote)
    result = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", test_shell],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert (result.returncode == 0) is should_pass, (remote, result.stdout, result.stderr)
    if not should_pass:
        assert "PAGES_SOURCE_MAIN_MOVED" in result.stderr, result.stderr

print("PAGES_MAIN_SOURCE_LEASE_CONTRACT_PASS")
