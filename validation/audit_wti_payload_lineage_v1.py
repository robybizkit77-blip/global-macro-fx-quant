#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path

TARGETS = ["92.16", "94.61", "92.41"]
PATHS = ["payload/part-00.txt", "live_data/sections/D.json"]


def run(*args: str) -> str:
    return subprocess.check_output(args, text=True, errors="replace")


def file_at(commit: str, path: str) -> str | None:
    try:
        return run("git", "show", f"{commit}:{path}")
    except subprocess.CalledProcessError:
        return None


def commit_meta(commit: str) -> dict:
    fmt = "%H%x00%P%x00%cI%x00%s"
    raw = run("git", "show", "-s", f"--format={fmt}", commit).strip()
    sha, parents, date, subject = raw.split("\x00", 3)
    return {"sha": sha, "parents": parents.split(), "date": date, "subject": subject}


def main() -> None:
    # Follow first-parent main lineage so stacked/side branches cannot masquerade as production history.
    commits = run("git", "rev-list", "--first-parent", "origin/main").splitlines()
    rows = []
    for commit in commits:
        hit = False
        path_rows = []
        for path in PATHS:
            text = file_at(commit, path)
            if text is None:
                continue
            matches = {t: (t in text) for t in TARGETS}
            triple = all(matches.values())
            if triple:
                hit = True
            # Also retain any WTI/date evidence even before the exact triple appears.
            has_wti = 'WTI' in text
            if triple or has_wti:
                path_rows.append({"path": path, "target_matches": matches, "all_three": triple, "has_wti": has_wti})
        if hit:
            row = commit_meta(commit)
            row["paths"] = path_rows
            rows.append(row)

    # Oldest first for provenance reasoning.
    rows.reverse()
    first = rows[0] if rows else None
    last = rows[-1] if rows else None
    receipt = {
        "schema": "GMFQ_WTI_PAYLOAD_LINEAGE_AUDIT_V1",
        "status": "FORENSIC_READ_ONLY",
        "main_head": run("git", "rev-parse", "origin/main").strip(),
        "search_scope": "origin/main first-parent lineage only",
        "targets": TARGETS,
        "matching_commits_count": len(rows),
        "first_matching_commit": first,
        "last_matching_commit": last,
        "matching_commits": rows,
        "mutation_performed": False,
        "publication_performed": False,
    }
    Path("/tmp/wti-payload-lineage-receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
