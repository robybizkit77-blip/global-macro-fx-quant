#!/usr/bin/env python3
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

FROZEN_COMMIT = "ff52198a75cc67f7dae96fc2bbf65623f170791c"
SIGNED = Path("validation/DASHBOARD_PAIR_SIGNED_INPUTS_V1_2026-10-07.json")
OUT = Path("validation/FROZEN_MACRO_ANCHOR_PARITY_AUDIT_V1_2026-10-07.json")
CCYS = ["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"]


def git_show(path: str) -> str:
    return subprocess.check_output(
        ["git", "show", f"{FROZEN_COMMIT}:{path}"], text=True, stderr=subprocess.STDOUT
    )


def extract_currency_macro_labels(source: str):
    labels = {}
    for c in CCYS:
        # Restrict to each currency object and capture its macro layer first label.
        start = source.find(f"{c}:{{state:")
        if start < 0:
            raise RuntimeError(f"currencyIntelData block not found for {c}")
        next_starts = [source.find(f"{x}:{{state:", start + 1) for x in CCYS]
        next_starts = [x for x in next_starts if x > start]
        end = min(next_starts) if next_starts else len(source)
        block = source[start:end]
        m = re.search(r"macro:\['([^']+)'", block)
        if not m:
            raise RuntimeError(f"macro label not found for {c}")
        labels[c] = m.group(1)
    return labels


def polarity(label: str) -> int:
    s = label.lower()
    if "favorevole" in s:
        return 1
    if "contrario" in s:
        return -1
    return 0


def pair_anchor(pair: str, pol):
    a, b = pair.split("/")
    av, bv = pol[a], pol[b]
    if av > bv:
        return "A"
    if bv > av:
        return "B"
    return "MIXED"


def main():
    # currencyIntelData and deriveCurrencyState live in frozen payload/part-02..05;
    # concatenate only those frozen payloads so the audit never trusts current UI labels.
    frozen_source = "\n".join(git_show(f"payload/part-{i:02d}.txt") for i in range(2, 6))
    labels = extract_currency_macro_labels(frozen_source)
    pol = {c: polarity(v) for c, v in labels.items()}

    signed = json.loads(SIGNED.read_text())
    pairs = signed["pairs"]
    comparisons = {}
    mismatch = []
    frozen_counts = Counter()
    current_counts = Counter()

    for pair, rec in sorted(pairs.items()):
        frozen_anchor = pair_anchor(pair, pol)
        current_anchor = rec["macro_anchor"]
        same = frozen_anchor == current_anchor
        frozen_counts[frozen_anchor] += 1
        current_counts[current_anchor] += 1
        comparisons[pair] = {
            "frozen_canonical_anchor": frozen_anchor,
            "research_current_anchor": current_anchor,
            "research_macro_source": rec.get("macro_source"),
            "match": same,
        }
        if not same:
            mismatch.append(pair)

    out = {
        "schema": "GMFQ_FROZEN_MACRO_ANCHOR_PARITY_AUDIT_V1",
        "status": "PARITY" if not mismatch else "ARCHITECTURAL_MISMATCH_FOUND",
        "frozen_engine_commit": FROZEN_COMMIT,
        "rules_fingerprint": "3356baf0",
        "purpose": "Compare the frozen canonical pair Macro rule against the current research signed-input Macro anchors without changing engine, live data, OOS baseline or production state.",
        "frozen_rule": {
            "currency_macro": "layerPolarity(currencyIntelData[c].macro): Favorevole=+1, Contrario=-1, otherwise 0",
            "pair_macro": "A if macroA>macroB; B if macroB>macroA; otherwise MIXED/TIE",
            "cert53_role": "Frozen runtime comment explicitly says legacy relative Macro readings must not override the canonical currency engine."
        },
        "frozen_currency_macro": {
            c: {"label": labels[c], "polarity": pol[c]} for c in CCYS
        },
        "distribution": {
            "frozen_canonical": dict(sorted(frozen_counts.items())),
            "research_current": dict(sorted(current_counts.items())),
            "match_count": 28 - len(mismatch),
            "mismatch_count": len(mismatch),
        },
        "mismatched_pairs": mismatch,
        "pairs": comparisons,
        "interpretation": {
            "claim": "This audit tests architectural parity only, not predictive performance.",
            "if_mismatch": "Do not promote or silently rewrite current research states. First choose a canonical Macro-state regeneration contract and replay downstream research layers read-only.",
            "macro_ingest_gate": "BLOCK_APPLY_UNTIL_CANONICAL_CURRENCY_MACRO_REGENERATION_EXISTS"
        },
        "guards": {
            "changes_engine_rules": False,
            "changes_live_data": False,
            "changes_oos_baseline": False,
            "production_promotion": False,
            "predictive_claim": False
        }
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(out["distribution"], ensure_ascii=False))
    print(f"status={out['status']} mismatches={len(mismatch)}")


if __name__ == "__main__":
    main()
