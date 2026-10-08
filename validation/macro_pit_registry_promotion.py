#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "validation" / "macro" / "MACRO_SOURCE_REGISTRY_2026-10-08.json"


def load(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_evidence(evidence: dict) -> tuple[str, dict, dict]:
    require(evidence.get("schema") == "GMFQ_MACRO_PIT_ANCHOR_EVIDENCE_V1", "unexpected PIT evidence schema")
    require(evidence.get("status") == "PASS", "PIT evidence is not PASS")
    require(evidence.get("macro_series_exact_match") is True, "MACRO_SERIES exact match missing")
    require(evidence.get("heatmap_exact_match") is True, "heatmap exact match missing")
    require(evidence.get("live_data_written_by_replay") is False, "replay wrote live_data")
    require(evidence.get("engine_or_source_infrastructure_changed") is False, "engine/source infrastructure changed")
    require(evidence.get("registry_promotion") == "NOT_ATTEMPTED", "evidence must precede registry promotion")

    target = evidence.get("target")
    candidate = evidence.get("candidate")
    require(isinstance(target, dict), "evidence target missing")
    require(isinstance(candidate, dict), "evidence candidate missing")
    for field in ("currency", "dimension", "macro_series_id"):
        require(bool(target.get(field)), f"target missing {field}")
    require(candidate.get("currency") == target.get("currency"), "candidate currency differs from target")
    require(candidate.get("dimension") == target.get("dimension"), "candidate dimension differs from target")
    require(candidate.get("macro_series_id") == target.get("macro_series_id"), "candidate macro_series_id differs from target")

    delta = evidence.get("atomic_delta")
    require(isinstance(delta, dict), "atomic_delta missing")
    rows = delta.get("changed_rows")
    require(isinstance(rows, list) and len(rows) == 1, "promotion requires exactly one changed MACRO_SERIES row")
    require(rows[0].get("currency") == target.get("currency"), "changed row currency differs from target")
    require(rows[0].get("macro_series_id") == target.get("macro_series_id"), "changed row id differs from target")

    anchor = evidence.get("anchor")
    require(isinstance(anchor, dict), "anchor metadata missing")
    require(bool(anchor.get("before_git_head")) and bool(anchor.get("after_git_head")), "anchor git heads missing")
    return f"{target['currency']}.{target['dimension']}", target, candidate


def evidence_class(evidence: dict) -> tuple[str, dict[str, Any]]:
    bootstrap = evidence.get("bootstrap_provenance")
    if isinstance(bootstrap, dict):
        require(bootstrap.get("official_release_pair_verified") is True, "bootstrap official release pair not verified")
        require(str(bootstrap.get("before_state", "")).startswith("RECONSTRUCTED_"), "bootstrap before state is not explicitly reconstructed")
        return "RECONSTRUCTED_HISTORICAL_REPLAY", {
            "before_state": bootstrap.get("before_state"),
            "after_state": bootstrap.get("after_state"),
            "official_release_pair_verified": True,
            "manifest_sha256": bootstrap.get("manifest_sha256"),
        }
    return "DIRECT_PIT_REPLAY", {}


def build_reference(evidence: dict, target: dict, candidate: dict) -> dict[str, Any]:
    klass, extra = evidence_class(evidence)
    ref = {
        "schema": "GMFQ_MACRO_PIT_CERTIFICATION_REF_V1",
        "evidence_schema": evidence["schema"],
        "evidence_sha256": canonical_sha256(evidence),
        "evidence_class": klass,
        "macro_series_id": target["macro_series_id"],
        "observation_date": candidate.get("observation_date"),
        "value": candidate.get("value"),
        "before_git_head": evidence["anchor"]["before_git_head"],
        "after_git_head": evidence["anchor"]["after_git_head"],
        "promotion_mode": "EXPLICIT_REVIEW_REQUIRED",
    }
    ref.update({k: v for k, v in extra.items() if v is not None})
    return ref


def build_proposal(registry: dict, evidence: dict) -> tuple[dict, dict]:
    key, target, candidate = validate_evidence(evidence)
    series = registry.get("series", {})
    row = series.get(key)
    require(isinstance(row, dict), f"unknown registry target: {key}")
    require(row.get("source_adapter_status") == "READY", f"{key} source adapter is not READY")
    require(row.get("series_id") == candidate.get("series_id"), f"{key} series_id mismatch")
    require(row.get("frequency") == candidate.get("frequency"), f"{key} frequency mismatch")
    require(row.get("transformation") == candidate.get("transformation"), f"{key} transformation mismatch")

    already = row.get("historical_replay_certified") is True
    proposed = copy.deepcopy(registry)
    out_row = proposed["series"][key]
    fresh_ref = build_reference(evidence, target, candidate)
    action = "PROPOSAL_CREATED"

    if not already:
        out_row["historical_replay_certified"] = True
        out_row["historical_replay_evidence"] = fresh_ref
    else:
        existing = out_row.get("historical_replay_evidence")
        require(isinstance(existing, dict), f"{key} certified row is missing historical_replay_evidence")
        require(existing.get("macro_series_id") == target["macro_series_id"], "existing certification target differs")
        require(existing.get("observation_date") == candidate.get("observation_date"), "existing certification observation differs")
        require(float(existing.get("value")) == float(candidate.get("value")), "existing certification value differs")

        # Never silently repin a reviewed evidence hash/head on a later rerun. We may
        # only enrich legacy certification metadata with the provenance class.
        changed = False
        for field in ("evidence_class", "before_state", "after_state", "official_release_pair_verified", "manifest_sha256"):
            if field in fresh_ref and field not in existing:
                existing[field] = fresh_ref[field]
                changed = True
            elif field in fresh_ref and field in existing:
                require(existing[field] == fresh_ref[field], f"existing certification {field} differs")
        action = "METADATA_ENRICHMENT_PROPOSED" if changed else "ALREADY_CERTIFIED"

    receipt = {
        "schema": "GMFQ_MACRO_PIT_REGISTRY_PROMOTION_RECEIPT_V1",
        "status": "PASS",
        "target": key,
        "promotion_action": action,
        "canonical_registry_modified": False,
        "historical_replay_certified_before": bool(row.get("historical_replay_certified")),
        "historical_replay_certified_proposed": True,
        "current_evidence_sha256": canonical_sha256(evidence),
        "evidence_class": evidence_class(evidence)[0],
        "registry_promotion": "REVIEW_REQUIRED",
    }
    return proposed, receipt


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a reviewed registry promotion proposal from one GREEN PIT evidence artifact")
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    ap.add_argument("--proposed-registry", required=True)
    ap.add_argument("--receipt", required=True)
    args = ap.parse_args()

    registry_path = pathlib.Path(args.registry).resolve()
    evidence = load(pathlib.Path(args.evidence).resolve())
    registry = load(registry_path)
    proposed, receipt = build_proposal(registry, evidence)
    dump(pathlib.Path(args.proposed_registry).resolve(), proposed)
    dump(pathlib.Path(args.receipt).resolve(), receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        raise
