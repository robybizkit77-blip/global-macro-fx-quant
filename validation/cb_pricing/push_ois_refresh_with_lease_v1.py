#!/usr/bin/env python3
"""Safely persist an already validated OIS refresh despite unrelated main commits.

Only rebases on remote commits that did not change any OIS source, logic, or
persistent OIS artifact. Never force-pushes or replaces concurrently updated OIS.
Each non-fast-forward retry fetches and checks the protected dependency set.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ESTIMATED_PATHS = (
    "live_data/sections/CB_PRICING_ESTIMATED_LIVE_QUOTES.json",
    "live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json",
    "live_data/sections/CB_PRICING_ESTIMATED.json",
    "live_data/sections/OIS_OPERATIONAL_VIEW.json",
    # Publishing the operational view without its matching pending-source
    # dossier can leave Home and Rates contradictory until the next G8 job.
    # Both writers share the existing exclusive concurrency group and lease.
    "live_data/sections/OIS_SOURCE_READINESS_VIEW.json",
    "validation/cb_pricing/history/OIS_ESTIMATED_SNAPSHOTS_V1.jsonl",
    "validation/cb_pricing/history/OIS_SAME_CONTRACT_QUOTES_V1.jsonl",
    "validation/cb_pricing/history/OIS_SAME_CONTRACT_CONFLICTS_V1.jsonl",
)
G8_PATHS = ESTIMATED_PATHS + (
    "validation/cb_pricing/history/OIS_G8_SNAPSHOTS_V1.jsonl",
)
# Changing any of these upstream invalidates the observations or the producer
# contract. They require a NEW refresh rather than a blind rebase.
PROTECTED = (
    "validation/cb_pricing",
    "live_data/sections/OIS_DATA.json",
    "live_data/sections/NATIVE_CB_DATA.json",
    "live_data/sections/CB_PRICING_ESTIMATED_LIVE_QUOTES.json",
    "live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json",
    "live_data/sections/CB_PRICING_ESTIMATED.json",
    "live_data/sections/OIS_OPERATIONAL_VIEW.json",
    "live_data/sections/OIS_SOURCE_READINESS_VIEW.json",
    ".github/workflows/ois-estimated-snapshot-repricing-v1.yml",
    ".github/workflows/ois-g8-history-persistent-daily-v1.yml",
)
COMMITS = {
    "estimated": "Refresh live estimated OIS operational repricing history",
    "g8": "Persist daily G8 OIS curve history",
}


class LeaseError(RuntimeError):
    pass


def git(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True)
    if check and result.returncode != 0:
        raise LeaseError(f"git {args[0]} failed: {result.stderr[-900:]}")
    return result


def persist(base_sha: str, mode: str, *, cwd: Path | None = None, attempts: int = 4) -> dict:
    if mode not in COMMITS:
        raise LeaseError("Invalid writer mode")
    if attempts < 1 or attempts > 6:
        raise LeaseError("Invalid bounded retry count")
    paths = ESTIMATED_PATHS if mode == "estimated" else G8_PATHS
    base_actual = git("rev-parse", "HEAD", cwd=cwd).stdout.strip()
    if base_actual != base_sha:
        raise LeaseError("Original checkout HEAD differs from captured BASE_SHA")
    unstaged = git("diff", "--name-only", cwd=cwd).stdout.splitlines()
    staged = git("diff", "--cached", "--name-only", cwd=cwd).stdout.splitlines()
    if not set(unstaged + staged).issubset(paths):
        raise LeaseError("REFUSED_OUT_OF_SCOPE: " + json.dumps(sorted(set(unstaged + staged) - set(paths))))
    git("add", "--", *paths, cwd=cwd)
    pending = git("diff", "--cached", "--quiet", cwd=cwd, check=False)
    if pending.returncode == 0:
        return {"status": "NO_CHANGE", "mode": mode, "attempts": 0}
    if pending.returncode != 1:
        raise LeaseError("Could not inspect staged OIS changes")
    git("-c", "user.name=github-actions[bot]",
        "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
        "commit", "-m", COMMITS[mode], cwd=cwd)
    anchor = base_sha
    for attempt in range(1, attempts + 1):
        git("fetch", "--no-tags", "origin", "+refs/heads/main:refs/remotes/origin/main", cwd=cwd)
        remote = git("rev-parse", "refs/remotes/origin/main", cwd=cwd).stdout.strip()
        ancestor = git("merge-base", "--is-ancestor", base_sha, remote, cwd=cwd, check=False)
        if ancestor.returncode != 0:
            raise LeaseError("REFUSED_HISTORY_DIVERGENCE: original main not ancestor")
        changed = git("diff", "--quiet", base_sha, remote, "--", *PROTECTED, cwd=cwd, check=False)
        if changed.returncode != 0:
            if changed.returncode == 1:
                raise LeaseError("REFUSED_PROTECTED_OIS_CHANGE: recompute refresh from latest main")
            raise LeaseError("Could not compare protected inputs on main")
        if anchor != remote:
            # A hosted runner may not have a repository identity. The initial
            # commit already supplies a scoped identity; the rebase rewrite must
            # do the same when unrelated main changes require replay.
            git("-c", "user.name=github-actions[bot]",
                "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                "rebase", "--onto", remote, anchor, cwd=cwd)
            anchor = remote
        pushed = git("push", "origin", "HEAD:refs/heads/main", cwd=cwd, check=False)
        if pushed.returncode == 0:
            return {
                "status": "PUSHED",
                "mode": mode,
                "attempts": attempt,
                "unrelated_main_advance": remote != base_sha,
                "commit": git("rev-parse", "HEAD", cwd=cwd).stdout.strip(),
            }
        if attempt == attempts:
            raise LeaseError("REFUSED_PUSH_RETRY_LIMIT: " + pushed.stderr[-600:])
    raise LeaseError("unreachable")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--mode", choices=sorted(COMMITS), required=True)
    parser.add_argument("--attempts", type=int, default=4)
    args = parser.parse_args()
    try:
        result = persist(args.base_sha, args.mode, attempts=args.attempts)
        print(json.dumps(result, sort_keys=True))
        return 0
    except LeaseError as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
