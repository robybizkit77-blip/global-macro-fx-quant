#!/usr/bin/env python3
"""Apply a semantic-checked CAD OIS candidate when legacy line endings differ."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SECTION = ROOT / "live_data" / "sections" / "OIS_DATA.json"
PAYLOAD = ROOT / "payload" / "part-00.txt"
MARKER = b"window.__GMFQ_DATA.OIS_DATA="


def extract_payload_json(raw: bytes) -> tuple[dict, int, int]:
    start_marker = raw.find(MARKER)
    if start_marker < 0:
        raise ValueError("OIS runtime marker not found")
    start = start_marker + len(MARKER)
    text = raw[start:].decode("utf-8")
    value, end_chars = json.JSONDecoder().raw_decode(text)
    end = start + len(text[:end_chars].encode("utf-8"))
    cursor = end
    while raw[cursor:cursor + 1] in (b" ", b"\t", b"\r", b"\n"):
        cursor += 1
    if raw[cursor:cursor + 1] != b";":
        raise ValueError("OIS runtime assignment has no terminating semicolon")
    return value, start, end


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    args = ap.parse_args()

    existing = json.loads(SECTION.read_text(encoding="utf-8"))
    candidate_path = pathlib.Path(args.candidate)
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    payload = PAYLOAD.read_bytes()
    payload_value, start, end = extract_payload_json(payload)
    if payload_value != existing:
        raise SystemExit("Refusing update: OIS section and runtime payload differ semantically")

    changed = [currency for currency in existing["currencies"] if existing["currencies"][currency] != candidate["currencies"].get(currency)]
    # An already-applied candidate is permitted only as an idempotent byte
    # normalization pass; any non-CAD semantic delta remains a hard failure.
    if changed not in ([], ["CAD"]):
        raise SystemExit(f"Refusing update: candidate scope is not CAD-only: {changed}")
    cad = candidate["currencies"]["CAD"]
    required = ("source_validated", "asof_validated", "meeting_path_validated", "changes_validated", "current_real", "previous_real", "week_real")
    if cad.get("status") != "ACTIVE" or not all(cad.get("validation", {}).get(k) is True for k in required):
        raise SystemExit("Refusing update: CAD activation gate is incomplete")

    replacement = candidate_path.read_bytes().rstrip(b"\r\n")
    updated = payload[:start] + replacement + payload[end:]
    check_value, _, _ = extract_payload_json(updated)
    if check_value != candidate:
        raise SystemExit("Refusing update: runtime candidate round-trip mismatch")

    # The runtime embeds the compact JSON without a trailing newline; retain the
    # same bytes in the canonical section so the content-addressed manifest can
    # verify an exact one-occurrence round trip.
    SECTION.write_bytes(replacement)
    PAYLOAD.write_bytes(updated)
    print(json.dumps({
        "status": "PASS",
        "scope": changed,
        "semantic_baseline_match": True,
        "runtime_roundtrip_match": True,
        "candidate_as_of": cad["as_of"],
        "candidate_source": cad["source"],
        "changed_payload_part": 0,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
