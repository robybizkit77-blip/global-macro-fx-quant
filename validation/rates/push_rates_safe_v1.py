#!/usr/bin/env python3
"""Publish validated G8 Rates on main without overwriting concurrent writers.

Replay a validated candidate over disjoint changes. If only shared runtime
files overlap, rebuild them from the latest main and the validated Rates JSON.
Never promote a stale candidate over newer Rates source data.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RATES_DATA = "live_data/sections/NATIVE_RATES_DATA.json"
RATES_METADATA = "live_data/sections/RATES_AUDIT_METADATA.json"
RATES_SOURCES = frozenset({RATES_DATA, RATES_METADATA})
SHARED_RUNTIME = frozenset({
    "live_data/manifest.v2.json",
    "payload/part-00.txt",
    "payload/part-15.txt",
})
RATES_OWNED = RATES_SOURCES | SHARED_RUNTIME
SCOPES = {
    "rates": RATES_OWNED,
    "metadata": frozenset({
        RATES_METADATA,
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
    """Refuse changed Rates sources. Derived runtime can be rebuilt."""
    overlap = changed & RATES_SOURCES
    if overlap:
        raise RuntimeError(
            "RATES_CONCURRENT_SOURCE_CHANGED_FAIL_CLOSED: "
            + ", ".join(sorted(overlap))
        )


def canonical_rates_already_identical(remote_sha: str, cwd: str | Path) -> bool:
    """A concurrent writer already committed the *exact same* Rates JSON blob.

    This is only a no-op gate. It never publishes, rebases or overwrites
    another writer's sources, and does not equate same date with same data.
    """
    remote_blob = git("rev-parse", f"{remote_sha}:{RATES_DATA}", cwd=cwd)
    candidate_blob = git("rev-parse", f"HEAD:{RATES_DATA}", cwd=cwd)
    return bool(remote_blob) and remote_blob == candidate_blob


def verify_local_scope(changed: set[str], mode: str) -> None:
    if not changed or not changed <= SCOPES[mode]:
        raise RuntimeError(
            "RATES_PUBLISH_SCOPE_VIOLATION: " + repr(sorted(changed))
        )
    if mode == "rates" and RATES_DATA not in changed:
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


def rebuild_shared_runtime(
    remote_sha: str, changed: set[str], mode: str, cwd: str | Path, validate,
) -> None:
    """Apply the exact validated source files using main's current generators."""
    verify_local_scope(changed, mode)
    sources = changed & RATES_SOURCES
    if not sources:
        raise RuntimeError("RATES_REBUILD_WITHOUT_SOURCE_CHANGE_REFUSED")
    candidate = git("rev-parse", "HEAD", cwd=cwd)
    with tempfile.TemporaryDirectory() as scratch:
        replacements = {}
        for source in sources:
            path = Path(scratch) / Path(source).name
            path.write_bytes((Path(cwd) / source).read_bytes())
            replacements[source] = path
        git("reset", "--hard", remote_sha, cwd=cwd)
        try:
            if RATES_DATA in replacements:
                run([sys.executable, "validation/update_live_direct_section.py",
                     "--section", "NATIVE_RATES_DATA", "--replacement",
                     str(replacements[RATES_DATA]), "--apply"], cwd=cwd)
            if RATES_METADATA in replacements:
                run([sys.executable, "validation/update_live_derived_sections.py",
                     "--rates", str(replacements[RATES_METADATA]), "--apply"], cwd=cwd)
            run([sys.executable, "validation/build_live_manifest_v2.py",
                 "--write", "live_data/manifest.v2.json"], cwd=cwd)
            for source, expected in replacements.items():
                if (Path(cwd) / source).read_bytes() != expected.read_bytes():
                    raise RuntimeError("RATES_REBUILD_ALTERED_VALIDATED_SOURCE: " + source)
            rebuilt = set(git("diff", "--name-only", remote_sha, cwd=cwd).splitlines())
            verify_local_scope(rebuilt, mode)
            validate(cwd)
            git("add", "--", *sorted(rebuilt), cwd=cwd)
            git("commit", "-C", candidate, cwd=cwd)
        except Exception:
            git("reset", "--hard", candidate, cwd=cwd)
            raise


def publish(
    *, base_sha: str, mode: str, cwd: str | Path = ".",
    max_attempts: int = 3, validate=validate_rebased_runtime,
    sleep=time.sleep,
) -> dict:
    if not SHA.fullmatch(base_sha) or mode not in SCOPES:
        raise ValueError("Invalid Rates publish base SHA or mode")
    if max_attempts < 1 or max_attempts > 5:
        raise ValueError("Attempt count outside bounded safety range")
    if git("status", "--porcelain", "--untracked-files=no", cwd=cwd):
        raise RuntimeError("RATES_UNCOMMITTED_CHANGES_REFUSED")
    last_replayed_base = base_sha
    rebased = False
    runtime_rebuilt = False

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
            own_candidate = set(git("diff", "--name-only", last_replayed_base,
                                    "HEAD", cwd=cwd).splitlines())
            if mode == "rates" and changed & RATES_OWNED:
                # Two successful scheduled collectors can observe the exact
                # same official close. Preserve the first writer and report
                # a verified no-op, never a second push or false failure.
                verify_local_scope(own_candidate, mode)
                if canonical_rates_already_identical(remote_sha, cwd):
                    return {
                        "status": "RATES_ALREADY_PUBLISHED_IDENTICAL",
                        "mode": mode, "attempts": attempt,
                        "disjoint_remote_rebase": rebased,
                        "shared_runtime_rebuilt": runtime_rebuilt,
                        "changed_files": [],
                        "published_commit": remote_sha,
                        "force_push": False,
                        "canonical_blob_identical": True,
                    }
            inspect_new_main_files(changed)
            if changed & SHARED_RUNTIME:
                rebuild_shared_runtime(remote_sha, own_candidate, mode, cwd, validate)
                runtime_rebuilt = True
            else:
                git("rebase", "--onto", remote_sha, last_replayed_base,
                    "HEAD", cwd=cwd)
                rebased = True
                validate(cwd)
            last_replayed_base = remote_sha
            if git("status", "--porcelain", "--untracked-files=no", cwd=cwd):
                raise RuntimeError("RATES_REBASE_NOT_CLEAN")

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
                "shared_runtime_rebuilt": runtime_rebuilt,
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
