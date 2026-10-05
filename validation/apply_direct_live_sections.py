#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ROOT / "live_data" / "sections"
PAYLOAD = ROOT / "payload"
MANIFEST = ROOT / "live_data" / "manifest.v2.json"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply validated DIRECT_SINGLE_PART section changes to payload and manifest.v2")
    ap.add_argument("--before-dir", type=Path, required=True, help="Directory containing pre-change copies of changed section files")
    ap.add_argument("--section", action="append", required=True, help="Section key from manifest.v2; repeat for multiple sections")
    ap.add_argument("--evidence", type=Path)
    args = ap.parse_args()

    manifest = load_json(MANIFEST)
    if manifest.get("schema") != "GMFQ_LIVE_DATA_MANIFEST_V2":
        raise SystemExit("manifest.v2 schema mismatch")
    rows = {str(r.get("key")): r for r in manifest.get("sections", [])}
    evidence: list[dict[str, Any]] = []

    for key in args.section:
        if key not in rows:
            raise SystemExit(f"unknown manifest section key: {key}")
        row = rows[key]
        if row.get("mode") != "DIRECT_SINGLE_PART" or row.get("direct_update_allowed") is not True:
            raise SystemExit(f"section {key} is not a direct-update surface")
        file_name = str(row.get("file"))
        part_index = row.get("part")
        if not isinstance(part_index, int):
            raise SystemExit(f"section {key} has invalid payload part")

        before_path = args.before_dir / file_name
        after_path = SECTIONS / file_name
        part_path = PAYLOAD / f"part-{part_index:02d}.txt"
        if not before_path.exists() or not after_path.exists() or not part_path.exists():
            raise SystemExit(f"missing input for {key}")

        old = before_path.read_bytes()
        new = after_path.read_bytes()
        part = part_path.read_bytes()
        occurrences = part.count(old)
        if occurrences != 1:
            raise SystemExit(f"{key}: expected old section exactly once in {part_path.name}, found {occurrences}")
        if old == new:
            # No replacement needed, but manifest should still describe current bytes.
            updated_part = part
        else:
            updated_part = part.replace(old, new, 1)
            part_path.write_bytes(updated_part)

        if updated_part.count(new) != 1:
            raise SystemExit(f"{key}: new section does not occur exactly once after replacement")

        row["bytes"] = len(new)
        row["sha256"] = sha(new)
        row["occurrences_in_payload"] = 1
        row["part"] = part_index
        evidence.append({
            "key": key,
            "file": file_name,
            "part": part_index,
            "old_bytes": len(old),
            "new_bytes": len(new),
            "old_sha256": sha(old),
            "new_sha256": sha(new),
            "payload_part_sha256": sha(updated_part),
            "changed": old != new,
        })

    parts = [PAYLOAD / f"part-{i:02d}.txt" for i in range(16)]
    missing = [p.name for p in parts if not p.exists()]
    if missing:
        raise SystemExit(f"missing payload parts: {missing}")
    runtime = b"".join(p.read_bytes() for p in parts)
    manifest["runtime_sha256"] = sha(runtime)
    manifest["runtime_bytes"] = len(runtime)
    manifest["part_count"] = 16
    manifest["generated_from_current_payload"] = True
    manifest["failures"] = []
    manifest["status"] = "PASS"
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    result = {
        "status": "PASS",
        "sections": evidence,
        "runtime_sha256": manifest["runtime_sha256"],
        "runtime_bytes": manifest["runtime_bytes"],
        "manifest_updated": True,
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
