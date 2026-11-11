#!/usr/bin/env python3
"""Persist Calendar/News changes only if the remote branch has not changed
any of our managed files. Rebase and retry on unrelated concurrent writes.

The immutable G8 macro ledgers must NEVER be silently overwritten, appended
twice or merged with unvalidated rows. On any remote overlap this fails
closed and preserves upstream data. No forced pushes, reset or auto-merge.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANAGED = (
    "live_data/sections/CALENDAR_OPERATIONAL_VIEW.json",
    "live_data/sections/MACRO_CONSENSUS_SECONDARY_V1.json",
    "live_data/sections/NEWS_PULSE_OPERATIONAL.json",
    "validation/macro/MACRO_PRE_RELEASE_CONSENSUS_LEDGER_V1.jsonl",
    "validation/macro/MACRO_EXACT_METRIC_FORECAST_FIRST_SEEN_V9.jsonl",
    "validation/macro/MACRO_BLS_CPI_EXACT_ACTUAL_FIRST_SEEN_V10.jsonl",
    "validation/macro/MACRO_UK_CH_GDP_OFFICIAL_FIRST_SEEN_V11.jsonl",
    "validation/macro/MACRO_OFFICIAL_ACTUAL_FIRST_SEEN_V1.jsonl",
    "validation/macro/MACRO_EVENT_PRE_RELEASE_MARKET_ANCHORS_V1.jsonl",
    "live_data/sections/NATIVE_CB_DATA.json",
    "live_data/manifest.v2.json",
    "payload/part-00.txt",
)
MAX_ATTEMPTS = 6


def git(repo: Path, *args: str, check=True):
    p = subprocess.run(
        ["git", *args], cwd=repo, text=True, encoding="utf-8",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if check and p.returncode:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({p.returncode}): {p.stderr.strip()}")
    return p


def changed_files(repo: Path, *args: str):
    r = git(repo, "diff", "--name-only", *args)
    return set(filter(None, r.stdout.splitlines()))


def persist(repo: Path = ROOT, *, managed=MANAGED, max_attempts=MAX_ATTEMPTS,\n            commit_message="Refresh official release ledgers and operational Calendar/News"):
    repo = Path(repo).resolve()
    managed = tuple(managed)
    if not managed or any(not x or x.startswith("/") or ".." in Path(x).parts
                          for x in managed) or len(managed) != len(set(managed)):
        raise ValueError("invalid managed-file contract")
    if max_attempts < 1 or max_attempts > 10:
        raise ValueError("invalid retry budget")
    if not isinstance(commit_message, str) or not commit_message.strip() or '\\n' in commit_message or '\\r' in commit_message:
        raise ValueError("invalid commit message")
    before = git(repo, "rev-parse", "HEAD").stdout.strip()
    dirty = changed_files(repo)
    if not dirty:
        return {"status": "NO_TRACKED_CHANGES", "attempts": 0}
    unexpected = dirty - set(managed)
    if unexpected:
        raise ValueError(f"UNEXPECTED_WORKTREE_CHANGE: {sorted(unexpected)}")
    # Existing workflow never commits untracked files; stay consistent.
    git(repo, "config", "user.name", "github-actions[bot]")
    git(repo, "config", "user.email",
        "41898282+github-actions[bot]@users.noreply.github.com")
    git(repo, "add", "--", *managed)
    if not git(repo, "diff", "--cached", "--quiet", check=False).returncode:
        return {"status": "NO_STAGED_CHANGE", "attempts": 0}
    git(repo, "commit", "-m", commit_message)
    for attempt in range(1, max_attempts + 1):
        push = git(repo, "push", "origin", "HEAD:main", check=False)
        if push.returncode == 0:
            return {"status": "PERSISTED", "attempts": attempt,
                    "commit": git(repo, "rev-parse", "HEAD").stdout.strip(),
                    "rebased_onto_latest_main": attempt > 1}
        git(repo, "fetch", "--no-tags", "origin",
            "+refs/heads/main:refs/remotes/origin/main")
        if git(repo, "merge-base", "--is-ancestor", before, "origin/main",
               check=False).returncode != 0:
            raise RuntimeError("REMOTE_MAIN_DIVERGED_FROM_CHECKOUT_NO_REWRITE")
        # A remote change only conflicts if it touches a file this runner
        # is writing. Other managed files can move safely without overwrite.
        overlap = changed_files(
            repo, before, "origin/main", "--", *sorted(dirty))
        if overlap:
            raise RuntimeError(
                "REMOTE_MANAGED_FILES_MOVED_FAIL_CLOSED: "
                + ", ".join(sorted(overlap)))
        latest = git(repo, "rev-parse", "origin/main").stdout.strip()
        if latest == before:
            raise RuntimeError(
                "GIT_PUSH_FAILED_WITHOUT_REMOTE_ADVANCE: "
                + push.stderr.strip()[:500])
        rebased = git(repo, "rebase", "origin/main", check=False)
        if rebased.returncode:
            git(repo, "rebase", "--abort", check=False)
            raise RuntimeError(
                "GIT_REBASE_FAILED_NO_REMOTE_OVERWRITE: "
                + rebased.stderr.strip()[:500])
    raise RuntimeError("MAIN_ADVANCED_REPEATEDLY_MAX_RETRIES_NO_FORCE_PUSH")


if __name__ == "__main__":
    print(json.dumps(persist(), ensure_ascii=False, sort_keys=True))
