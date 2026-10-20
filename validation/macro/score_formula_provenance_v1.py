#!/usr/bin/env python3
"""Auditable boundary: historical numeric Macro scores != directional FX votes.

Read-only source inventory; NO claim that display thresholds or polarity rules
reconstruct Growth/Labour/Inflation, cycle or a new D.json baseline.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
FX = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
PILLARS = ("growth", "labour", "inflation")
PARTS = {
    "display": "payload/part-02.txt",
    "structural_pair": "payload/part-03.txt",
    "structural_currency": "payload/part-05.txt",
}
FUNCTIONS = {
    "display": ("macroSimpleScore", "deriveCurrencyRegime"),
    "structural_pair": ("derivePairDecisionFrame",),
    "structural_currency": ("layerPolarity", "policyFamilyPolarity", "deriveCurrencyState"),
}
CYCLES = {"GOLDILOCKS", "SLOWDOWN_DISINFLATION", "STAGFLATION", "REFLATION"}


def require(ok: bool, why: str) -> None:
    if not ok:
        raise ValueError("MACRO_SCORE_PROVENANCE_REJECTED: " + why)


def function_body(text: str, name: str) -> str:
    match = re.search(r"\bfunction\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{", text)
    require(match is not None, name + ": source implementation not located")
    start = match.start()
    # All locked functions must terminate before the next top-level declaration.
    # This is only a source fingerprint, never JavaScript execution.
    next_fn = re.search(r"\nfunction\s+[A-Za-z_$]\w*\s*\(", text[match.end():])
    require(next_fn is not None, name + ": cannot establish function boundary")
    body = text[start:match.end() + next_fn.start()]
    require(len(body) > 100, name + ": unexpectedly short function")
    return body


def inspect(model: dict, setup: dict, parts: dict[str, str], today: date) -> dict:
    require(set(parts) == set(PARTS), "source inventory incomplete")
    require(set(model.get("macro") or {}) == set(FX), "eight historical score records required")
    require(set(setup.get("pairs") or {}) and len(setup["pairs"]) == 28,
            "28 historical pair records required")
    require(setup.get("macro_baseline_asof") == model.get("asOf"),
            "pair model baseline not identical to D as-of")
    require(setup.get("thesis_is_not_entry") is True and
            setup.get("entry_level_published") is False, "thesis / trade contract broken")
    require(setup.get("price_asof") and setup["price_asof"] >= model["asOf"],
            "historical Macro and newer price chronology broken")
    baseline = date.fromisoformat(model["asOf"])
    price = date.fromisoformat(setup["price_asof"])
    require(baseline <= price <= today, "future baseline / price snapshot")
    require((today - baseline).days > 10, "historical model no longer stale; re-audit")
    scores = {}
    for ccy in FX:
        row = model["macro"][ccy]
        require(row.get("cycle") in CYCLES, ccy + ": unrecognized historical regime")
        for field in PILLARS:
            x = row.get(field)
            require(type(x) in (int, float) and math.isfinite(x),
                    ccy + "." + field + ": historical numeric score malformed")
        scores[ccy] = {key: row[key] for key in (*PILLARS, "cycle")}
    pairs = setup["pairs"]
    expected = {frozenset(pair) for pair in itertools.combinations(FX, 2)}
    actual = set()
    for key, rec in pairs.items():
        require(re.fullmatch(r"[A-Z]{6}", key) is not None and
                key[:3] in FX and key[3:] in FX and key[:3] != key[3:],
                "invalid currency pair " + str(key))
        actual.add(frozenset((key[:3], key[3:])))
        require(rec.get("canonical_pair") == key[:3] + "/" + key[3:],
                key + ": canonical key mismatch")
    require(actual == expected and len(actual) == 28,
            "duplicate or incomplete 28 pair combinations")

    func_hashes: dict[str, str] = {}
    source_hashes = {}
    excerpts = {}
    for group, source in parts.items():
        source_hashes[group] = hashlib.sha256(source.encode("utf-8")).hexdigest()
        for name in FUNCTIONS[group]:
            body = function_body(source, name)
            func_hashes[name] = hashlib.sha256(body.encode("utf-8")).hexdigest()
            excerpts[name] = body
    # Positive proofs of what the currently deployed JavaScript ACTUALLY reads:
    require("kind==='Inflazione'" in excerpts["macroSimpleScore"] and
            "Math.abs(v)" in excerpts["macroSimpleScore"] and
            "return 'forte'" in excerpts["macroSimpleScore"],
            "visual score interpretation has changed")
    require("D.macro?.[c]" in excerpts["deriveCurrencyRegime"] and
            "m.cycle" in excerpts["deriveCurrencyRegime"],
            "cycle is not read from frozen D")
    require("layerPolarity(d.macro)" in excerpts["deriveCurrencyState"] and
            "policyFamilyPolarity(d)" in excerpts["deriveCurrencyState"],
            "structural directional labels changed")
    require("deriveCurrencyState(a)" in excerpts["derivePairDecisionFrame"] and
            "deriveCurrencyState(b)" in excerpts["derivePairDecisionFrame"],
            "pair derivation no longer uses G8 directional states")
    require("D.macro?.[a]?.rate2y" in excerpts["derivePairDecisionFrame"] and
            "D.macro?.[b]?.rate2y" in excerpts["derivePairDecisionFrame"],
            "legacy pair reference 2Y contract changed")
    # These implementations are presentational or directional. If they begin to
    # assign canonical numeric pillar scores, stop: a new score audit is needed.
    for name, body in excerpts.items():
        require(not re.search(r"(?:D\.macro|m)\s*(?:\[[^\]]+\]|\.[A-Za-z_]+)*\s*(?:\.\s*(?:growth|labour|inflation)|\[\s*['\"](?:growth|labour|inflation)['\"]\s*\])\s*=", body),
                name + ": unreviewed numeric Macro score mutation")
    frozen = json.dumps(scores, sort_keys=True, separators=(",", ":"))
    return {
        "schema": "GMFQ_MACRO_SCORE_PROVENANCE_BOUNDARY_V1",
        "status": "PASS_HISTORICAL_SCORE_READERS_IDENTIFIED_NO_SCORE_GENERATOR_CERTIFIED",
        "model_as_of": model["asOf"],
        "price_as_of": setup["price_asof"],
        "audit_as_of": today.isoformat(),
        "historical_scalar_scores": 8 * len(PILLARS),
        "historical_regimes": len(FX),
        "pairs_in_source_snapshot": len(pairs),
        "historical_scores_sha256": hashlib.sha256(frozen.encode("utf-8")).hexdigest(),
        "source_files_sha256": source_hashes,
        "runtime_function_sha256": func_hashes,
        "certified_semantics": {
            "macroSimpleScore": "DISPLAY_LABELS_FROM_ALREADY_STORED_NUMBER",
            "deriveCurrencyRegime": "REGIME_LABEL_FROM_ALREADY_STORED_D_CYCLE",
            "deriveCurrencyState": "DIRECTIONAL_VOTE_FROM_UNDATED_QUALITATIVE_LABELS",
            "derivePairDecisionFrame": "STRUCTURAL_DIRECTION_FROM_TWO_CURRENCY_VOTES_AND_EMBEDDED_2Y",
        },
        "uncertified_semantics": {
            "growth_score_source_to_number": "MISSING_VERSIONED_PIT_FORMULA",
            "labour_score_source_to_number": "MISSING_VERSIONED_PIT_FORMULA",
            "inflation_score_source_to_number": "MISSING_VERSIONED_PIT_FORMULA",
            "economic_cycle_from_pillars": "MISSING_VERSIONED_TRANSITION_RULE",
            "qualitative_labels_as_new_macro": "MISSING_SOURCE_TIMESTAMPED_VINTAGE",
        },
        "ready_for_numeric_macro_rebase": False,
        "safe_to_publish_new_D": False,
        "safe_to_update_28_pair_theses": False,
        "writes_live_data": False,
        "note": ("This is a provenance boundary, not a mathematical score reconstruction. "
                 "An independently replayed FX vote is NOT certified as a refreshed "
                 "source-to-numeric-score transform; displayed thresholds are not weights."),
    }


def run(root: Path = ROOT, today: date | None = None) -> dict:
    today = today or datetime.now(ZoneInfo("Europe/Rome")).date()
    read = lambda name: (root / name).read_text(encoding="utf-8")
    model = json.loads(read("live_data/sections/D.json"))
    setup = json.loads(read("live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json"))
    return inspect(model, setup, {k: read(p) for k, p in PARTS.items()}, today)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asof", default=datetime.now(ZoneInfo("Europe/Rome")).date().isoformat())
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = run(today=date.fromisoformat(args.asof))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    print(json.dumps({k: result[k] for k in (
        "status", "model_as_of", "price_as_of", "historical_scalar_scores",
        "historical_regimes", "pairs_in_source_snapshot",
        "ready_for_numeric_macro_rebase", "safe_to_publish_new_D"
    )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
