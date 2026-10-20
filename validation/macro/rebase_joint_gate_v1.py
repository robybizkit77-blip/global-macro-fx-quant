#!/usr/bin/env python3
"""Read-only Macro pre-rebase evidence join. NEVER generates D.json or FX signals.

Joins the independent 16-source official release ledger to the 8-currency,
28-pair source-to-engine inventory. An intact daily data pipeline or validated
latest release cannot be misread as permission to recompute structural scores.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.macro.rebase_readiness_v1 import ROOT, FX, DIMS, PATHS, g8_coverage
from validation.macro.latest_release_pit_ledger_v1 import build_ledger

SCHEMA = "GMFQ_MACRO_JOINT_REBASE_GATE_V1"
GRADES = {"FULL_RELEASE_INSTANT", "DATE_ONLY",
          "WITHHELD_EXACT_PERIOD_EVIDENCE",
          "WITHHELD_OFFICIAL_SOURCE_VALUE_CONFLICT"}


def require(condition, reason):
    if not condition:
        raise ValueError("MACRO_JOINT_REBASE_GATE_REJECTED: " + reason)


def combine(source, ledger):
    require(source.get("source_lineage") == "PASS" and
            source.get("structural_rebase") == "BLOCKED_SCORE_CONTRACT" and
            source.get("safe_to_publish_D") is False and
            source.get("safe_to_update_structural_pair_preferences") is False,
            "unsafe source-to-engine release status")
    require(ledger.get("source_lineage") == "PASS" and
            ledger.get("safe_to_publish_new_D") is False and
            ledger.get("safe_to_promote_macro_labels") is False and
            ledger.get("historical_vintage_series_available") is False and
            ledger.get("release_dates_not_inferred_from_calendar") is True and
            ledger.get("release_ledger_scope") == "LATEST_OBSERVATION_ONLY",
            "latest release ledger falsely promoted to vintage history")
    require(source.get("run_as_of") == ledger.get("as_of") and
            source.get("canonical_macro_baseline_as_of") ==
            ledger.get("model_baseline_as_of"), "date alignment")
    require(source.get("registered_macro_series") == 16 and
            source.get("tracked_currencies") == 8 and
            source.get("tracked_pairs") == 28 and
            ledger.get("observations_checked") == 16,
            "incomplete G8/28 coverage")
    require(set(source.get("currencies", {})) == set(FX) and
            set(ledger.get("observations", {})) ==
            {c + "." + dim for c in FX for dim in DIMS},
            "source identities/coverage drift")
    counts = {g: 0 for g in sorted(GRADES)}
    lanes = {}
    for currency in FX:
        row = source["currencies"][currency]
        rec = {"country": currency, "macro_baseline_as_of": row["historical_model_as_of"],
               "source_ready": {}, "growth_rule": row["growth_score_status"],
               "growth_sources_inventoried": len(row["growth_source_inventory"]),
               "rates": row["rates_2y_10y"]["status"],
               "policy_pricing": row["policy_pricing"]["status"],
               "structural_score_status": "BLOCKED_VERSIONED_SCORE_AND_COMPLETE_PIT",
               "historical_scores_preserved": True}
        require(row["historical_model_as_of"] ==
                source["canonical_macro_baseline_as_of"],
                currency + " macro source baseline drift")
        require(row["proposed_scores"] is None and row["rebase_ready"] is False and
                row["growth_score_status"] == "VERSIONED_RULE_NOT_CERTIFIED",
                currency + " unauthorized structural score")
        for dim in DIMS:
            key = currency + "." + dim
            observed = ledger["observations"][key]
            source_value = row[dim]
            release = observed["release"]
            status = release["status"]
            require(status in GRADES, key + " unsupported release grade")
            require(observed["series_id"] == source_value["series_id"] and
                    observed["canonical_series_id"] == source_value["canonical_macro_series_id"] and
                    observed["current_observation_period"] ==
                    source_value["observation_as_of"], key + " period or id mismatch")
            require(observed["latest_transformed_observation"] ==
                    source_value["transformed_value"],
                    key + " value mismatch across audits")
            require(release["historical_backtest_safe_for_all_periods"] is False and
                    release["source_history_values_are_not_first_release_vintages"] is True,
                    key + " sparse PIT incorrectly promoted")
            if status == "FULL_RELEASE_INSTANT":
                require(release["release_clock_verified"] is True and
                        bool(release["first_release_timestamp_utc"]),
                        key + " timestamp proof missing")
            elif status == "DATE_ONLY":
                require(release["date_only_not_eligible_for_intraday_PIT"] is True and
                        not release["first_release_timestamp_utc"],
                        key + " date-only intraday promotion")
            else:
                require(release["first_release_date"] is None and
                        release["first_release_timestamp_utc"] is None,
                        key + " WITHHELD evidence promoted")
            counts[status] += 1
            rec["source_ready"][dim] = {
                "latest_observation_period": observed["current_observation_period"],
                "latest_release_grade": status,
                "first_release_date": release["first_release_date"],
                "intraday_release_time_verified": release["release_clock_verified"],
                "archival_vintage_certified": False,
                "score_transform_certified": False,
            }
        lanes[currency] = rec
    require(counts == ledger["counts"] and sum(counts.values()) == 16,
            "release evidence counts inconsistent")
    require(all(len(lanes[c]["source_ready"]) == 2 for c in FX),
            "incomplete currency ledger")
    return {
        "schema": SCHEMA,
        "status": "AUDITED_NOT_AUTHORIZED_FOR_MACRO_REBASE",
        "as_of": source["run_as_of"],
        "macro_baseline_as_of": source["canonical_macro_baseline_as_of"],
        "price_as_of": source["pair_price_as_of"],
        "source_lineage": "PASS",
        "source_rows_compared": 16,
        "currency_count": 8,
        "pair_count": 28,
        "release_grades": counts,
        "currency_gates": lanes,
        "mandatory_open_gates": [
            "VERSIONED_GROWTH_INFLATION_LABOUR_SCORE_TRANSFORM_UNCERTIFIED",
            "COMPLETE_POINT_IN_TIME_FIRST_RELEASE_VINTAGES_UNAVAILABLE",
            "RATES_AND_POLICY_SOURCE_DATE_QUALITY_RECONCILIATION_PENDING",
            "INDEPENDENT_D_SCORE_28_PAIR_AND_OOS_FINGERPRINT_REQUIRED",
        ],
        "safe_to_publish_new_D": False,
        "safe_to_update_pair_thesis": False,
        "writes_live_data": False,
        "note": ("The source ledger certifies some latest official release dates. "
                 "It never supplies a historical PIT vintage series or versioned "
                 "Macro scoring formula. No date-only proof authorizes intraday signals."),
    }


def run(root=ROOT, today=None):
    root = Path(root)
    today = today or datetime.now(ZoneInfo("Europe/Rome")).date()
    feeds = {key: json.loads((root / path).read_text(encoding="utf-8"))
             for key, path in PATHS.items()}
    source = g8_coverage(*(feeds[k] for k in PATHS), today)
    ledger = build_ledger(root, today)
    return combine(source, ledger)


def markdown(r):
    lines = [
        "## Macro G8 — audit congiunto pre-ricertificazione",
        "",
        f"**Integrità delle fonti:** {r['source_lineage']} · "
        f"**Nuova baseline autorizzata:** NO",
        f"Macro {r['macro_baseline_as_of']} · Prezzo {r['price_as_of']} · "
        f"16 input Macro e 28 coppie verificati",
        "",
        "| Valuta | Inflazione · prima uscita | Lavoro · prima uscita | Growth | Rates | Pricing |",
        "|---|---|---|---|---|---|",
    ]
    for c, v in r["currency_gates"].items():
        date_or_status = lambda dim: (
            v["source_ready"][dim]["first_release_date"] or
            v["source_ready"][dim]["latest_release_grade"]) + " · " + \
            v["source_ready"][dim]["latest_release_grade"]
        lines.append(f"| {c} | {date_or_status('inflation')} | "
                     f"{date_or_status('labour')} | RULE NOT CERTIFIED | "
                     f"{v['rates']} | {v['policy_pricing']} |")
    lines += ["", "**Prove ultime uscite:** " + ", ".join(
        f"{name}={value}" for name, value in r["release_grades"].items()),
        "", "### Blocchi da chiudere prima di generare una nuova tesi",
        *("- " + x for x in r["mandatory_open_gates"]), "",
        "**I successi GitHub Actions certificano integrità delle pipeline, non "
        "un nuovo D.json.** Le preferenze delle 28 coppie restano storiche. "
        "Nessuna data osservata viene trattata come timestamp di rilascio.", ""]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--asof", default=datetime.now(ZoneInfo("Europe/Rome")).date().isoformat())
    p.add_argument("--out", type=Path)
    p.add_argument("--markdown", type=Path)
    args = p.parse_args()
    result = run(today=date.fromisoformat(args.asof))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown(result), encoding="utf-8")
    print(json.dumps({k: result[k] for k in
          ("status", "source_rows_compared", "pair_count",
           "release_grades", "safe_to_publish_new_D")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
