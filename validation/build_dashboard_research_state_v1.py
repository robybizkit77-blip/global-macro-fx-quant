#!/usr/bin/env python3
"""Deterministically derive the dashboard research sidecar from the canonical registry.

This builder is intentionally fail-closed. It supports the current non-production
research states only. If a registry entry becomes production-authorized, generation
stops and requires a separate promotion change to the dashboard publication contract.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path("validation/RESEARCH_CANDIDATE_REGISTRY_V1_2026-10-12.json")
OUTPUT_PATH = Path("live_data/sections/RESEARCH_STATE.json")

CONTEXT_LABELS = {
    "INFORMATIVE_ONLY": "INFORMATIVO",
    "CANDIDATE_FORWARD_WAITING": "IN VALIDAZIONE",
    "FORWARD_CONFLUENCE_WAITING": "CONFLUENZA IN VALIDAZIONE",
    "VALIDATED_PENDING_PROMOTION": "VALIDATO / IN ATTESA PROMOZIONE",
}
CONTEXT_STATUSES = set(CONTEXT_LABELS)
EXCLUDED_STATUSES = {"FALSIFIED"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_state(registry: dict[str, Any]) -> dict[str, Any]:
    if registry.get("schema") != "GMFQ_RESEARCH_CANDIDATE_REGISTRY_V1":
        raise SystemExit("unexpected research registry schema")

    entries = registry.get("entries")
    if not isinstance(entries, list):
        raise SystemExit("registry entries must be a list")

    production = []
    context_only = []
    excluded = []

    for entry in entries:
        status = entry.get("status")
        prod = entry.get("production_signal_authorized") is True
        sizing = entry.get("sizing_authorized") is True

        if status == "PRODUCTION_AUTHORIZED" or prod or sizing:
            production.append(entry)
            continue
        if status in CONTEXT_STATUSES:
            context_only.append({
                "id": entry["id"],
                "layer": entry["layer"],
                "ui_label": CONTEXT_LABELS[status],
                "status": status,
                "decision_weight": 0,
            })
            continue
        if status in EXCLUDED_STATUSES:
            excluded.append(entry)
            continue
        raise SystemExit(f"unknown/unpublishable research status: {status!r}")

    # Promotion must be an explicit contract change; never silently change the live
    # dashboard from WITHHELD to production just because a registry field changed.
    if production:
        ids = ", ".join(str(x.get("id")) for x in production)
        raise SystemExit(
            "production-authorized research detected; separate dashboard promotion "
            f"contract required before sidecar generation: {ids}"
        )

    return {
        "schema": "GMFQ_DASHBOARD_RESEARCH_STATE_V1",
        "as_of": registry.get("as_of"),
        "research_signal_state": "WITHHELD",
        "reason": "No research entry is production-authorized.",
        "decision_signal_count": 0,
        "sizing_authorized_count": 0,
        "context_only_count": len(context_only),
        "excluded_count": len(excluded),
        "decision_weight": 0,
        "may_modify_pair_bias": False,
        "may_modify_currency_score": False,
        "may_modify_sizing": False,
        "context_only": context_only,
    }


def canonical_text(state: dict[str, Any]) -> str:
    return json.dumps(state, indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if committed sidecar drifts")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    state = build_state(load_json(REGISTRY_PATH))
    expected = canonical_text(state)

    if args.check:
        if not args.output.exists():
            raise SystemExit(f"missing generated sidecar: {args.output}")
        actual = args.output.read_text(encoding="utf-8")
        if actual != expected:
            raise SystemExit(
                "dashboard research state drift detected; regenerate with "
                "python validation/build_dashboard_research_state_v1.py"
            )
        print(json.dumps({
            "verdict": "PASS_DASHBOARD_RESEARCH_STATE_NO_DRIFT",
            "registry_entries": len(load_json(REGISTRY_PATH)["entries"]),
            "context_only": len(state["context_only"]),
            "excluded": state["excluded_count"],
            "decision_signals": state["decision_signal_count"],
            "decision_weight": state["decision_weight"],
        }, indent=2))
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
