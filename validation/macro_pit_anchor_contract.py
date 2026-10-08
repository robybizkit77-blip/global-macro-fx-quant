#!/usr/bin/env python3
"""Fail-closed evidence contract for one atomic macro PIT refresh.

This tool never applies a candidate to live_data.  ``capture`` copies the two
runtime artifacts to an external evidence directory; ``verify`` rebuilds only
from the BEFORE copies and proves semantic parity with the AFTER copies.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERIES_REL = pathlib.Path("live_data/sections/MACRO_SERIES.json")
HEAT_REL = pathlib.Path("live_data/sections/MACRO_THERMOMETER_DATA.json")
SERIES_NAME, HEAT_NAME = SERIES_REL.name, HEAT_REL.name
REGISTRY_REL = pathlib.Path("validation/macro/MACRO_SOURCE_REGISTRY_2026-10-08.json")
# A refresh may change live_data only.  Changes to any of these paths between
# captures invalidate the anchor rather than silently changing replay rules.
PROTECTED_PATHS = (
    pathlib.Path("validation/build_macro_candidate.py"),
    pathlib.Path("validation/macro"),
    pathlib.Path("validation/sources"),
)


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def protected_fingerprints() -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in PROTECTED_PATHS:
        path = ROOT / rel
        if path.is_file():
            out[rel.as_posix()] = sha256_file(path)
        elif path.is_dir():
            for child in sorted(p for p in path.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
                out[child.relative_to(ROOT).as_posix()] = sha256_file(child)
        else:
            raise ValueError(f"protected path missing: {rel}")
    return out


def dirty_paths() -> list[str]:
    return [line[3:] for line in git("status", "--porcelain").splitlines() if line]


def snapshot_paths(evidence_dir: pathlib.Path, phase: str) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    base = evidence_dir / phase
    return base / SERIES_NAME, base / HEAT_NAME, base / "capture.json"


def assert_snapshot_integrity(meta: dict, series_path: pathlib.Path, heat_path: pathlib.Path) -> None:
    if meta.get("schema") != "GMFQ_MACRO_PIT_CAPTURE_V1":
        raise ValueError("unexpected capture schema")
    for name, path in ((SERIES_NAME, series_path), (HEAT_NAME, heat_path)):
        expected = meta.get("artifacts", {}).get(name, {})
        if expected.get("sha256") != sha256_file(path):
            raise ValueError(f"captured {name} byte fingerprint mismatch")
        if expected.get("semantic_sha256") != canonical_hash(load(path)):
            raise ValueError(f"captured {name} semantic fingerprint mismatch")


def capture(args: argparse.Namespace) -> int:
    dirty = dirty_paths()
    allowed_live_dirty = {SERIES_REL.as_posix(), HEAT_REL.as_posix()}
    allow_live_dirty = args.phase == "after" and args.allow_live_data_dirty
    if dirty and (not allow_live_dirty or not set(dirty).issubset(allowed_live_dirty)):
        raise ValueError("capture requires a clean repository; AFTER may opt in only to dirty target live artifacts")
    evidence_dir = pathlib.Path(args.evidence_dir).resolve()
    series_out, heat_out, manifest_out = snapshot_paths(evidence_dir, args.phase)
    if manifest_out.exists() and not args.overwrite:
        raise ValueError(f"snapshot already exists: {manifest_out}; use --overwrite only for a deliberate recapture")
    for src, dst in ((ROOT / SERIES_REL, series_out), (ROOT / HEAT_REL, heat_out)):
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    registry = load(ROOT / REGISTRY_REL)
    key = f"{args.currency}.{args.dimension}"
    row = registry.get("series", {}).get(key)
    if not isinstance(row, dict):
        raise ValueError(f"unknown core series: {key}")
    if row.get("macro_series_id") not in (None, args.macro_series_id):
        raise ValueError("registry macro_series_id conflicts with requested target")
    manifest = {
        "schema": "GMFQ_MACRO_PIT_CAPTURE_V1",
        "phase": args.phase.upper(),
        "captured_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "git_head": git("rev-parse", "HEAD"),
        "target": {"currency": args.currency, "dimension": args.dimension, "macro_series_id": args.macro_series_id},
        "artifacts": {
            SERIES_NAME: {"sha256": sha256_file(series_out), "semantic_sha256": canonical_hash(load(series_out))},
            HEAT_NAME: {"sha256": sha256_file(heat_out), "semantic_sha256": canonical_hash(load(heat_out))},
        },
        "protected_fingerprints": protected_fingerprints(),
        "repository_state": "CLEAN" if not dirty else "LIVE_DATA_ONLY_DIRTY",
        "dirty_paths": dirty,
    }
    dump(manifest_out, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


def diff_paths(before: Any, after: Any, path: str = "") -> list[str]:
    if type(before) is not type(after):
        return [path or "/"]
    if isinstance(before, dict):
        out: list[str] = []
        for key in sorted(set(before) | set(after)):
            token = str(key).replace("~", "~0").replace("/", "~1")
            out.extend(diff_paths(before.get(key), after.get(key), f"{path}/{token}"))
        return out
    if isinstance(before, list):
        out: list[str] = []
        for i in range(max(len(before), len(after))):
            if i >= len(before) or i >= len(after):
                out.append(f"{path}/{i}")
            else:
                out.extend(diff_paths(before[i], after[i], f"{path}/{i}"))
        return out
    return [] if before == after else [path or "/"]


def row_map(rows: Any) -> dict[str, Any]:
    if not isinstance(rows, list):
        raise ValueError("currency MACRO_SERIES entry must be an array")
    mapped = {row.get("id"): row for row in rows if isinstance(row, dict) and row.get("id")}
    if len(mapped) != len(rows):
        raise ValueError("MACRO_SERIES rows must have unique ids")
    return mapped


def validate_atomic_delta(before_series: dict, after_series: dict, before_heat: dict, after_heat: dict, target: dict) -> dict:
    c, d, series_id = target["currency"], target["dimension"], target["macro_series_id"]
    if set(before_series) != set(after_series):
        raise ValueError("MACRO_SERIES currency coverage changed")
    changed_rows: list[dict[str, Any]] = []
    for currency in sorted(before_series):
        b, a = row_map(before_series[currency]), row_map(after_series[currency])
        for key in sorted(set(b) | set(a)):
            if b.get(key) != a.get(key):
                changed_rows.append({"currency": currency, "macro_series_id": key, "changed_paths": diff_paths(b.get(key), a.get(key))})
    if [x["currency"] for x in changed_rows] != [c] or [x["macro_series_id"] for x in changed_rows] != [series_id]:
        raise ValueError(f"non-atomic MACRO_SERIES delta: {changed_rows}")

    detail = "unemployment" if d == "labour" else "inflation"
    changed_cells = diff_paths(before_heat, after_heat)
    allowed_prefixes = (f"/currencies/{c}/{d}", f"/currencies/{c}/as_of_detail/{detail}")
    forbidden = [p for p in changed_cells if not p.startswith(allowed_prefixes)]
    if forbidden:
        raise ValueError(f"non-atomic heatmap delta: {forbidden}")
    if not changed_cells:
        raise ValueError("refresh did not change heatmap")
    return {"changed_rows": changed_rows, "changed_heatmap_cells": changed_cells}


def candidate_from_after(after_series: dict, after_heat: dict, target: dict) -> dict:
    c, d, series_id = target["currency"], target["dimension"], target["macro_series_id"]
    rows = row_map(after_series[c])
    row = rows.get(series_id)
    if not isinstance(row, dict) or not row.get("dates") or not row.get("values"):
        raise ValueError("target after row missing dates/values")
    if len(row["dates"]) != len(row["values"]):
        raise ValueError("target after row has mismatched dates/values")
    heat = after_heat.get("currencies", {}).get(c, {}).get(d)
    if not isinstance(heat, dict):
        raise ValueError("target after heatmap entry missing")
    candidate = {
        "currency": c, "dimension": d, "macro_series_id": series_id,
        "observation_date": row["last_date"], "value": row["last_value"],
        "source": heat["source"], "series_id": heat["series_id"],
        "frequency": heat["frequency"], "transformation": heat["transformation"],
    }
    if row.get("unit") is not None:
        candidate["unit"] = row["unit"]
    return candidate


def verify(args: argparse.Namespace) -> int:
    evidence_dir = pathlib.Path(args.evidence_dir).resolve()
    bs, bh, bm = snapshot_paths(evidence_dir, "before")
    aas, ah, am = snapshot_paths(evidence_dir, "after")
    before_meta, after_meta = load(bm), load(am)
    assert_snapshot_integrity(before_meta, bs, bh)
    assert_snapshot_integrity(after_meta, aas, ah)
    if before_meta.get("target") != after_meta.get("target"):
        raise ValueError("BEFORE and AFTER target identities differ")
    target = before_meta["target"]
    if target != {"currency": args.currency, "dimension": args.dimension, "macro_series_id": args.macro_series_id}:
        raise ValueError("command target differs from captured target")
    if before_meta.get("protected_fingerprints") != after_meta.get("protected_fingerprints"):
        raise ValueError("engine/source infrastructure fingerprint changed between snapshots")
    if before_meta.get("repository_state") != "CLEAN":
        raise ValueError("BEFORE capture must originate from a clean repository")
    allowed_live_dirty = {SERIES_REL.as_posix(), HEAT_REL.as_posix()}
    if after_meta.get("repository_state") not in {"CLEAN", "LIVE_DATA_ONLY_DIRTY"} or not set(after_meta.get("dirty_paths", [])).issubset(allowed_live_dirty):
        raise ValueError("AFTER capture repository state is not restricted to the two live artifacts")
    changed_rules = subprocess.run(
        ["git", "diff", "--quiet", before_meta["git_head"], after_meta["git_head"], "--", *[str(p) for p in PROTECTED_PATHS],
        cwd=ROOT,
    ).returncode != 0
    if changed_rules:
        raise ValueError("engine/source infrastructure changed in Git between anchors")

    before_series, before_heat = load(bs), load(bh)
    after_series, after_heat = load(aas), load(ah)
    delta = validate_atomic_delta(before_series, after_series, before_heat, after_heat, target)
    candidate = candidate_from_after(after_series, after_heat, target)
    if args.candidate:
        supplied = load(pathlib.Path(args.candidate))
        keys = ("currency", "dimension", "macro_series_id", "observation_date", "value", "source", "series_id", "frequency", "transformation")
        mismatch = {k: (supplied.get(k), candidate.get(k)) for k in keys if supplied.get(k) != candidate.get(k)}
        if mismatch:
            raise ValueError(f"candidate does not describe AFTER artifact: {mismatch}")

    live_before = {str(SERIES_REL): sha256_file(ROOT / SERIES_REL), str(HEAT_REL): sha256_file(ROOT / HEAT_REL)}
    with tempfile.TemporaryDirectory(prefix="gmfq-macro-pit-") as tmp:
        temp = pathlib.Path(tmp)
        candidate_path = temp / "candidate.json"
        dump(candidate_path, candidate)
        command = [sys.executable, str(ROOT / "validation/build_macro_candidate.py"), "--candidate", str(candidate_path),
                   "--series-input", str(bs), "--heatmap-input", str(bh), "--output-dir", str(temp / "replay")]
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        if proc.returncode:
            raise ValueError(f"builder replay failed: {proc.stderr or proc.stdout}")
        replay_series, replay_heat = load(temp / "replay" / SERIES_NAME), load(temp / "replay" / HEAT_NAME)
        builder_summary = load(temp / "replay" / "summary.json")
    live_after = {str(SERIES_REL): sha256_file(ROOT / SERIES_REL), str(HEAT_REL): sha256_file(ROOT / HEAT_REL)}
    live_written = live_before != live_after
    exact_series, exact_heat = replay_series == after_series, replay_heat == after_heat
    evidence = {
        "schema": "GMFQ_MACRO_PIT_ANCHOR_EVIDENCE_V1", "status": "PASS" if exact_series and exact_heat and not live_written else "FAIL",
        "target": target, "candidate": candidate,
        "anchor": {"before_git_head": before_meta["git_head"], "after_git_head": after_meta["git_head"],
                   "before_sha256": before_meta["artifacts"], "after_sha256": after_meta["artifacts"]},
        "atomic_delta": delta, "macro_series_exact_match": exact_series, "heatmap_exact_match": exact_heat,
        "live_data_written_by_replay": live_written, "engine_or_source_infrastructure_changed": False,
        "registry_promotion": "NOT_ATTEMPTED", "builder_summary": builder_summary,
    }
    output = pathlib.Path(args.evidence_output).resolve() if args.evidence_output else evidence_dir / "macro_pit_anchor_evidence.json"
    dump(output, evidence)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if evidence["status"] == "PASS" else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Atomic one-series macro PIT anchor contract")
    sub = ap.add_subparsers(dest="command", required=True)
    for phase in ("before", "after"):
        cp = sub.add_parser(f"capture-{phase}")
        cp.add_argument("--evidence-dir", required=True)
        cp.add_argument("--currency", required=True)
        cp.add_argument("--dimension", required=True, choices=("inflation", "labour"))
        cp.add_argument("--macro-series-id", required=True)
        cp.add_argument("--allow-live-data-dirty", action="store_true", help="AFTER only: permit uncommitted changes limited to the two captured live artifacts")
        cp.add_argument("--overwrite", action="store_true")
        cp.set_defaults(phase=phase, func=capture)
    vp = sub.add_parser("verify")
    vp.add_argument("--evidence-dir", required=True)
    vp.add_argument("--currency", required=True)
    vp.add_argument("--dimension", required=True, choices=("inflation", "labour"))
    vp.add_argument("--macro-series-id", required=True)
    vp.add_argument("--candidate")
    vp.add_argument("--evidence-output")
    vp.set_defaults(func=verify)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        raise
