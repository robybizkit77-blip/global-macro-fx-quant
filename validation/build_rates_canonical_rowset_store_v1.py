#!/usr/bin/env python3
"""Build and verify compact canonical Rates Temporal-PIT rowsets.

Input artifacts MUST be the exact historical artifacts referenced by the canonical
Rates evidence files. The builder never fetches market data itself: it converts
already-certified A/B materializations into compact CSV snapshots and proves that
the semantic rowset hash remains identical to the canonical evidence hash.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "validation"
STORE = VALIDATION / "rates_pit_rowsets"
MANIFEST = STORE / "manifest_v1.json"

CONFIG = {
    "USD": {
        "artifact_id": 11695909548,
        "artifact_digest": "sha256:9e53dc54ea79dca08afc9ce45b32c2183350d5b06bb42f7f6def6acd85181016",
        "evidence": "USD_RATES_TEMPORAL_PIT_EVIDENCE_V1_2026-10-11.json",
    },
    "EUR": {
        "artifact_id": 11696513178,
        "artifact_digest": "sha256:8ffd5f840c4fd7f0c7dfa5746c1994e3041d9d4b9690882234063418235a7823",
        "evidence": "EUR_RATES_TEMPORAL_PIT_EVIDENCE_V1_2026-10-11.json",
    },
    "JPY": {
        "artifact_id": 11697156816,
        "artifact_digest": "sha256:760bf4e5299aa27bfa7be71dee4cb889a7b56afcebe2a22908d678d9828cbbff",
        "evidence": "JPY_RATES_TEMPORAL_PIT_EVIDENCE_V1_2026-10-11.json",
    },
    "CAD": {
        "artifact_id": 11698400061,
        "artifact_digest": "sha256:152fd875fc276f699c4b460b49b6379746076c8a84c6fd97e1c2202e0e5a9ddb",
        "evidence": "CAD_RATES_TEMPORAL_PIT_EVIDENCE_V1_2026-10-11.json",
    },
    "AUD": {
        "artifact_id": 11698900287,
        "artifact_digest": "sha256:056e0bf91411319704bb54e58e8ea55d892519cba5c8803de62f73694b3b00e7",
        "evidence": "AUD_RATES_TEMPORAL_PIT_EVIDENCE_V1_2026-10-11.json",
    },
}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def semantic_payload(ccy: str, source_basis: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        item = {
            "currency": ccy,
            "observation_date": r["observation_date"],
            "yield_2y": float(r["yield_2y"]),
            "yield_10y": float(r["yield_10y"]),
            "source_basis": source_basis,
        }
        if ccy == "JPY":
            item["first_eligible_decision_point"] = r["first_eligible_decision_point"]
        else:
            item["first_eligible_decision_date"] = r["first_eligible_decision_date"]
        out.append(item)
    return out


def semantic_hash(ccy: str, source_basis: str, rows: list[dict[str, Any]]) -> str:
    payload = semantic_payload(ccy, source_basis, rows)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return sha256_bytes(raw)


def read_artifact(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        required = {"a/evidence.json", "b/evidence.json"}
        if not required.issubset(names):
            raise RuntimeError(f"artifact {path.name} lacks exact A/B evidence files")
        a = json.loads(z.read("a/evidence.json"))
        b = json.loads(z.read("b/evidence.json"))
    if a != b:
        raise RuntimeError(f"A/B certified materializations differ in {path.name}")
    return a, b


def row_columns(ccy: str) -> list[str]:
    cols = ["observation_date", "yield_2y", "yield_10y", "first_eligible_decision_date"]
    if ccy == "JPY":
        cols.append("first_eligible_decision_point")
    return cols


def normalized_rows(ccy: str, runtime_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cols = row_columns(ccy)
    rows = [{k: r[k] for k in cols} for r in runtime_rows]
    dates = [r["observation_date"] for r in rows]
    if not dates or dates != sorted(dates) or len(dates) != len(set(dates)):
        raise RuntimeError(f"{ccy} rowset dates invalid")
    for r in rows:
        if r["first_eligible_decision_date"] <= r["observation_date"]:
            raise RuntimeError(f"{ccy} non-conservative eligibility at {r['observation_date']}")
        if ccy == "JPY" and not r["first_eligible_decision_point"].endswith("+09:00"):
            raise RuntimeError(f"JPY eligibility point lacks JST offset at {r['observation_date']}")
    return rows


def write_csv(path: Path, ccy: str, rows: list[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = row_columns(ccy)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return sha256_bytes(path.read_bytes())


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["yield_2y"] = float(r["yield_2y"])
        r["yield_10y"] = float(r["yield_10y"])
    return rows


def evidence_for(ccy: str) -> dict[str, Any]:
    return json.loads((VALIDATION / CONFIG[ccy]["evidence"]).read_text(encoding="utf-8"))


def build(artifact_dir: Path, artifact_metadata: Path) -> dict[str, Any]:
    metadata = json.loads(artifact_metadata.read_text(encoding="utf-8"))
    STORE.mkdir(parents=True, exist_ok=True)
    entries = {}
    total_rows = 0
    for ccy, cfg in CONFIG.items():
        key = str(cfg["artifact_id"])
        md = metadata.get(key)
        if not isinstance(md, dict):
            raise RuntimeError(f"missing artifact metadata for {ccy}/{key}")
        if md.get("digest") != cfg["artifact_digest"]:
            raise RuntimeError(f"artifact metadata digest mismatch for {ccy}")
        artifact = artifact_dir / f"{ccy.lower()}.zip"
        runtime, _ = read_artifact(artifact)
        evidence = evidence_for(ccy)
        if runtime.get("target") != evidence.get("target"):
            raise RuntimeError(f"target mismatch for {ccy}")
        if runtime.get("semantic_rowset_sha256") != evidence.get("semantic_rowset_sha256"):
            raise RuntimeError(f"runtime/evidence semantic hash mismatch for {ccy}")
        runtime_rows = runtime.get("rows")
        if not isinstance(runtime_rows, list):
            raise RuntimeError(f"runtime rows missing for {ccy}")
        rows = normalized_rows(ccy, runtime_rows)
        source_basis = runtime_rows[0]["source_basis"]
        h = semantic_hash(ccy, source_basis, rows)
        if h != evidence["semantic_rowset_sha256"]:
            raise RuntimeError(f"normalized semantic hash mismatch for {ccy}: {h}")
        cov = evidence["coverage"]
        if len(rows) != cov["observations"]:
            raise RuntimeError(f"row count mismatch for {ccy}")
        if rows[-1]["observation_date"] != cov["end_date"]:
            raise RuntimeError(f"end date mismatch for {ccy}")
        expected_start = cov.get("start_date")
        if expected_start and rows[0]["observation_date"] != expected_start:
            raise RuntimeError(f"start date mismatch for {ccy}")
        if cov.get("start_year") and not rows[0]["observation_date"].startswith(str(cov["start_year"]) + "-"):
            raise RuntimeError(f"start year mismatch for {ccy}")
        file_name = f"{ccy.lower()}_rates_2y_10y_temporal_pit_v1.csv"
        file_path = STORE / file_name
        file_hash = write_csv(file_path, ccy, rows)
        entries[ccy] = {
            "target": evidence["target"],
            "authority": evidence["authority"],
            "source_basis": source_basis,
            "rowset_file": f"validation/rates_pit_rowsets/{file_name}",
            "rowset_file_sha256": file_hash,
            "semantic_rowset_sha256": h,
            "observations": len(rows),
            "start_date": rows[0]["observation_date"],
            "end_date": rows[-1]["observation_date"],
            "columns": row_columns(ccy),
            "canonical_evidence": f"validation/{cfg['evidence']}",
            "certified_artifact_id": cfg["artifact_id"],
            "certified_artifact_digest": cfg["artifact_digest"],
            "a_b_materializations_exactly_identical": True,
        }
        total_rows += len(rows)

    manifest = {
        "schema": "GMFQ_RATES_CANONICAL_ROWSET_STORE_V1",
        "status": "PASS",
        "purpose": "Immutable normalized snapshots of the exact certified Rates Temporal-PIT artifact rowsets for deterministic backtest row selection.",
        "policy": {
            "official_certified_artifacts_only": True,
            "artifact_digest_must_match_canonical_evidence": True,
            "a_b_materializations_must_match_exactly": True,
            "semantic_hash_must_match_canonical_evidence": True,
            "runtime_history_fallback_allowed": False,
            "secondary_source_fallback_allowed": False,
            "same_day_use_allowed": False,
            "store_updates_require_new_certification": True,
        },
        "currencies": sorted(entries),
        "total_observations": total_rows,
        "entries": entries,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def verify() -> dict[str, Any]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("schema") != "GMFQ_RATES_CANONICAL_ROWSET_STORE_V1" or manifest.get("status") != "PASS":
        raise RuntimeError("invalid Rates rowset store manifest")
    total = 0
    for ccy in manifest.get("currencies", []):
        entry = manifest["entries"][ccy]
        path = ROOT / entry["rowset_file"]
        if sha256_bytes(path.read_bytes()) != entry["rowset_file_sha256"]:
            raise RuntimeError(f"canonical file hash mismatch for {ccy}")
        evidence = evidence_for(ccy)
        rows = read_csv(path)
        if len(rows) != entry["observations"]:
            raise RuntimeError(f"canonical row count mismatch for {ccy}")
        h = semantic_hash(ccy, entry["source_basis"], rows)
        if h != entry["semantic_rowset_sha256"] or h != evidence["semantic_rowset_sha256"]:
            raise RuntimeError(f"canonical semantic hash mismatch for {ccy}")
        if rows[0]["observation_date"] != entry["start_date"] or rows[-1]["observation_date"] != entry["end_date"]:
            raise RuntimeError(f"canonical coverage mismatch for {ccy}")
        total += len(rows)
    if total != manifest.get("total_observations"):
        raise RuntimeError("canonical total observation count mismatch")
    return {
        "schema": "GMFQ_RATES_CANONICAL_ROWSET_STORE_VERIFICATION_V1",
        "status": "VERIFIED",
        "currencies": manifest["currencies"],
        "total_observations": total,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--artifact-dir", type=Path, required=True)
    b.add_argument("--artifact-metadata", type=Path, required=True)
    sub.add_parser("verify")
    args = ap.parse_args()
    result = build(args.artifact_dir, args.artifact_metadata) if args.command == "build" else verify()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
