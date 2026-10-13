#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "payload"
SECTIONS = ROOT / "live_data" / "sections"
PARTS = [PAYLOAD / f"part-{i:02d}.txt" for i in range(16)]
TARGETS = {
    "MACRO_THERMOMETER_DATA": SECTIONS / "MACRO_THERMOMETER_DATA.json",
    "MACRO_SERIES": SECTIONS / "MACRO_SERIES.json",
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def assignment_pattern(key: str) -> re.Pattern[str]:
    # Runtime assignments are legacy JS and are not guaranteed to use
    # const/let/var. Match the exact identifier followed by '=' while
    # excluding longer identifiers. This still fails closed if not unique.
    return re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(key)}(?![A-Za-z0-9_$])\s*=\s*")


def find_json_literal(text: str, key: str) -> tuple[int, int]:
    pattern = assignment_pattern(key)
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(f"{key}: expected exactly one assignment in selected payload part, found {len(matches)}")
    start = matches[0].end()
    while start < len(text) and text[start].isspace():
        start += 1
    if start >= len(text) or text[start] not in "[{":
        raise RuntimeError(f"{key}: assignment does not begin with JSON object/array")

    opening = text[start]
    closing = "}" if opening == "{" else "]"
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == opening:
            depth += 1
        elif ch == closing:
            depth -= 1
            if depth == 0:
                # Standalone JSON sections intentionally retain their terminal
                # newline. Include any whitespace immediately following the
                # literal so a converged repair is byte-idempotent instead of
                # re-adding one newline on every pass.
                end = i + 1
                while end < len(text) and text[end].isspace():
                    end += 1
                return start, end
    raise RuntimeError(f"{key}: unterminated JSON literal")


def locate_key(parts: list[str], key: str) -> int:
    pattern = assignment_pattern(key)
    hits = [i for i, text in enumerate(parts) if pattern.search(text)]
    if len(hits) != 1:
        raise RuntimeError(f"{key}: expected assignment in exactly one payload part, found parts={hits}")
    return hits[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Write repaired payload parts. Default is dry-run.")
    args = ap.parse_args()

    parts = [p.read_text(encoding="utf-8") for p in PARTS]
    receipts = []

    for key, section_path in TARGETS.items():
        replacement = section_path.read_text(encoding="utf-8")
        # Standalone must itself be valid JSON before it is allowed into runtime.
        json.loads(replacement)

        part_idx = locate_key(parts, key)
        current = parts[part_idx]
        start, end = find_json_literal(current, key)
        embedded = current[start:end]
        json.loads(embedded)

        changed = embedded != replacement
        repaired = current[:start] + replacement + current[end:] if changed else current
        receipts.append({
            "key": key,
            "part": part_idx,
            "changed": changed,
            "old_literal_bytes": len(embedded.encode("utf-8")),
            "new_literal_bytes": len(replacement.encode("utf-8")),
            "old_literal_sha256": sha256_text(embedded),
            "new_literal_sha256": sha256_text(replacement),
            "old_part_sha256": sha256_text(current),
            "new_part_sha256": sha256_text(repaired),
            "byte_delta": len(repaired.encode("utf-8")) - len(current.encode("utf-8")),
        })
        parts[part_idx] = repaired

    # Post-repair invariant: each standalone blob occurs exactly once in payload.
    for key, section_path in TARGETS.items():
        raw = section_path.read_text(encoding="utf-8")
        hits = [(i, text.count(raw)) for i, text in enumerate(parts) if text.count(raw)]
        total = sum(n for _, n in hits)
        if total != 1 or len(hits) != 1:
            raise RuntimeError(f"{key}: repaired standalone must occur exactly once; total={total}, hits={hits}")

    changed_parts = sorted({r["part"] for r in receipts if r["changed"]})
    if args.apply:
        for idx in changed_parts:
            PARTS[idx].write_text(parts[idx], encoding="utf-8")

    out = {
        "status": "PASS",
        "apply": args.apply,
        "targets": receipts,
        "changed_payload_parts": changed_parts,
        "tracked_standalone_mutation": False,
        "publication": False,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
