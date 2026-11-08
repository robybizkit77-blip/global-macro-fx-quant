#!/usr/bin/env python3
"""Fail-closed, read-only no-op check for the exact Control Room Pages copy set.

Only when every copied file on validated main is byte-identical to gh-pages
can the publisher skip mutation. Git branch parity is not public HTTP delivery.
The copy set is parsed from the live publishing workflow to avoid a second
hand-maintained, potentially incomplete list.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/publish-dashboard-pages-v1.yml"
SCHEMA = "GMFQ_DASHBOARD_PAGES_MIRROR_NOOP_V1"
REQUIRED_DIRS = {"dashboard", "live_data/sections"}


def copied_paths(workflow: str) -> tuple[str, ...]:
    """Derive all *explicit* copy targets from the approved shell publisher."""
    required = (
        "cp index.html /tmp/gmfq-pages/index.html",
        "cp payload/part-*.txt /tmp/gmfq-pages/payload/",
        "cp live_data/manifest.v2.json /tmp/gmfq-pages/live_data/manifest.v2.json",
    )
    if any(workflow.count(cmd) != 1 for cmd in required):
        raise ValueError("Pages copy scope no longer matches its proof")
    pattern = re.compile(
        r'(?m)^          for f in (?P<names>[A-Za-z0-9_. -]+); do cp '
        r'"(?P<folder>dashboard|live_data/sections)/\$f" '
        r'"/tmp/gmfq-pages/(?P=folder)/\$f"; done$'
    )
    found = list(pattern.finditer(workflow))
    if len(found) != 2 or {m.group("folder") for m in found} != REQUIRED_DIRS:
        raise ValueError("Pages runtime/feed copy scope changed without reviewed parity")
    # Reject any extra independent "cp" to the public worktree, rather than
    # silently skipping an asset newly added to the publisher.
    copy_commands = [line.strip() for line in workflow.splitlines()
                     if "/tmp/gmfq-pages/" in line and (
                         "cp " in line or line.strip().startswith("cp "))]
    if len(copy_commands) != 5:
        raise ValueError("Unlisted Pages copy command")
    paths = ["index.html", "live_data/manifest.v2.json"]
    paths.extend(f"payload/part-{n:02d}.txt" for n in range(16))
    for match in found:
        folder = match.group("folder")
        names = match.group("names").split()
        if not names or len(names) != len(set(names)):
            raise ValueError("Invalid public-copy names")
        if any(not re.fullmatch(r"[A-Za-z0-9_.-]+", name) for name in names):
            raise ValueError("Unsafe public-copy name")
        paths.extend(f"{folder}/{name}" for name in names)
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate Pages copy target")
    return tuple(sorted(paths))


def git_rows(ref: str, paths: tuple[str, ...]) -> dict[str, str]:
    if ref not in {"HEAD", "origin/gh-pages"}:
        raise ValueError("Unapproved Git ref")
    proc = subprocess.run(
        ["git", "ls-tree", "-r", "-z", "--full-tree", ref, "--", *paths],
        cwd=ROOT, check=False, capture_output=True,
    )
    if proc.returncode:
        raise ValueError("Missing or unreadable Git source: " + ref)
    result = {}
    for raw in proc.stdout.split(b"\0"):
        if not raw:
            continue
        try:
            head, path_bytes = raw.split(b"\t", 1)
            mode, typ, oid = head.decode("ascii").split()
            name = path_bytes.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("Malformed Git tree response") from exc
        if mode not in ("100644", "100755") or typ != "blob":
            raise ValueError("Invalid Git asset type: " + name)
        if name in result or name not in paths or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", oid):
            raise ValueError("Unexpected Git asset: " + name)
        result[name] = oid
    return result


def inspect(workflow: str, source: dict[str, str],
            pages: dict[str, str]) -> dict:
    paths = copied_paths(workflow)
    if set(source) != set(paths):
        raise ValueError("MAIN_COPIED_ASSET_MISSING_OR_UNTRACKED")
    if any(not re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", sha)
           for sha in source.values()):
        raise ValueError("MAIN_COPIED_ASSET_INVALID_BLOB")
    same = set(pages) == set(paths) and all(
        pages.get(p) == source[p] for p in paths
    )
    return {
        "schema": SCHEMA,
        "status": "PUBLICATION_BRANCH_NOOP" if same else "PUBLICATION_REQUIRED",
        "publish_needed": not same,
        "total_copied_assets": len(paths),
        "different_assets": sum(pages.get(p) != source[p] for p in paths),
        "source_scope": "EXACT_CONTROL_ROOM_PUBLISHER_COPY_FILES",
        "branch_parity_only_not_public_http": True,
        "public_http_certified": False,
        "no_core_or_signal_effect": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    wf = WORKFLOW.read_text(encoding="utf-8")
    paths = copied_paths(wf)
    # The caller first refreshes origin/main and checks out that exact main.
    # Fail rather than treating a stale checkout as a validated source.
    remote = subprocess.run(
        ["git", "rev-parse", "--verify", "origin/main"],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    local = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    if remote != local:
        raise ValueError("PAGES_NOOP_SOURCE_MAIN_MOVED")
    result = inspect(wf, git_rows("HEAD", paths),
                     git_rows("origin/gh-pages", paths))
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as out:
            out.write(f"publish_needed={str(result['publish_needed']).lower()}\n")
    print("PAGES_DASHBOARD_BRANCH_PARITY", json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
