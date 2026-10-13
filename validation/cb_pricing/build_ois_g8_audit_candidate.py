#!/usr/bin/env python3
"""Build a non-promoting OIS runtime metadata candidate from the G8 source audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OIS = ROOT / "live_data" / "sections" / "OIS_DATA.json"
AUDIT = ROOT / "validation" / "cb_pricing" / "OIS_G8_SOURCE_AUDIT_V2_2026-10-13.json"
G8 = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    runtime = json.loads(OIS.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    audited = audit["currencies"]
    if sorted(audited) != sorted(G8):
        raise SystemExit("audit does not cover exactly the G8 universe")
    active = [ccy for ccy in G8 if runtime["currencies"][ccy]["status"] == "ACTIVE"]
    withheld = [ccy for ccy in G8 if runtime["currencies"][ccy]["status"] == "WITHHELD"]
    if active != audit["result"]["active"] or withheld != audit["result"]["withheld"]:
        raise SystemExit("audit/runtime status disagreement")
    runtime["g8_comparability"] = {
        "status": "WITHHELD_NOT_FULL_G8",
        "audit_as_of": audit["as_of_audit"],
        "audit_reference": "validation/cb_pricing/OIS_G8_SOURCE_AUDIT_V2_2026-10-13.json",
        "active": active,
        "withheld": withheld,
        "relative_pair_vote": False,
        "publication_permitted": False,
        "rule": "No G8 relative OIS vote until every currency has reproducible same-basis current, T-1 and source-specific T-5 PIT evidence.",
    }
    # Preserve the compact runtime representation so this certification-only
    # metadata change does not create unrelated payload formatting drift.
    args.output.write_text(json.dumps(runtime, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"status": "PASS", "active": active, "withheld": withheld, "publication_permitted": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
