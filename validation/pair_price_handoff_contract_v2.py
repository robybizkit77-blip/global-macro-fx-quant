#!/usr/bin/env python3
"""Fail-closed handoff: 28 FX pair PRICE-context refresh, not Macro rebasing.

Never stamp a new Macro date, recalculate structural FX preferences with
undated data, or turn qualitative model context into executable triggers.
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

FX = ("USD", "EUR", "GBP", "JPY", "AUD", "CAD", "NZD", "CHF")
PAIR_SETS = {frozenset((a, b)) for a, b in itertools.combinations(FX, 2)}


def guard(ok: bool, msg: str) -> None:
    if not ok:
        raise ValueError("PAIR_HANDOFF_REJECTED: " + msg)


def parse_day(value: object, label: str, today: date) -> date:
    guard(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is not None,
          f"{label} missing/invalid")
    try:
        d = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"PAIR_HANDOFF_REJECTED: {label} impossible date") from exc
    guard(d <= today, f"{label} is in the future")
    return d


def validate_pair_shape(snapshot: dict, today: date) -> tuple[date, date]:
    guard(snapshot.get("schema") == "GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1", "snapshot schema")
    guard(snapshot.get("status") == "CURRENT_CANONICAL_ENGINE", "snapshot status")
    guard(snapshot.get("pair_count") == 28, "snapshot pair count")
    guard(snapshot.get("thesis_is_not_entry") is True and
          snapshot.get("entry_level_published") is False, "no-entry semantics")
    audit = snapshot.get("price_audit") or {}
    guard(audit.get("status") == "PASS" and audit.get("no_lookahead") is True and
          audit.get("complete_return_values") == 140 and
          audit.get("returns_complete") is True and
          audit.get("pair_count") == 28, "ECB 28x5 official price audit")
    guard(audit.get("as_of") == snapshot.get("price_asof"), "price audit as-of mismatch")
    pday = parse_day(snapshot.get("price_asof"), "Price", today)
    mday = parse_day(snapshot.get("macro_baseline_asof"), "Macro baseline", today)
    guard(mday <= pday, "Macro baseline later than Price observation")
    pairs = snapshot.get("pairs") or {}
    guard(isinstance(pairs, dict) and len(pairs) == 28, "28 individual pair records")
    seen = set()
    for code, row in pairs.items():
        guard(re.fullmatch(r"[A-Z]{6}", code) is not None, f"{code}: invalid pair code")
        a, b = code[:3], code[3:]
        key = frozenset((a, b))
        guard(a in FX and b in FX and a != b and key not in seen, f"{code}: duplicate/unknown")
        seen.add(key)
        guard(row.get("canonical_pair") == a + "/" + b, f"{code}: pair label")
        guard(isinstance(row.get("setup"), dict) and
              isinstance(row.get("decision_frame"), dict) and
              isinstance(row.get("transition"), dict) and
              isinstance(row.get("relative_dynamics"), dict),
              f"{code}: missing canonical structure")
    guard(seen == PAIR_SETS, "G8 pair combinations incomplete")
    return pday, mday


def classify(candidate: dict, prior: dict, d: dict, price: dict, today: date) -> dict:
    cand_price, cand_macro = validate_pair_shape(candidate, today)
    prev_price, prev_macro = validate_pair_shape(prior, today)
    baseline = parse_day(d.get("asOf"), "D.asOf", today)
    guard(candidate["macro_baseline_asof"] == d.get("asOf"),
          "Candidate Macro provenance differs from current canonical D")
    guard(price.get("schema") == "GMFQ_ECB_G8_PRICE_HISTORY_V1" and
          price.get("status") == "CURRENT_OFFICIAL_HISTORY" and
          price.get("pair_count") == 28, "official ECB price history schema/status")
    official_asof = parse_day(price.get("last_as_of"), "ECB Price history", today)
    guard(price.get("rows") and price["rows"][-1].get("Date") == price["last_as_of"],
          "ECB last row/as-of mismatch")
    guard((today - official_asof).days <= 5, "official Price history not current")
    # Price overlay and the independently persisted ECB history update in
    # different workflows. A newer, date-valid overlay may reach the browser
    # first. This is a pending dependency, NEVER publication approval.
    # The retry is already wired to Price History Persistent Daily V1.
    if cand_price > official_asof:
        return {
            "status": "WAITING_FOR_ECB_HISTORY_SAME_DAY",
            "action": "NO_WRITE",
            "reason": "ECB overlay is newer than the separately validated history; wait for matching official archive row before price handoff",
            "candidate_price_asof": cand_price.isoformat(),
            "official_history_asof": official_asof.isoformat(),
            "previous_price_asof": prev_price.isoformat(),
            "macro_asof": cand_macro.isoformat(),
            "pair_count": 28,
            "ready_for_forward_v2": False,
            "structural_preferences_preserved": True,
            "entry_levels_added": False,
        }
    guard(cand_price == official_asof, "candidate Price must match validated ECB last row")
    guard(cand_price >= prev_price, "candidate Price regresses")
    if baseline != prev_macro:
        return {
            "status": "BLOCKED_MACRO_REBASE",
            "action": "NO_WRITE",
            "reason": "D.asOf changed. Revalidate Macro/Rates structural inputs with PIT proof before republishing 28 theses.",
            "candidate_price_asof": cand_price.isoformat(),
            "macro_asof": baseline.isoformat(),
        }

    # A change to the price layer must NOT silently produce a new Macro/CB
    # preference from the same frozen D baseline.
    structural_fields = (
        ("setup", "structuralFav"),
        ("decision_frame", "macroSide"),
        ("decision_frame", "policySide"),
    )
    for code in candidate["pairs"]:
        curr, old = candidate["pairs"][code], prior["pairs"][code]
        for parent, field in structural_fields:
            guard(curr[parent].get(field) == old[parent].get(field),
                  f"{code}: {parent}.{field} changed without Macro rebase")
    status = "NO_CHANGE" if candidate == prior else "PRICE_CONTEXT_UPDATE"
    return {
        "status": status,
        "action": "NO_WRITE" if status == "NO_CHANGE" else "ELIGIBLE_FOR_PERSISTENCE",
        "previous_price_asof": prev_price.isoformat(),
        "candidate_price_asof": cand_price.isoformat(),
        "macro_asof": cand_macro.isoformat(),
        "macro_current": (today - cand_macro).days <= 10,
        "stale_macro_is_not_promoted": True,
        "pair_count": 28,
        "structural_preferences_preserved": True,
        "entry_levels_added": False,
    }


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--candidate", type=Path, required=True)
    cli.add_argument("--prior", type=Path, default=Path("live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json"))
    cli.add_argument("--model", type=Path, default=Path("live_data/sections/D.json"))
    cli.add_argument("--prices", type=Path, default=Path("live_data/sections/ECB_G8_PRICE_HISTORY.json"))
    cli.add_argument("--asof", type=str, default=datetime.now(ZoneInfo("Europe/Rome")).date().isoformat())
    cli.add_argument("--output", type=Path)
    args = cli.parse_args()
    read = lambda path: json.loads(path.read_text(encoding="utf-8"))
    receipt = classify(read(args.candidate), read(args.prior), read(args.model),
                       read(args.prices), date.fromisoformat(args.asof))
    serialized = json.dumps(receipt, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")


if __name__ == "__main__":
    main()
