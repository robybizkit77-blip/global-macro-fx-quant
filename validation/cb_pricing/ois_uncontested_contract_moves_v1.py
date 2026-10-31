#!/usr/bin/env python3
"""Independent research-only same-contract moves despite other tenor conflicts.

No interpolated curve, OIS delta, CB repricing, COT or FX signals. The currency
can have an unresolved 3M/12M print while verified individual 6M contracts
retain their own dated, checked 100-price history. Only *identical* contract,
expiry, source feed and same-business-day archive are admitted.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from ois_same_contract_history_v1 import (
    SOURCE, HISTORY, candidates, load_history, quote_fingerprint, record_key,
    require, validate_row,
)
from reconcile_ois_secondary_conflicts_v1 import (
    CONFLICTS, read_conflicts, validate_conflict_lineage,
)

SCHEMA = "GMFQ_SECONDARY_UNCONTESTED_SAME_CONTRACT_MOVES_V1"
HORIZONS = ("3m", "6m", "12m")
CCYS = ("USD", "EUR", "CHF")


def evaluate(feed: dict, rows: list[dict], conflicts: list[dict]) -> dict:
    # This audit is logically independent from any model of the CB rate path.
    quality = validate_conflict_lineage(feed, rows, conflicts)
    live, excluded = candidates(feed)
    archive = {record_key(x): x for x in rows}
    contested = {
        record_key(e["original_immutable_quote"])
        for e in conflicts
    }
    candidates_by_horizon = {
        (x["currency"], x["observed_under_horizon"]): x for x in live
    }
    out = {}
    for ccy in CCYS:
        tenor_rows = {}
        for tenor in HORIZONS:
            current = candidates_by_horizon.get((ccy, tenor))
            entry = {
                "status": "WITHHELD_NO_CURRENT_VERIFIED_CONTRACT",
                "contract": None, "quote_day": None,
                "matched_previous_quote_day": None,
                "calendar_gap_days": None,
                "observed_same_contract_change_bp": None,
                "verified_current_rate_indicative": None,
                "official_ois": False, "policy_delta_allowed": False,
                "trade_signal_allowed": False, "forward_v2_effect": "NONE",
                "is_exactly_one_trading_session": None,
            }
            if current is None:
                raw = ((feed.get("currencies") or {}).get(ccy) or {}).get("horizons") or {}
                p = raw.get(tenor) or {}
                entry["contract"] = p.get("contract")
                entry["quote_day"] = p.get("quote_as_of")
                entry["status"] = ("WITHHELD_DISPUTED_CURRENT_BAR" if
                                   p.get("quote_timestamp_source") ==
                                   "QUARANTINED_SAME_CONTRACT_SAME_DAY"
                                   else "WITHHELD_UNVERIFIED_CURRENT_BAR")
            else:
                key = record_key(current)
                entry["contract"] = current["contract"]
                entry["quote_day"] = current["observation_date"]
                if key in contested:
                    entry["status"] = "WITHHELD_HISTORICALLY_DISPUTED_CONTRACT_DAY"
                elif key not in archive:
                    entry["status"] = "WITHHELD_NOT_YET_PERSISTED_TO_IMMUTABLE_HISTORY"
                else:
                    signed = archive[key]
                    require(quote_fingerprint(signed) == quote_fingerprint(current),
                            ccy + "/" + tenor + ": current verified bar is inconsistent with immutable archive")
                    # Do not use a past conflicted print as the comparison
                    # reference, even if the first version remains immutable.
                    previous = [x for x in rows
                                if x["currency"] == ccy
                                and x["contract"] == current["contract"]
                                and x["symbol"] == current["symbol"]
                                and x["expiration"] == current["expiration"]
                                and x["observation_date"] < current["observation_date"]
                                and record_key(x) not in contested]
                    previous.sort(key=lambda x: x["observation_date"])
                    entry["verified_current_rate_indicative"] = current["implied_rate"]
                    if not previous:
                        entry["status"] = "CURRENT_VERIFIED_NO_CLEAN_SAME_CONTRACT_HISTORY"
                    else:
                        prior = previous[-1]
                        for bar in (current, prior):
                            validate_row(bar)
                        gap = (date.fromisoformat(current["observation_date"]) -
                               date.fromisoformat(prior["observation_date"])).days
                        if gap > 5:
                            entry["status"] = "CURRENT_VERIFIED_PRIOR_OBSERVATION_TOO_OLD"
                            entry["matched_previous_quote_day"] = prior["observation_date"]
                            entry["calendar_gap_days"] = gap
                        else:
                            entry.update({
                                "status": "VERIFIED_SAME_CONTRACT_OBSERVED_MOVE_RESEARCH_ONLY",
                                "matched_previous_quote_day": prior["observation_date"],
                                "calendar_gap_days": gap,
                                "observed_same_contract_change_bp":
                                    round((current["implied_rate"] - prior["implied_rate"]) * 100, 4),
                                "is_exactly_one_trading_session": False,
                            })
            tenor_rows[tenor] = entry
        out[ccy] = tenor_rows
    return {
        "schema": SCHEMA,
        "status": "PASS_RESEARCH_DIAGNOSTIC_NOT_OIS_OR_POLICY_REPRICING",
        "source_generated_at_utc": feed.get("generated_at_utc"),
        "quote_archive_rows": len(rows),
        "quarantine_events_validated": quality["journal_events_validated"],
        "currencies": out,
        "summary": {
            "observed_same_contract_moves": sum(
                item["status"] == "VERIFIED_SAME_CONTRACT_OBSERVED_MOVE_RESEARCH_ONLY"
                for rows in out.values() for item in rows.values()),
            "disputed_or_unverified_current_contracts": sum(
                item["status"].startswith("WITHHELD_DISPUTED")
                or item["status"].startswith("WITHHELD_UNVERIFIED")
                or item["status"].startswith("WITHHELD_HISTORICALLY_DISPUTED")
                for rows in out.values() for item in rows.values()),
            "total_horizons": 9,
            "official_ois_promotions": 0,
            "policy_deltas_computed": 0,
            "fx_signals_computed": 0,
        },
        "writes_live_data": False,
        "writes_history": False,
        "official_ois_curve_constructed": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quotes", type=Path, default=SOURCE)
    parser.add_argument("--history", type=Path, default=HISTORY)
    parser.add_argument("--quarantine", type=Path, default=CONFLICTS)
    parser.add_argument("--output", type=Path, default=Path("/tmp/ois-uncontested-tenor-moves-v1.json"))
    args = parser.parse_args()
    require(args.output.resolve().is_relative_to(Path("/tmp")),
            "research-only report must be under /tmp")
    result = evaluate(json.loads(args.quotes.read_text(encoding="utf-8")),
                      load_history(args.history), read_conflicts(args.quarantine))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2,
                                      sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], **result["summary"],
                      "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
