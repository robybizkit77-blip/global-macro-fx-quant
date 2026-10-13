#!/usr/bin/env python3
"""Fail-closed finalization contracts for non-core dashboard lanes.

This is deliberately a *classification* gate.  It proves that every one of
the 28 cross frames has an explicit status and that an unavailable optional
lane is propagated as WITHHELD, rather than being silently turned into a
signal.  A PASS result never authorises publication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from itertools import combinations
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
G8 = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
LIVE = ROOT / "live_data" / "sections"
PAYLOAD = ROOT / "payload"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(root: Path = ROOT) -> dict:
    live = root / "live_data" / "sections"
    payload = root / "payload"
    d = load(live / "D.json")
    cert = load(live / "CERT53.json")
    ois = load(live / "OIS_DATA.json")
    what = live / "WHAT_CHANGED.json"
    themes = live / "TOP_THEMES.json"
    payload_text = b"".join((payload / f"part-{n:02d}.txt").read_bytes() for n in range(16)).decode("utf-8")

    failures: list[str] = []
    # Display orientation is a UI choice (for example EUR/USD versus USD/EUR);
    # integrity is assessed on the unordered G8 cross universe.
    pair_names = {x.get("pair") for x in d.get("pairs", [])}
    pair_sets = {frozenset(name.split("/")) for name in pair_names if name}
    required_pairs = {frozenset((a, b)) for a, b in combinations(G8, 2)}
    cert_names = set(cert.get("pairs", {}))
    cert_sets = {frozenset(name.split("/")) for name in cert_names}
    if pair_sets != required_pairs:
        failures.append("d_pair_universe_not_exact_g8_28")
    if cert_sets != required_pairs:
        failures.append("cert_pair_universe_not_exact_g8_28")

    currencies = ois.get("currencies", {})
    active = sorted(k for k in G8 if currencies.get(k, {}).get("status") == "ACTIVE")
    withheld_ois = sorted(k for k in G8 if k not in active)
    ois_comparable = not withheld_ois and all(
        all(currencies[c].get("validation", {}).get(k) is True
            for k in ("source_validated", "asof_validated", "meeting_path_validated", "changes_validated"))
        for c in G8
    )
    if ois_comparable:
        ois_status = "PRESENT+VALIDATED"
        ois_blocker = None
    else:
        ois_status = "WITHHELD/EXPLICIT"
        ois_blocker = "G8 relative pricing is not comparable: " + ", ".join(withheld_ois)

    risk = d.get("risk", {})
    risk_lanes = {}
    for name in ("WTI", "Gold"):
        # The runtime may display a value, but a value without source identity,
        # as-of and PIT/freshness evidence is never eligible for a pair vote.
        risk_lanes[name] = {
            "status": "WITHHELD/EXPLICIT",
            "runtime_value_present": risk.get(name) is not None,
            "blocker": "No official source identity + freshness/PIT contract; runtime display is context-only.",
            "pair_vote": False,
        }

    static_files = {"what_changed": what, "top_themes": themes}
    static = {
        name: {
            "status": "WITHHELD/EXPLICIT",
            "sha256": digest(path),
            "blocker": "Snapshot narrative has no deterministic builder with certified input lineage and freshness receipt.",
            "pair_vote": False,
        }
        for name, path in static_files.items()
    }
    static["financial_conditions"] = {
        "status": "WITHHELD/EXPLICIT",
        "blocker": "No homogeneous cross-country FCI source registry, PIT contract or relative methodology.",
        "pair_vote": False,
    }
    static["event_risk"] = {
        "status": "WITHHELD/EXPLICIT",
        "runtime_template_present": "EVENT_TEMPLATES" in payload_text,
        "blocker": "Templates are deterministic UI guidance, not a timestamped certified economic-calendar feed.",
        "pair_vote": False,
    }
    static["news_pulse"] = {
        "status": "WITHHELD/EXPLICIT",
        "runtime_marker_present": "NEWS" in payload_text or "NP" in payload_text,
        "blocker": "No licensed/official news feed, item identity, timestamp or refresh receipt.",
        "pair_vote": False,
    }

    bad_pair_fields = []
    for name, frame in cert.get("pairs", {}).items():
        # These fields establish that secondary context cannot cast a mechanical
        # vote.  OIS may be shown, but is labelled withheld at the pair level.
        if frame.get("mechanical_secondary_vote") is not False:
            bad_pair_fields.append(f"{name}:secondary_vote")
        pricing = frame.get("market_pricing_relative")
        if pricing is not None and not str(pricing).startswith(("WITHHELD", "NOT_COMPARABLE")):
            bad_pair_fields.append(f"{name}:ois_not_withheld")
        if frame.get("macro_candidate_overlay_P70", {}).get("mechanical_override") is not False:
            bad_pair_fields.append(f"{name}:macro_overlay")
    if bad_pair_fields:
        failures.append("noncertified_lane_can_influence_pair:" + ",".join(bad_pair_fields))

    report = {
        "schema": "GMFQ_DASHBOARD_FINALIZATION_CONTRACT_V2",
        "publication_permitted": False,
        "validator_green": not failures,
        "failures": failures,
        "layers": {
            "ois_market_pricing_g8": {"status": ois_status, "active": active, "withheld": withheld_ois, "blocker": ois_blocker, "pair_vote": False},
            "wti": risk_lanes["WTI"],
            "gold": risk_lanes["Gold"],
            **static,
        },
        "composite_28_cross": {
            "status": "PASS_WITH_WITHHELD_PROPAGATED" if not failures else "FAIL",
            "expected_pairs": len(required_pairs),
            "d_pairs": len(pair_sets),
            "cert_pairs": len(cert_sets),
            "withheld_layers_propagated": ["ois_market_pricing_g8", "wti", "gold", "financial_conditions", "event_risk", "what_changed", "top_themes", "news_pulse"],
            "noncertified_pair_votes": bad_pair_fields,
        },
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", type=Path)
    args = parser.parse_args()
    report = evaluate()
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.write:
        args.write.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0 if report["validator_green"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
