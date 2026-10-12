#!/usr/bin/env python3
"""Build the fail-closed, descriptive Bank Research dashboard sidecar."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path("validation/BANK_RESEARCH_LAYER_CONTRACT_V1_2026-10-12.json")
SOURCE_PATH = Path("live_data/sections/NATIVE_CB_DATA.json")
OUTPUT_PATH = Path("live_data/sections/BANK_RESEARCH_STATE.json")


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build(contract: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    if contract.get("schema") != "GMFQ_BANK_RESEARCH_LAYER_CONTRACT_V1":
        raise SystemExit("unexpected Bank Research contract schema")
    publication = contract.get("publication")
    if not isinstance(publication, dict) or any((
        publication.get("state") != "INFORMATIONAL_ONLY",
        publication.get("decision_weight") != 0,
        publication.get("may_modify_pair_bias") is not False,
        publication.get("may_modify_currency_score") is not False,
        publication.get("may_modify_sizing") is not False,
        publication.get("may_create_direction") is not False,
        publication.get("may_infer_missing_data") is not False,
    )):
        raise SystemExit("Bank Research publication contract must remain zero-weight and non-directional")

    required = contract["source"]["required_currencies"]
    if set(source) != set(required):
        raise SystemExit("Bank Research source currency coverage mismatch")

    records = []
    for currency in required:
        row = source[currency]
        pricing = row.get("market_pricing")
        if not isinstance(pricing, dict):
            raise SystemExit(f"{currency}: missing market_pricing object")
        required_row = ("bank", "last_date", "action", "next_meeting", "pricing_tier")
        required_pricing = ("as_of", "instrument", "quality", "freshness_status")
        if any(row.get(field) is None for field in required_row):
            raise SystemExit(f"{currency}: missing required observed central-bank field")
        if any(pricing.get(field) is None for field in required_pricing):
            raise SystemExit(f"{currency}: missing required market-pricing provenance field")
        records.append({
            "currency": currency,
            "bank": row["bank"],
            "last_decision_date": row["last_date"],
            "observed_policy_action": row["action"],
            "next_meeting": row["next_meeting"],
            "pricing_tier": row["pricing_tier"],
            "market_pricing": {
                "as_of": pricing["as_of"],
                "instrument": pricing["instrument"],
                "quality": pricing["quality"],
                "freshness_status": pricing["freshness_status"],
            },
        })

    return {
        "schema": "GMFQ_BANK_RESEARCH_STATE_V1",
        "as_of": contract["as_of"],
        "state": publication["state"],
        "reason": "Observed central-bank and pricing provenance only; no research direction is generated.",
        "decision_weight": 0,
        "may_modify_pair_bias": False,
        "may_modify_currency_score": False,
        "may_modify_sizing": False,
        "may_create_direction": False,
        "source_record_count": len(records),
        "records": records,
    }


def canonical_text(state: dict[str, Any]) -> str:
    return json.dumps(state, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--source", type=Path, default=SOURCE_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    expected = canonical_text(build(load(args.contract), load(args.source)))
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != expected:
            raise SystemExit("Bank Research state drift detected; regenerate with build_bank_research_state_v1.py")
        print(json.dumps({"verdict": "PASS_BANK_RESEARCH_STATE_NO_DRIFT"}))
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
