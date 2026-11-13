#!/usr/bin/env python3
"""Fail-closed *source contract* for mirroring the approved V2 website.

This is not a market-freshness or FX signal certification. It ensures four
research data surfaces are parseable, source-labelled and quarantined from Core
before the Git-tracked V2 subtree is copied to gh-pages. Narrative regressions
remain separately tested; date-fixed unit fixtures must not block a verified
data-only mirror of main.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REL = Path("site/fx-quant-v2")
G8 = {"USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD"}
FILES = {
    "ois-pricing-snapshot.json": "GMFQ_FXV2_PRICING_SNAPSHOT_V1",
    "cross-asset-live-data.json": "GMFQ_FXV2_CROSS_ASSET_SOURCE_OVERLAY_V1",
    "pricing-relative-28pairs-research.json": "GMFQ_FXV2_RELATIVE_PRICING_28PAIR_RESEARCH_V1",
    "quant-temporal-readiness-v1.json": "GMFQ_FXV2_RATE_FX_TEMPORAL_READINESS_V1",
}


def validate(root: Path = ROOT) -> dict:
    items = {}
    for name, schema in FILES.items():
        path = root / REL / name
        if not path.is_file():
            raise ValueError(f"MISSING_V2_RESEARCH_FILE:{name}")
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"INVALID_V2_RESEARCH_JSON:{name}") from exc
        if not isinstance(doc, dict) or doc.get("schema") != schema:
            raise ValueError(f"RESEARCH_SCHEMA_MISMATCH:{name}")
        items[name] = doc

    ois = items["ois-pricing-snapshot.json"]
    if (ois.get("ui_only") is not True or
            ois.get("eligible_for_fx_engine") is not False or
            set(ois.get("currencies", {})) != G8):
        raise ValueError("RESEARCH_OIS_SCOPE_OR_G8_INVALID")

    cross = items["cross-asset-live-data.json"]
    if (cross.get("eligible_for_fx_core") is not False or
            set(cross.get("streams", {})) !=
            {"SP500", "NASDAQCOM", "IG_OAS", "HY_OAS", "VIX"}):
        raise ValueError("CROSS_ASSET_SOURCE_SCOPE_INVALID")

    pricing = items["pricing-relative-28pairs-research.json"]
    quant = items["quant-temporal-readiness-v1.json"]
    for name, obj in (("PRICING", pricing), ("QUANT", quant)):
        pairs = obj.get("pairs")
        if (not isinstance(pairs, dict) or len(pairs) != 28 or
                obj.get("canonical_fx_core_untouched") is not True or
                obj.get("eligible_for_backtests") is not False):
            raise ValueError(f"{name}_PAIR_COVERAGE_OR_CORE_SCOPE_INVALID")
    if pricing.get("eligible_for_fx_engine") is not False:
        raise ValueError("RELATIVE_PRICING_ENGINE_PROMOTION_FORBIDDEN")
    if quant.get("eligible_for_signals") is not False:
        raise ValueError("TEMPORAL_RESEARCH_SIGNAL_PROMOTION_FORBIDDEN")

    # Preserve the canonical *market* orientation of each FX pair (EUR/AUD
    # is not AUD/EUR). Coverage is assessed on unordered currency identities,
    # while both research files must retain exactly the same oriented keys.
    expected_pairs = {
        frozenset((a, b))
        for i, a in enumerate(sorted(G8)) for b in sorted(G8)[i + 1:]
    }
    def identities(keys):
        out = []
        for key in keys:
            parts = key.split("/")
            if (len(parts) != 2 or parts[0] not in G8 or
                    parts[1] not in G8 or parts[0] == parts[1]):
                raise ValueError("RESEARCH_PAIR_KEY_INVALID")
            out.append(frozenset(parts))
        return out

    pkeys = set(pricing["pairs"])
    qkeys = set(quant["pairs"])
    if (pkeys != qkeys or
            set(identities(pkeys)) != expected_pairs or
            set(identities(qkeys)) != expected_pairs):
        raise ValueError("RESEARCH_PAIR_UNIVERSE_MISMATCH")

    return {"status": "SOURCE_CONTRACT_PASS", "files": len(items),
            "pairs": 28, "core_promotion": False,
            "public_http_certified": False, "source_freshness_certified": False}


if __name__ == "__main__":
    print("FXV2_RESEARCH_MIRROR_SOURCE_CONTRACT",
          json.dumps(validate(), sort_keys=True))
