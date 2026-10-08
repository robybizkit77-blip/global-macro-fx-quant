#!/usr/bin/env python3
"""Apply semantic-checked JPY OIS/native-CB candidates to live sections/runtime.

Fail-closed: refuses any semantic delta outside JPY and verifies both runtime
assignments round-trip exactly. Manifest rebuild is intentionally a separate step.
"""
from __future__ import annotations
import argparse, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OIS_SECTION = ROOT / "live_data" / "sections" / "OIS_DATA.json"
NATIVE_SECTION = ROOT / "live_data" / "sections" / "NATIVE_CB_DATA.json"
PAYLOAD = ROOT / "payload" / "part-00.txt"
OIS_MARKER = b"window.__GMFQ_DATA.OIS_DATA="
NATIVE_MARKER = b"window.__GMFQ_DATA.NATIVE_CB_DATA="


def extract(raw: bytes, marker: bytes):
    m = raw.find(marker)
    if m < 0:
        raise ValueError(f"runtime marker not found: {marker!r}")
    start = m + len(marker)
    text = raw[start:].decode("utf-8")
    value, end_chars = json.JSONDecoder().raw_decode(text)
    end = start + len(text[:end_chars].encode("utf-8"))
    cursor = end
    while raw[cursor:cursor+1] in (b" ",b"\t",b"\r",b"\n"):
        cursor += 1
    if raw[cursor:cursor+1] != b";":
        raise ValueError("runtime assignment has no terminating semicolon")
    return value, start, end


def replace(raw: bytes, marker: bytes, candidate_bytes: bytes):
    _, start, end = extract(raw, marker)
    updated = raw[:start] + candidate_bytes + raw[end:]
    check, _, _ = extract(updated, marker)
    if check != json.loads(candidate_bytes.decode("utf-8")):
        raise ValueError("runtime candidate round-trip mismatch")
    return updated


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ois-candidate", required=True)
    ap.add_argument("--native-candidate", required=True)
    a = ap.parse_args()

    existing_ois = json.loads(OIS_SECTION.read_text(encoding="utf-8"))
    existing_native = json.loads(NATIVE_SECTION.read_text(encoding="utf-8"))
    ois_path = pathlib.Path(a.ois_candidate)
    native_path = pathlib.Path(a.native_candidate)
    cand_ois = json.loads(ois_path.read_text(encoding="utf-8"))
    cand_native = json.loads(native_path.read_text(encoding="utf-8"))

    changed_ois = [k for k in existing_ois["currencies"] if existing_ois["currencies"][k] != cand_ois["currencies"].get(k)]
    changed_native = [k for k in existing_native if existing_native[k] != cand_native.get(k)]
    if changed_ois not in ([],["JPY"]) or changed_native not in ([],["JPY"]):
        raise SystemExit(f"Refusing update: non-JPY semantic delta OIS={changed_ois} NATIVE={changed_native}")

    jpy = cand_ois["currencies"]["JPY"]
    req = ("source_validated","asof_validated","meeting_path_validated","changes_validated","current_real","previous_real","week_real")
    if jpy.get("status") != "ACTIVE" or not all(jpy.get("validation",{}).get(k) is True for k in req):
        raise SystemExit("Refusing update: JPY activation gate incomplete")

    raw = PAYLOAD.read_bytes()
    runtime_ois, _, _ = extract(raw,OIS_MARKER)
    runtime_native, _, _ = extract(raw,NATIVE_MARKER)
    if runtime_ois != existing_ois or runtime_native != existing_native:
        raise SystemExit("Refusing update: live sections and runtime payload differ semantically")

    ois_bytes = ois_path.read_bytes().rstrip(b"\r\n")
    native_bytes = native_path.read_bytes().rstrip(b"\r\n")
    updated = replace(raw,OIS_MARKER,ois_bytes)
    updated = replace(updated,NATIVE_MARKER,native_bytes)

    OIS_SECTION.write_bytes(ois_bytes)
    NATIVE_SECTION.write_bytes(native_bytes)
    PAYLOAD.write_bytes(updated)
    print(json.dumps({
        "status":"PASS",
        "scope":{"OIS":changed_ois,"NATIVE_CB":changed_native},
        "runtime_roundtrip_match":True,
        "candidate_as_of":jpy["as_of"],
        "candidate_source":jpy["source"],
        "changed_payload_part":0,
        "next_required_step":"python3 validation/build_live_manifest_v2.py --write"
    },indent=2,ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
