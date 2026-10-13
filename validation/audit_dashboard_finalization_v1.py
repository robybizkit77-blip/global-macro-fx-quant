#!/usr/bin/env python3
"""Audit the dashboard as a product, not just the current data orchestrator.

The program intentionally returns a successful process when the inventory is
consistent.  A successful audit run means that the dashboard's actual scope
and gaps are reported faithfully; it does *not* mean the dashboard is ready
for automatic publication.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from check_dashboard_finalization_contracts_v2 import evaluate as evaluate_finalization_v2


ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "live_data" / "sections"
PAYLOAD = ROOT / "payload"
WORKFLOW = ROOT / ".github" / "workflows" / "daily-data-orchestrator-v1.yml"

VALID = {
    "PRESENT+VALIDATED",
    "PRESENT+NOT VALIDATED",
    "PLANNED/NOT WIRED",
    "WITHHELD/HARD BLOCKER",
    "WITHHELD/EXPLICIT",
    "OUT OF SCOPE BY DESIGN",
}


def read_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def has_all(text: str, *needles: str) -> bool:
    return all(needle in text for needle in needles)


def row(name: str, status: str, data: str, contract: str, workflow: str, ui: str, finding: str) -> dict:
    assert status in VALID
    return {
        "component": name,
        "status": status,
        "data_or_implementation": data,
        "contract_or_validation": contract,
        "workflow": workflow,
        "ui_or_runtime": ui,
        "finding": finding,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", type=Path, help="Optional path for the immutable audit receipt")
    args = parser.parse_args()

    failures: list[str] = []
    payload_parts = [(PAYLOAD / f"part-{i:02d}.txt").read_bytes() for i in range(16)]
    payload_bytes = b"".join(payload_parts)
    payload = payload_bytes.decode("utf-8")
    manifest = read_json(ROOT / "live_data" / "manifest.v2.json")
    d = read_json(LIVE / "D.json")
    cert = read_json(LIVE / "CERT53.json")
    rates = read_json(LIVE / "NATIVE_RATES_DATA.json")
    ois = read_json(LIVE / "OIS_DATA.json")
    liq = read_json(LIVE / "NATIVE_LIQ_DATA.json")
    workflow_text = WORKFLOW.read_text(encoding="utf-8")
    contracts_v2 = evaluate_finalization_v2(ROOT)
    if not contracts_v2["validator_green"]:
        failures.extend(f"finalization_v2:{x}" for x in contracts_v2["failures"])

    if manifest.get("status") != "PASS":
        failures.append("manifest_v2_not_pass")
    if manifest.get("runtime_sha256") != hashlib.sha256(payload_bytes).hexdigest():
        failures.append("runtime_manifest_byte_hash_mismatch")
    if any(b"\r\n" in part for part in payload_parts):
        failures.append("runtime_contains_crlf_despite_content_addressed_contract")
    if sorted(d.get("currencies", [])) != sorted(rates):
        failures.append("rates_currency_universe_drift")
    if len(d.get("pairs", {})) != 28 or len(cert.get("pairs", {})) != 28:
        failures.append("not_exactly_28_g8_crosses")
    if not has_all(payload, "risk['WTI']", "risk['Gold']", "risk['China CLI']"):
        failures.append("risk_inputs_not_visualized")
    if not has_all(workflow_text, "fetch_cboe_vix_candidate.py", "fetch_eia_brent_probe.py"):
        failures.append("risk_certification_contract_missing")
    if any(x in workflow_text for x in ("fetch_wti", "fetch_gold", "fetch_china")):
        failures.append("risk_audit_registry_needs_update_for_new_source")

    statuses = {c: v.get("status") for c, v in liq.items()}
    for currency in ("CHF", "JPY"):
        if currency not in statuses:
            failures.append(f"missing_liquidity_currency:{currency}")

    matrix = [
        row("Macro core (growth, labour, inflation, cycle)", "PRESENT+VALIDATED",
            "live_data/sections/MACRO_THERMOMETER_DATA.json; MACRO_SERIES.json; D.json",
            "validation/macro/check_macro_source_registry.py; strict PIT receipts",
            "macro-final-apply-gate-v1.yml; daily-data-orchestrator-v1.yml",
            "Macro Lab / currency cards / CERT53", "Canonical macro lane is in the final gate."),
        row("Rates: 2Y, 10Y, 10Y-2Y and front-end impulse", "PRESENT+VALIDATED",
            "live_data/sections/NATIVE_RATES_DATA.json; RATES_AUDIT_METADATA.json",
            "validation/build_rates_audit_metadata.py; temporal PIT receipts",
            "rates-daily-operational.yml; daily-data-orchestrator-v1.yml",
            "Rates cards and CERT53.rates_components", "2Y, 10Y and curve remain separate diagnostics."),
        row("Rates decomposition: real yields, breakevens, term premium, fiscal/supply", "PLANNED/NOT WIRED",
            "NATIVE_RATES_DATA has nullable real/breakeven/term_premium fields",
            "No source registry or freshness/PIT contract for this decomposition",
            "None", "v401DecompCards renders 'Non comparabile' when absent", "Educational UI exists; no validated dataset or fiscal-stress model is wired."),
        row("Central banks: realized decisions and guidance", "PRESENT+VALIDATED",
            "live_data/sections/NATIVE_CB_DATA.json",
            "CB decision/source checks embedded in the canonical runtime and lane receipts",
            "cb-pricing-daily-operational.yml; daily-data-orchestrator-v1.yml",
            "Central-bank panel and CERT53.central_bank_realized_direction", "Realized policy is distinct from forward market pricing."),
        row("Market pricing / OIS", "WITHHELD/EXPLICIT",
            "live_data/sections/OIS_DATA.json; NATIVE_CB_DATA.market_pricing",
            "Source readiness exists, but OIS_DATA.status is PARTIAL_REAL_INGEST",
            "cb-pricing-active-orchestrator.yml; cb-pricing-daily-operational.yml",
            "OIS panel; pair frames explicitly label non-comparable forward pricing WITHHELD", "Explicitly withheld by V2 contract: partial G8 coverage prevents a comparable relative 28-cross signal."),
        row("Bank research", "OUT OF SCOPE BY DESIGN",
            "No bank-research dataset, adapter or UI section in this branch",
            "No contract", "None", "None", "The repository does not claim this as a sourced lane; no proxy is substituted."),
        row("Liquidity", "WITHHELD/HARD BLOCKER",
            "live_data/sections/NATIVE_LIQ_DATA.json",
            "validation/liquidity/* source policy and provenance resolutions",
            "daily-data-orchestrator-v1.yml",
            "Liquidity/secondary context in Macro Lab and pair narratives", "Exact withheld inputs: CHF.liquidity and JPY.liquidity."),
        row("Credit", "WITHHELD/HARD BLOCKER",
            "live_data/sections/NATIVE_LIQ_DATA.json",
            "validation/liquidity/CHF_CREDIT_PROVENANCE_RESOLUTION_2026-10-13.json",
            "daily-data-orchestrator-v1.yml",
            "Liquidity/credit secondary context", "Exact withheld input: CHF.credit."),
        row("Financial conditions", "WITHHELD/EXPLICIT",
            "Secondary-sector narratives in CERT53 and payload runtime",
            "No standalone cross-country FCI source registry, PIT contract or final-gate lane",
            "dashboard finalization contracts V2", "Macro Lab / pair secondary context", "Explicitly withheld from pair voting: no homogeneous FCI source registry or PIT contract."),
        row("Global risk: VIX", "PRESENT+VALIDATED",
            "D.json.risk.VIX",
            "validation/fetch_cboe_vix_candidate.py",
            "daily-data-orchestrator-v1.yml", "Risk panel / marketContext", "Official-source probe is fail-closed and non-mutating."),
        row("Global risk: Brent", "WITHHELD/HARD BLOCKER",
            "D.json.risk.Brent",
            "validation/check_risk_brent_hard_blocker_v1.py; RISK_SOURCE_POLICY_V1",
            "risk-brent-hard-blocker-contract-v1.yml; daily-data-orchestrator-v1.yml",
            "Risk panel / marketContext", "Canonical EIA spot does not meet the one-business-day freshness gate; no equivalent proxy is used."),
        row("Global risk: WTI", "WITHHELD/EXPLICIT",
            "D.json.risk.WTI",
            "No WTI official-source freshness/PIT contract found",
            "dashboard finalization contracts V2", "marketContext and risk UI", "Runtime value is context-only; no official source identity and freshness/PIT contract exists."),
        row("Global risk: Gold", "WITHHELD/EXPLICIT",
            "D.json.risk.Gold",
            "No gold official-source freshness/PIT contract found",
            "dashboard finalization contracts V2", "marketContext and risk UI", "Runtime value is context-only; no official source identity and freshness/PIT contract exists."),
        row("Global risk: China proxy / China macro confirmation", "PLANNED/NOT WIRED",
            "D.json.risk['China CLI'] only",
            "No China CLI/PMI source registry, release contract or confirmation rule found",
            "None", "marketContext and risk UI", "A China CLI display exists; distinct China macro confirmation does not."),
        row("COT / positioning", "PRESENT+VALIDATED",
            "V250_COT_CHART_DATA.json; V247_COT_STORIES.json; D.json.cot",
            "validation/build_cot_candidate.py; build_cot_stories.py",
            "cot-weekly-operational.yml", "COT map, stories and pair divergence fields", "Stocks, flow and concentration warnings are present; role remains context/early warning."),
        row("Price / market confirmation", "PRESENT+VALIDATED",
            "D.json.prices and Price runtime overlay",
            "PRICE_ECB_CONTROLLED_APPLY_CONTRACT_V1_2026-10-13.json",
            "price-ecb-controlled-apply-contract-v1.yml; daily-data-orchestrator-v1.yml", "Pair cards and CERT53.price_state", "Controlled apply is proven; automatic publication remains disabled."),
        row("Event risk", "WITHHELD/EXPLICIT",
            "EVENT_TEMPLATES in payload runtime",
            "Risk/event isolation test proves non-contamination only; no economic-calendar source contract",
            "dashboard finalization contracts V2", "Event Risk cards", "Template is verified as static UI guidance, explicitly withheld as a live calendar feed."),
        row("What Changed", "WITHHELD/EXPLICIT",
            "live_data/sections/WHAT_CHANGED.json",
            "Manifest integrity only; no dedicated freshness/content provenance contract",
            "dashboard finalization contracts V2", "What Changed ribbon/cards", "Snapshot hash is recorded, but no deterministic builder/current-input lineage exists."),
        row("Top Themes", "WITHHELD/EXPLICIT",
            "live_data/sections/TOP_THEMES.json",
            "Manifest integrity only; no dedicated source/provenance contract",
            "dashboard finalization contracts V2", "Top Themes section", "Snapshot hash is recorded, but no deterministic builder/current-input lineage exists."),
        row("News Pulse", "WITHHELD/EXPLICIT",
            "Runtime NEWS/NP arrays in payload",
            "No news-source registry, timestamp contract or live refresh validator",
            "dashboard finalization contracts V2", "News Pulse section", "Explicitly withheld: no feed identity, timestamp or refresh receipt."),
        row("Pair logic across 28 G8 crosses", "PRESENT+VALIDATED",
            "CERT53.json.pairs (28); D.json.pairs/pairStates (28)",
            "validation/check_dashboard_finalization_contracts_v2.py; exact G8 universe + withheld propagation",
            "dashboard-finalization-audit-v1.yml", "Pair decision frames and dashboard pair cards", "Dedicated composite gate verifies all 28 frames and rejects non-certified mechanical votes; publication stays false."),
        row("Rebuild / manifest", "PRESENT+VALIDATED",
            "live_data/manifest.v2.json and 16 payload parts",
            "check_live_update_contract.py; rebuild_live_data_runtime.py --verify-only",
            "live-update-preflight-v1.yml; daily-data-orchestrator-v1.yml", "Browser payload loader", "Current payload hash/sections are verified without mutation."),
        row("Publication", "WITHHELD/HARD BLOCKER",
            "No live-data or GitHub Pages promotion from this branch",
            "Final gate explicitly requires publishable=false",
            "daily-data-orchestrator-v1.yml", "N/A", "Automatic publication remains prohibited until this audit's residuals are closed and a release decision is made."),
    ]

    counts = {status: sum(r["status"] == status for r in matrix) for status in sorted(VALID)}
    report = {
        "schema": "GMFQ_DASHBOARD_FINALIZATION_AUDIT_V1",
        "audit_scope": "conceptual framework -> data -> validation -> workflow -> UI",
        "audit_is_green": False,
        "publication_permitted": False,
        "inventory_consistent": not failures,
        "failures": failures,
        "observed": {
            "currencies": d.get("currencies"),
            "pair_count": len(d.get("pairs", {})),
            "cert_pair_count": len(cert.get("pairs", {})),
            "manifest_status": manifest.get("status"),
            "ois_status": ois.get("status"),
            "liquidity_statuses": statuses,
            "risk_workflow_scope": ["VIX", "Brent"],
            "finalization_contract_v2": contracts_v2,
            "runtime_sha256": hashlib.sha256(payload_bytes).hexdigest(),
        },
        "classification_counts": counts,
        "matrix": matrix,
        "resolved_this_revision": [
            "OIS, WTI, Gold, Financial Conditions, Event Risk, What Changed, Top Themes and News Pulse have explicit fail-closed status and cannot cast a pair vote.",
            "28-cross composite contract proves the exact G8 cross universe and withheld propagation.",
        ],
        "remaining_blockers": [
            "CHF.liquidity official provenance/mapping",
            "CHF.credit official provenance/mapping",
            "JPY.liquidity official provenance/mapping",
            "Brent timely semantically-equivalent official source or approved gate change",
            "China macro confirmation (separate from CLI) source and rule",
            "Long-end decomposition: real yield, breakeven, term premium and fiscal/supply methodology",
            "Full comparable OIS/market-pricing coverage for the G8 universe",
            "Explicit release approval before any publication is enabled",
        ],
        "minimum_path_to_green": [
            "Resolve the four existing hard blockers without proxies.",
            "Keep WTI/Gold/Financial Conditions/Event/What Changed/Top Themes/News Pulse fail-closed unless their separate source contracts are added; they cannot affect the decision lane.",
            "Choose and implement the long-end decomposition methodology; keep null values until it has a source/PIT contract.",
            "Promote OIS only when each active currency has comparable, time-aligned forward data.",
            "Obtain a live calendar/news/narrative lineage only if those UI components are to become release-critical; otherwise retain their explicit withheld status.",
            "Require a manual release approval; do not auto-publish from this audit.",
        ],
    }
    output = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.write:
        args.write.write_text(output, encoding="utf-8")
    print(output)
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
