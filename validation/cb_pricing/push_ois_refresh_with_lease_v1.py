#!/usr/bin/env python3
"""Safely persist an already validated OIS refresh despite unrelated main commits.

Only rebases on remote commits that did not change any OIS source, logic, or
persistent OIS artifact. Never force-pushes or replaces concurrently updated OIS.
Each non-fast-forward retry fetches and checks the protected dependency set.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from ois_g8_history_snapshot_v1 import make_record

G8_HISTORY = "validation/cb_pricing/history/OIS_G8_SNAPSHOTS_V1.jsonl"
NZD_CAPTURE_HISTORY = "validation/cb_pricing/history/NZD_ASX_PROXY_CAPTURES_V1.jsonl"
OPERATIONAL_VIEW = "live_data/sections/OIS_OPERATIONAL_VIEW.json"

ESTIMATED_PATHS = (
    "live_data/sections/CB_PRICING_ESTIMATED_LIVE_QUOTES.json",
    "live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json",
    "live_data/sections/CB_PRICING_ESTIMATED.json",
    OPERATIONAL_VIEW,
    # Publishing the operational view without its matching pending-source
    # dossier can leave Home and Rates contradictory until the next G8 job.
    # Both writers share the existing exclusive concurrency group and lease.
    "live_data/sections/OIS_SOURCE_READINESS_VIEW.json",
    "validation/cb_pricing/history/OIS_ESTIMATED_SNAPSHOTS_V1.jsonl",
    "validation/cb_pricing/history/OIS_SAME_CONTRACT_QUOTES_V1.jsonl",
    "validation/cb_pricing/history/OIS_SAME_CONTRACT_CONFLICTS_V1.jsonl",
    "site/fx-quant-v2/ois-pricing-snapshot.json",
    "site/fx-quant-v2/ois-same-contract-repricing-research.json",
    "site/fx-quant-v2/next/rates-pricing-history-v1.json",
    G8_HISTORY,
    NZD_CAPTURE_HISTORY,
)
G8_PATHS = ESTIMATED_PATHS
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
    "site/fx-quant-v2/ois-pricing-snapshot.json",
    "site/fx-quant-v2/ois-same-contract-repricing-research.json",
    "site/fx-quant-v2/next/rates-pricing-history-v1.json",
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


def verify_official_history_append(base_sha: str, cwd: Path | None) -> None:
    before = git("show", f"{base_sha}:{G8_HISTORY}", cwd=cwd).stdout.encode("utf-8")
    root = cwd if cwd is not None else Path.cwd()
    after = (root / G8_HISTORY).read_bytes()
    if not after.startswith(before):
        raise LeaseError("REFUSED_G8_HISTORY_REWRITE")
    currencies = json.loads((root / OPERATIONAL_VIEW).read_text(encoding="utf-8"))["currencies"]
    for line in after[len(before):].splitlines():
        rec = json.loads(line)
        row = currencies.get(rec.get("currency"), {})
        if (row.get("operational_status") != "GREEN_OFFICIAL"
                or row.get("official_status") != "ACTIVE"
                or row.get("backtest_eligible_as_official") is not True
                or not rec.get("captured_at_utc")
                or rec != make_record(rec["currency"], row, rec["captured_at_utc"])):
            raise LeaseError("REFUSED_NON_OFFICIAL_G8_HISTORY_APPEND")


# These two source collectors record the time of the fetch, even when every
# quote and quality field is unchanged. Do not turn that timestamp alone into
# a persistent market-data refresh. No other paths or fields are exempt.
FETCH_CLOCK_ONLY_PATHS = frozenset(ESTIMATED_PATHS[:2])


def only_fetch_clock_changed(base_sha: str, changed: set[str], cwd: Path | None) -> bool:
    if not changed or not changed.issubset(FETCH_CLOCK_ONLY_PATHS):
        return False
    root = cwd if cwd is not None else Path.cwd()
    for path in changed:
        try:
            before = json.loads(git("show", f"{base_sha}:{path}", cwd=cwd).stdout)
            after = json.loads((root / path).read_text(encoding="utf-8"))
        except (OSError, ValueError, LeaseError):
            return False
        if not isinstance(before, dict) or not isinstance(after, dict):
            return False
        old = before.pop("generated_at_utc", None)
        new = after.pop("generated_at_utc", None)
        if not isinstance(old, str) or not isinstance(new, str) or before != after:
            return False
    return True


# A whole-document ASX checksum can change although the selected contracts,
# dates, provenance URLs, quality, and all derived prices remain identical.
# Only the paired NZD reference hashes may be ignored, never a history append,
# a conflicting hash, or any other source/market field.
NZD_PROXY = ESTIMATED_PATHS[1]
NEXT_HISTORY = "site/fx-quant-v2/next/rates-pricing-history-v1.json"


def only_asx_reference_metadata_changed(base_sha: str, changed: set[str], cwd: Path | None) -> bool:
    pair = {NZD_PROXY, NEXT_HISTORY}
    if not pair.issubset(changed) or not changed.issubset(pair | {ESTIMATED_PATHS[0]}):
        return False
    root = cwd if cwd is not None else Path.cwd()
    hashes = []
    try:
        for path in sorted(changed):
            before = json.loads(git("show", f"{base_sha}:{path}", cwd=cwd).stdout)
            after = json.loads((root / path).read_text(encoding="utf-8"))
            for obj in (before, after):
                if path != NEXT_HISTORY:
                    if not isinstance(obj.pop("generated_at_utc", None), str):
                        return False
                if path == NZD_PROXY:
                    node = obj["monthly_reference"]
                    if node["schema"] != "GMFQ_NZD_ASX_EXACT_20_WEEKDAY_REFERENCE_V1" or node["status"] != "REFERENCE_PARSED":
                        return False
                    value = node.pop("decoded_source_sha256")
                elif path == NEXT_HISTORY:
                    node = obj["currencies"]["NZD"]["fixed_contract_20d"]
                    if node["basis"] != "EXACT_LISTED_ASX_BANK_BILL_CONTRACT_NOT_OIS":
                        return False
                    value = node.pop("source_sha256")
                else:
                    continue
                if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                    return False
                hashes.append(value)
            if before != after:
                return False
    except (OSError, ValueError, LeaseError, KeyError, TypeError, AttributeError):
        return False
    return len(hashes) == 4 and hashes[0] == hashes[2] and hashes[1] == hashes[3] and hashes[0] != hashes[1]


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
    if mode == "estimated" and G8_HISTORY in unstaged + staged:
        verify_official_history_append(base_sha, cwd)
    if NZD_CAPTURE_HISTORY in unstaged + staged:
        root = cwd if cwd is not None else Path.cwd()
        previous = git("show", f"{base_sha}:{NZD_CAPTURE_HISTORY}", cwd=cwd).stdout.encode("utf-8")
        updated = (root / NZD_CAPTURE_HISTORY).read_bytes()
        if not updated.startswith(previous):
            raise LeaseError("REFUSED_NZD_CAPTURE_HISTORY_REWRITE")
        source = json.loads((root / "live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json").read_text())
        from archive_nzd_asx_proxy_v1 import validate
        for line in updated[len(previous):].splitlines():
            record = validate(json.loads(line))
            if record["source_commit"] != "VALIDATED_COLLECTOR_RUNTIME" or record["feed"] != source:
                raise LeaseError("REFUSED_NZD_CAPTURE_NOT_CURRENT_VALIDATED_SOURCE")
    if not staged and only_fetch_clock_changed(base_sha, set(unstaged), cwd):
        return {"status": "NO_CHANGE", "mode": mode, "attempts": 0,
                "reason": "FETCH_CLOCK_ONLY"}
    if not staged and only_asx_reference_metadata_changed(base_sha, set(unstaged), cwd):
        return {"status": "NO_CHANGE", "mode": mode, "attempts": 0,
                "reason": "ASX_REFERENCE_METADATA_ONLY"}
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
