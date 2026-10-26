#!/usr/bin/env python3
"""Append-only, fail-closed capture of the already-computed Core decision surface.

This module deliberately reads the published inputs and pair states after Core has
finished.  It is not imported by the decision engine and cannot feed back into it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FORWARD = ROOT / "validation" / "forward"
SCHEMA = FORWARD / "CORE_FORWARD_DECISION_LOGGER_V1_SCHEMA.json"
DECISIONS = FORWARD / "decision_snapshots" / "CORE_DECISION_SNAPSHOTS_V1.jsonl"
RECEIPTS = FORWARD / "receipts"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def load_json(relative: str) -> tuple[Any, str]:
    path = ROOT / relative
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()


def commit_sha() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "WITHHELD_NO_GIT_COMMIT"


def parse_cutoff(raw: str) -> dt.datetime:
    value = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("decision_cutoff must include an explicit UTC offset")
    return value.astimezone(dt.timezone.utc)


def date_available_before(date_value: Any, cutoff: dt.datetime) -> tuple[str | None, bool]:
    """Use end-of-observation day as a conservative availability bound.

    Same-day observations are withheld because this project has not certified an
    intraday publication timestamp for every source.
    """
    if not isinstance(date_value, str) or len(date_value) < 10:
        return None, False
    try:
        observed = dt.date.fromisoformat(date_value[:10])
    except ValueError:
        return None, False
    cutoff_date = cutoff.date()
    if observed >= cutoff_date:
        return None, False
    return f"{observed.isoformat()}T23:59:59Z", True


def item_date(item: Any, fallbacks: tuple[str, ...] = ()) -> Any:
    if not isinstance(item, dict):
        return None
    for key in ("available_at", "as_of", "asOf", "date", "price_asof", "updated_at", *fallbacks):
        if item.get(key):
            return item[key]
    return None


def input_record(layer: str, value: Any, source_id: str, source_sha: str, cutoff: dt.datetime, date_value: Any) -> tuple[dict[str, Any], bool]:
    available_at, usable = date_available_before(date_value, cutoff)
    record = {
        "layer": layer,
        "state": "AVAILABLE" if usable else "WITHHELD",
        "available_at": available_at,
        "source_id": source_id,
        "source_sha256": source_sha,
        "observed_or_as_of": date_value,
        "value": value if usable else None,
    }
    return record, not usable


def source_bundle(cutoff: dt.datetime) -> tuple[dict[str, tuple[Any, str]], dict[str, Any]]:
    sources: dict[str, tuple[Any, str]] = {}
    for key, rel in {
        "core_surface": "live_data/sections/D.json",
        "macro": "live_data/sections/MACRO_THERMOMETER_DATA.json",
        "rates": "live_data/sections/NATIVE_RATES_DATA.json",
        "ois": "live_data/sections/OIS_DATA.json",
        "central_bank": "live_data/sections/NATIVE_CB_DATA.json",
        "cot": "live_data/sections/V250_COT_CHART_DATA.json",
        "liquidity": "live_data/sections/NATIVE_LIQ_DATA.json",
    }.items():
        sources[key] = load_json(rel)
    d, _ = sources["core_surface"]
    if not isinstance(d.get("pairs"), list) or not isinstance(d.get("pairStates"), dict):
        raise ValueError("D.json has no canonical pair surface")
    return sources, d


def make_rows(cutoff: dt.datetime, run_id: str) -> list[dict[str, Any]]:
    sources, d = source_bundle(cutoff)
    rules_fp = "WITHHELD"
    try:
        t0, _ = load_json("validation/CANONICAL_ENGINE_OOS_T0_V3_2026-10-01.json")
        rules_fp = str(t0.get("rules_fingerprint") or "WITHHELD")
    except FileNotFoundError:
        pass
    # Preserve the frozen structural Core vintage. New observations must never
    # represent the Sep-2026 baseline as a newly recomputed Macro decision.
    baseline_day = d.get("asOf")
    if not isinstance(baseline_day, str) or len(baseline_day) != 10:
        raise ValueError("unverifiable Core structural baseline date")
    try:
        baseline_date = dt.date.fromisoformat(baseline_day)
    except ValueError as exc:
        raise ValueError("invalid Core structural baseline date") from exc
    if baseline_date >= cutoff.date():
        raise ValueError("Core baseline must predate prospective capture")
    rows = []
    for price in d["pairs"]:
        pair = str(price["pair"])
        base, quote = pair.split("/", 1)
        state = d["pairStates"].get(pair, {})
        macro, macro_sha = sources["macro"]
        rates, rates_sha = sources["rates"]
        ois, ois_sha = sources["ois"]
        cb, cb_sha = sources["central_bank"]
        cot, cot_sha = sources["cot"]
        liq, liq_sha = sources["liquidity"]
        core, core_sha = sources["core_surface"]
        inputs: dict[str, Any] = {}
        withheld: dict[str, bool] = {}
        inputs["core_pair_state"], withheld["core_pair_state"] = input_record(
            "CORE_SURFACE", state, "live_data/sections/D.json", core_sha, cutoff, d.get("asOf")
        )
        # The thermometer carries observation *periods* but not certified
        # PIT publication timestamps; do not leak a post-baseline macro datum
        # into the frozen structural decision by assigning d.asOf as its time.
        macro_ccys = macro.get("currencies", {})
        inputs["macro"], withheld["macro"] = input_record(
            "MACRO",
            {base: macro_ccys.get(base), quote: macro_ccys.get(quote)},
            "live_data/sections/MACRO_THERMOMETER_DATA.json", macro_sha, cutoff,
            None,
        )
        inputs["rates"], withheld["rates"] = input_record(
            "RATES", {base: rates.get(base), quote: rates.get(quote)}, "live_data/sections/NATIVE_RATES_DATA.json", rates_sha, cutoff,
            max(str(item_date(rates.get(base)) or ""), str(item_date(rates.get(quote)) or "")),
        )
        for name, source, sha, layer in (("ois", ois, ois_sha, "OIS"), ("central_bank", cb, cb_sha, "CENTRAL_BANK"), ("cot", cot, cot_sha, "COT"), ("liquidity", liq, liq_sha, "LIQUIDITY")):
            value = {base: source.get(base), quote: source.get(quote)}
            # No guessed global timestamp: each source must carry its own date.
            source_date = max(str(item_date(value[base]) or ""), str(item_date(value[quote]) or ""))
            inputs[name], withheld[name] = input_record(layer, value, f"live_data/sections/{ {'ois':'OIS_DATA.json','central_bank':'NATIVE_CB_DATA.json','cot':'V250_COT_CHART_DATA.json','liquidity':'NATIVE_LIQ_DATA.json'}[name]}", sha, cutoff, source_date)
        inputs["price"], withheld["price"] = input_record(
            "PRICE", price, "live_data/sections/D.json", core_sha, cutoff, price.get("price_asof") or d.get("priceAsOf")
        )
        # The Core contract states these are context-only; do not log a non-used overlay as an input.
        overlays = {"used": False, "reason": "Risk and liquidity do not alter Core structural scoring, bias, sizing or pair eligibility."}
        body = {
            "schema_version": "GMFQ_CORE_FORWARD_DECISION_LOGGER_V1.1.0",
            "decision_cutoff": cutoff.isoformat().replace("+00:00", "Z"),
            "run_id": run_id,
            "source_commit": commit_sha(),
            "pair": pair,
            "base_currency": base,
            "quote_currency": quote,
            "thesis_strength": state.get("convergence"),
            "trade_attractiveness": state.get("state_label"),
            "core_signal": state.get("convergence_winner"),
            "core_score": None,
            # Versioned observation of an old model, never an engine re-run.
            "capture_class": "FROZEN_CORE_BASELINE_OBSERVATION",
            "core_baseline_as_of": baseline_day,
            "core_recomputed_at_capture": False,
            "current_macro_score_certified": False,
            "source_panel_is_true_historical_pit": False,
            "inputs": inputs,
            "macro_inputs_states": inputs["macro"],
            "rates_2y_10y_ois_cb_states": {k: inputs[k] for k in ("rates", "ois", "central_bank")},
            "cot_positioning": inputs["cot"],
            "price_market_confirmation_divergence": {"price": inputs["price"], "pair_state": inputs["core_pair_state"]},
            "risk_liquidity_overlays": overlays,
            "withheld_flags": withheld,
            "source_provenance": {key: {"source_id": f"live_data/sections/{key}", "sha256": sha} for key, (_, sha) in sources.items()},
            "rules_fingerprint": rules_fp,
        }
        identity = f"{body['decision_cutoff']}|{run_id}|{pair}"
        body["snapshot_id"] = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        body["snapshot_sha256"] = digest(body)
        rows.append(body)
    if len(rows) != 28 or len({r["pair"] for r in rows}) != 28:
        raise ValueError("expected exactly 28 unique frozen canonical pairs")
    return sorted(rows, key=lambda row: row["pair"])


def existing_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {json.loads(line)["snapshot_id"] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def append_rows(rows: list[dict[str, Any]], dry_run: bool) -> dict[str, Any]:
    known = existing_ids(DECISIONS)
    new_rows = [row for row in rows if row["snapshot_id"] not in known]
    if not dry_run and new_rows:
        DECISIONS.parent.mkdir(parents=True, exist_ok=True)
        with DECISIONS.open("ab") as handle:
            for row in new_rows:
                handle.write(canonical(row))
    return {"written": len(new_rows), "duplicates_skipped": len(rows) - len(new_rows), "total_candidates": len(rows)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-cutoff", required=True, help="ISO-8601 instant with an explicit offset")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    cutoff = parse_cutoff(args.decision_cutoff)
    rows = make_rows(cutoff, args.run_id)
    result = append_rows(rows, args.dry_run)
    receipt = {
        "schema": "GMFQ_CORE_FORWARD_DECISION_LOGGER_RECEIPT_V1",
        "status": "PASS",
        "decision_cutoff": cutoff.isoformat().replace("+00:00", "Z"),
        "run_id": args.run_id,
        "observational_only": True,
        "no_forward_outcomes_in_snapshot": True,
        "pit_guard": "available_at <= decision_cutoff or explicit WITHHELD",
        "decision_store": str(DECISIONS.relative_to(ROOT)).replace("\\", "/"),
        "batch_sha256": digest(rows),
        "result": result,
    }
    if not args.dry_run:
        RECEIPTS.mkdir(parents=True, exist_ok=True)
        (RECEIPTS / f"{cutoff.date().isoformat()}__{args.run_id}__V1.json").write_bytes(canonical(receipt))
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
