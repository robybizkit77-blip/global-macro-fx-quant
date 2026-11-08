#!/usr/bin/env python3
"""Read-only preflight: suppress redundant V2 gh-pages writes by exact Git tree.

This compares the *entire* V2 subtree, not selected HTML files or a mutable
date label. The result concerns Git branch bytes only, NOT public CDN proof.
Any missing/invalid Git evidence fails closed rather than claiming parity.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Callable

SUBTREE = "site/fx-quant-v2"
SCHEMA = "GMFQ_FXV2_PUBLICATION_TREE_PREFLIGHT_V1"


def tree_oid(ref: str) -> str:
    if ref not in {"origin/main", "origin/gh-pages"}:
        raise ValueError("unexpected Git ref")
    cmd = ["git", "rev-parse", "--verify", f"{ref}:{SUBTREE}"]
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    oid = proc.stdout.strip()
    if proc.returncode or re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", oid) is None:
        raise ValueError(f"unverified V2 Git tree on {ref}")
    kind = subprocess.run(
        ["git", "cat-file", "-t", oid], check=False, capture_output=True, text=True)
    if kind.returncode or kind.stdout.strip() != "tree":
        raise ValueError(f"V2 source is not a Git tree on {ref}")
    return oid


def inspect(resolve: Callable[[str], str] = tree_oid) -> dict:
    source = resolve("origin/main")
    published = resolve("origin/gh-pages")
    # Incomplete or forged values must not license a false no-op.
    for value in (source, published):
        if not isinstance(value, str) or re.fullmatch(
            r"[a-f0-9]{40}|[a-f0-9]{64}", value) is None:
            raise ValueError("invalid V2 tree evidence")
    same = source == published
    return {
        "schema": SCHEMA,
        "status": "NO_V2_BRANCH_WRITE_NEEDED" if same else "V2_BRANCH_WRITE_REQUIRED",
        "publish_needed": not same,
        "source_tree": source,
        "pages_tree": published,
        "compared_path": SUBTREE,
        "branch_parity_only_not_public_http": True,
        "public_delivery_certified": False,
        "no_core_or_signal_effect": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    result = inspect()
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write(
                f"publish_needed={str(result['publish_needed']).lower()}\n"
                f"source_tree={result['source_tree']}\n"
                f"pages_tree={result['pages_tree']}\n"
            )
    print("FXV2_PUBLICATION_TREE_PREFLIGHT", json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
