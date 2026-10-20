#!/usr/bin/env python3
"""Independent read-only oracle for the currently deployed structural FX rules.

Crucial distinction: static currencyIntelData labels drive directional Macro
and Rates/CB votes. D.macro[c].{growth,labour,inflation} are HISTORICAL scalar
metrics, NOT inputs to these votes. This file cannot recalculate either.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from datetime import date
from pathlib import Path

FX = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
PAIRS = {frozenset((a, b)) for a, b in itertools.combinations(FX, 2)}
SCHEMA = "GMFQ_CANONICAL_STRUCTURAL_RULE_REPLAY_V1"


def require(ok, message):
    if not ok:
        raise ValueError("STRUCTURAL_RULE_REPLAY_REJECTED: " + message)


def real(x):
    return type(x) in (int, float) and math.isfinite(x)


def polarity(layer):
    require(isinstance(layer, list) and len(layer) >= 1 and isinstance(layer[0], str),
            "missing layer label")
    label = layer[0].strip().lower()
    # Canonical layerPolarity searches "favorevole" as a substring; prevent
    # accidental positive classification of the word "sfavorevole".
    require("sfavorevole" not in label, "ambiguous sfavorevole label would be incorrectly positive")
    if "favorevole" in label:
        return 1
    if "contrario" in label:
        return -1
    return 0


def policy(layers):
    rates_label = layers["rates"][0].lower()
    rates = polarity(layers["rates"])
    cb = polarity(layers["cb"])
    if "diverg" in rates_label:
        return 0
    if rates:
        return rates
    return cb


def category(macro, monetary):
    if macro == 1 and monetary == 1:
        return "FORTE"
    if macro == -1 and monetary == -1:
        return "FRAGILE"
    if (macro == 1 and monetary == 0) or (monetary == 1 and macro == 0):
        return "COSTRUTTIVA"
    if (macro == -1 and monetary == 0) or (monetary == -1 and macro == 0):
        return "DEBOLE"
    return "MISTA"


def direction(left, right):
    return "A" if left > right else "B" if right > left else "TIE"


def derive_pair(a, b, ca, cb):
    ma, mb = ca["macro"], cb["macro"]
    pa, pb = ca["policy"], cb["policy"]
    sm, sp = direction(ma, mb), direction(pa, pb)
    left, right = ca["rate2y"], cb["rate2y"]
    require(real(left) and real(right), f"{a}/{b}: missing rate2y cannot be interpreted as zero")
    spread = (left - right) * 100.0
    material = abs(spread) >= 75.0
    rate_side = ("—" if not material else a if spread > 0 else b)
    favorite = "—"
    quality = "MISTO / NON RISOLUTIVO"
    if sm != "TIE" and sm == sp:
        favorite = a if sm == "A" else b
        quality = "CONTRASTO STRUTTURALE FORTE"
    elif sm != "TIE" and sp == "TIE":
        favorite = a if sm == "A" else b
        quality = "VANTAGGIO RELATIVO PARZIALE"
    elif sp != "TIE" and sm == "TIE":
        favorite = a if sp == "A" else b
        quality = "VANTAGGIO RELATIVO PARZIALE"
    elif sm != "TIE" and sp != "TIE" and sm != sp:
        quality = "PILASTRI DIVISI"
    elif material and sm == sp == "TIE":
        quality = "SEPARAZIONE RATES MATERIALE"
    else:
        quality = "NESSUN CONTRASTO"
    return dict(favored=favorite, quality=quality,
                macro_side=sm, policy_side=sp, rates_bp=spread,
                rate_material=material, rate_side=rate_side)


def replay(snapshot: dict, model: dict, published: dict, asof: date):
    require(snapshot.get("schema") == SCHEMA and snapshot.get("currency_count") == 8 and
            snapshot.get("pair_count") == 28, "missing canonical 8x28 browser source")
    require(snapshot.get("status") == "HISTORICAL_DIRECTIONAL_RULES_AUDITED_NOT_MACRO_REBASED",
            "unsupported currentness status")
    require(snapshot.get("scores_reconstructed") is False and
            snapshot.get("macro_rebase_permitted") is False and
            snapshot.get("raw_labels_dated_independently") is False and
            snapshot.get("economic_score_weights_present") is False, "falsely promoted score lineage")
    require(not snapshot.get("page_errors"), "browser page errors")
    require(snapshot.get("model_asof") == model.get("asOf") ==
            published.get("macro_baseline_asof"), "model / pair Macro snapshot date discrepancy")
    day = date.fromisoformat(model["asOf"])
    require(day <= asof and (asof-day).days > 10, "historical Macro baseline policy changed; re-audit")
    require(set(snapshot.get("currencies", {})) == set(FX), "G8 currencies incomplete")
    require(len(snapshot.get("pairs", {})) == 28, "28 structural frames missing")
    functions = snapshot.get("engine_functions_sha256") or {}
    require(set(functions) == {"polarity", "policy", "currency", "pair"} and
            all(isinstance(h, str) and len(h) == 64 and
                all(ch in "0123456789abcdef" for ch in h) for h in functions.values()),
            "missing browser runtime rule fingerprints")
    currencies = {}
    for c in FX:
        row = snapshot["currencies"][c]
        raw = row["raw_layers"]
        require(set(raw) >= {"macro", "cb", "rates", "liquidity", "price"},
                f"{c}: missing layer labels")
        m, p = polarity(raw["macro"]), policy(raw)
        pol, rcb = polarity(raw["rates"]), polarity(raw["cb"])
        expected_base = category(m, p)
        actual = row["structural_engine"]
        require(actual["macro"] == m and actual["policy"] == p and
                actual["base"] == expected_base, f"{c}: engine directional votes mismatch")
        if pol == rcb and pol:
            expected_context = "CB CONFERMA RATES"
        elif not pol and not rcb:
            expected_context = "POLICY NON RISOLUTIVA"
        elif pol and not rcb:
            expected_context = "CB NEUTRALE VS RATES"
        elif not pol and rcb:
            expected_context = "CB GUIDA TEMPORANEAMENTE"
        else:
            expected_context = "CB DIVERGE DA RATES"
        require(actual["policy_context"] == expected_context,
                f"{c}: CB/Rates interpretation mismatch")
        frozen_scores = row["historical_D_scores"]
        require(all(real(frozen_scores.get(key)) and
                    frozen_scores[key] == model["macro"][c][key]
                    for key in ("growth", "labour", "inflation")), f"{c}: scalar scores not frozen D")
        require(frozen_scores.get("cycle") == model["macro"][c].get("cycle"),
                f"{c}: cycle changed without Macro score regeneration")
        rate = row.get("embedded_D_rate2y")
        require(real(rate), f"{c}: invalid browser 2Y")
        currencies[c] = {"macro": m, "policy": p, "rate2y": rate, "base": expected_base}
    actual_pairs = snapshot["pairs"]
    historical_pairs = published["pairs"]
    require(set(actual_pairs) == set(historical_pairs), "Pair feed vs browser set mismatch")
    seen = set()
    qualities = {}
    for pair, row in actual_pairs.items():
        require(len(pair) == 6 and row.get("canonical_pair") == pair[:3]+"/"+pair[3:],
                f"{pair}: pair label invalid")
        a, b = pair[:3], pair[3:]
        key = frozenset([a, b])
        require(key in PAIRS and key not in seen, f"{pair}: duplicate/missing combination")
        seen.add(key)
        expected = derive_pair(a, b, currencies[a], currencies[b])
        structural = row["structural"]
        require(row["favored"] == expected["favored"] and
                row["quality"] == expected["quality"], f"{pair}: pair winner/quality drift")
        require(structural["macro"]["side"] == expected["macro_side"] and
                structural["policy"]["side"] == expected["policy_side"] and
                structural["ratesGap"]["side"] == expected["rate_side"] and
                structural["ratesGap"]["material"] is expected["rate_material"] and
                math.isclose(structural["ratesGap"]["bp"], expected["rates_bp"], abs_tol=1e-7),
                f"{pair}: structural rate/side oracle drift")
        pub = historical_pairs[pair]
        require(pub["decision_frame"]["fav"] == expected["favored"] and
                pub["decision_frame"]["quality"] == expected["quality"] and
                pub["decision_frame"]["structural"]["macro"]["side"] == expected["macro_side"] and
                pub["decision_frame"]["structural"]["policy"]["side"] == expected["policy_side"] and
                pub["setup"].get("structuralFav") ==
                (None if expected["favored"] == "—" else expected["favored"]),
                f"{pair}: published structural feed mismatch")
        qualities[expected["quality"]] = qualities.get(expected["quality"], 0) + 1
    return {
        "schema": "GMFQ_STRUCTURAL_RULE_REPLAY_RECEIPT_V1",
        "status": "PASS_HISTORICAL_RULE_PARITY",
        "as_of": asof.isoformat(), "model_asof": model["asOf"],
        "currencies_verified": len(currencies),
        "pairs_verified": len(seen),
        "qualities": qualities,
        "engine_functions_sha256": functions,
        "macro_scores_recalculated": False,
        "dynamic_current_structural_rebase_allowed": False,
        "unblocking_requirements": [
            "PIT timestamped observations and versioned 3-pillar score transforms",
            "Evidence-backed refreshed currency directional Macro and Rates/CB labels",
            "Macro D.json proposal and OOS fingerprint/restart policy",
        ],
        "policy": "Current core direction replayed, not current Macro thesis validated.",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--trace", required=True, type=Path)
    p.add_argument("--model", type=Path, default=Path("live_data/sections/D.json"))
    p.add_argument("--setup", type=Path,
                   default=Path("live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json"))
    p.add_argument("--asof", default=date.today().isoformat())
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    load = lambda f: json.loads(f.read_text(encoding="utf-8"))
    result = replay(load(args.trace), load(args.model), load(args.setup),
                    date.fromisoformat(args.asof))
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
