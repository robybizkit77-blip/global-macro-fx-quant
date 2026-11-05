#!/usr/bin/env python3
"""Publish validated G8 Rates on main without overwriting concurrent writers.

The candidate and its source checks have already succeeded.  A moving main
branch is retryable ONLY when newer commits touch no Rates-owned file.
Never force-push and never promote a stale Rates candidate over new Rates data.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

RATES_OWNED = frozenset({
    "live_data/sections/NATIVE_RATES_DATA.json",
    "live_data/sections/RATES_AUDIT_METADATA.json",
    "live_data/manifest.v2.json",
    "payload/part-00.txt",
    "payload/part-15.txt",
})
SCOPES = {
    "rates": RATES_OWNED,
    "metadata": frozenset({
        "live_data/sections/RATES_AUDIT_METADATA.json",
        "live_data/manifest.v2.json",
        "payload/part-15.txt",
    }),
}
SHA = re.compile(r"^[0-9a-f]{40}$")


def run(args: list[str], *, cwd: str | Path = ".", check: bool = True):
    return subprocess.run(
        args, cwd=cwd, text=True, capture_output=True, check=check
    )


def git(*args: str, cwd: str | Path = ".") -> str:
    return run(["git", *args], cwd=cwd).stdout.strip()


def inspect_new_main_files(changed: set[str]) -> None:
    """Do not rebase over a new canonical/metadata/runtime writer."""
    overlap = changed & RATES_OWNED
    if overlap:
        raise RuntimeError(
            "RATES_CONCURRENT_SOURCE_CHANGED_FAIL_CLOSED: "
            + ", ".join(sorted(overlap))
        )


def verify_local_scope(changed: set[str], mode: str) -> None:
    if not changed or not changed <= SCOPES[mode]:
        raise RuntimeError(
            "RATES_PUBLISH_SCOPE_VIOLATION: " + repr(sorted(changed))
        )
    if mode == "rates" and "live_data/sections/NATIVE_RATES_DATA.json" not in changed:
        raise RuntimeError("RATES_CANONICAL_CHANGE_MISSING")


def validate_rebased_runtime(cwd: str | Path) -> None:
    """A safe replay must still satisfy the *current* published contract."""
    for script in (
        "validation/check_live_update_contract.py",
        "validation/rebuild_live_data_runtime.py",
    ):
        cmd = [sys.executable, script]
        if script.endswith("rebuild_live_data_runtime.py"):
            cmd.append("--verify-only")
        result = run(cmd, cwd=cwd)
        data = json.loads(result.stdout)
        if data.get("status") != "PASS":
            raise RuntimeError("RATES_REBASED_RUNTIME_NOT_VALID: " + script)
        if script.endswith("rebuild_live_data_runtime.py") and (
            data.get("noop_roundtrip_byte_identical") is not True
        ):
            raise RuntimeError("RATES_REBASED_RUNTIME_ROUNDTRIP_FAILED")


def publish(
    *, base_sha: str, mode: str, cwd: str | Path = ".",
    max_attempts: int = 3, validate=validate_rebased_runtime,
    sleep=time.sleep,
) -> dict:
    if not SHA.fullmatch(base_sha) or mode not in SCOPES:
        raise ValueError("Invalid Rates publish base SHA or mode")
    if max_attempts < 1 or max_attempts > 5:
        raise ValueError("Attempt count outside bounded safety range")
    if git("status", "--porcelain", cwd=cwd):
        raise RuntimeError("RATES_UNCOMMITTED_CHANGES_REFUSED")
    last_replayed_base = base_sha
    rebased = False

    for attempt in range(1, max_attempts + 1):
        # Fetch the exact target ref. Only Git's fast-forward push is used:
        # no force, no lease bypass, no overwrite of another writer.
        git("fetch", "--no-tags", "origin",
            "+refs/heads/main:refs/remotes/origin/main", cwd=cwd)
        remote_sha = git("rev-parse", "refs/remotes/origin/main", cwd=cwd)
        if not SHA.fullmatch(remote_sha):
            raise RuntimeError("RATES_REMOTE_HEAD_INVALID")
        if run(["git", "merge-base", "--is-ancestor", base_sha, remote_sha],
               cwd=cwd, check=False).returncode != 0:
            raise RuntimeError("RATES_REMOTE_DIVERGENCE_FAIL_CLOSED")

        if remote_sha != last_replayed_base:
            changed = set(git("diff", "--name-only", last_replayed_base,
                              remote_sha, cwd=cwd).splitlines())
            inspect_new_main_files(changed)
            # Replay ONLY our already-validated Rates commit(s) over
            # disjoint remote changes; fail if Git cannot rebase cleanly.
            git("rebase", "--onto", remote_sha, last_replayed_base,
                "HEAD", cwd=cwd)
            last_replayed_base = remote_sha
            rebased = True
            if git("status", "--porcelain", cwd=cwd):
                raise RuntimeError("RATES_REBASE_NOT_CLEAN")
            validate(cwd)

        own_diff = set(git("diff", "--name-only", remote_sha, "HEAD",
                           cwd=cwd).splitlines())
        verify_local_scope(own_diff, mode)
        result = run(["git", "push", "origin", "HEAD:refs/heads/main"],
                     cwd=cwd, check=False)
        if result.returncode == 0:
            return {
                "status": "RATES_SAFE_PUSH_CONFIRMED",
                "mode": mode, "attempts": attempt,
                "disjoint_remote_rebase": rebased,
                "changed_files": sorted(own_diff),
                "published_commit": git("rev-parse", "HEAD", cwd=cwd),
                "force_push": False,
            }
        if attempt >= max_attempts:
            break
        sleep(2 * attempt)
    raise RuntimeError(
        "RATES_PUSH_REJECTED_AFTER_BOUNDED_RETRIES: "
        "remote moved or push permission unavailable; no force-push performed"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--mode", choices=sorted(SCOPES), required=True)
    args = ap.parse_args()
    try:
        result = publish(base_sha=args.base, mode=args.mode)
    except (RuntimeError, subprocess.CalledProcessError, ValueError) as err:
        print("RATES_SAFE_PUBLISH_FAIL", str(err), file=sys.stderr)
        return 1
    print("RATES_SAFE_PUBLISH", json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
