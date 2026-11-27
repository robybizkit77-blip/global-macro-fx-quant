#!/usr/bin/env python3
"""Publish a source-verifiable V3 Macro observation snapshot for Control Room.

Output is a separate website research JSON file. It does NOT modify the
canonical D.json/28-pair structural states, nor make any currency forecasts.
Only audited raw economic observations and contextual pair comparisons.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.macro.v3_current_g8_28pair_economic_evidence_v1 import (
    FX, ROOT, SCHEMA as SOURCE_SCHEMA, run
)

SCHEMA = "GMFQ_MACRO_V3_G8_28PAIR_PUBLIC_OBSERVED_CONTEXT_V1"
TARGET = ROOT / "site/control-room-preview/macro-v3-current-evidence.json"


def ensure(ok, why):
    if not ok:
        raise ValueError("MACRO_V3_PUBLICATION_REJECTED: " + why)


def snapshot(src, momentum=None, dynamics=None, sectors=None):
    day = datetime.now(ZoneInfo("Europe/Rome")).date()
    ensure(src.get("schema") == SOURCE_SCHEMA
           and src.get("status") == "COMPLETE_CURRENT_ECONOMIC_OBSERVATION_8_G8_28_PAIRS_NOT_FX_SIGNAL"
           and src.get("summary", {}).get("currencies") == 8
           and src["summary"].get("economic_dimensions") == 24
           and src["summary"].get("latest_observation_values_present") == 24
           and src["summary"].get("pairs") == 28
           and src["summary"].get("pair_trade_signals_generated") == 0
           and src.get("safe_to_republish_D") is False
           and src.get("safe_to_recompute_structural_pair_theses") is False
           and src.get("eligible_for_trading_or_forward_backtest") is False
           and src.get("point_in_time_historical_backtest_certified") is False
           and src.get("writes_live_data") is False,
           "attempt to promote observed source into a validated FX model")
    asof = datetime.fromisoformat(src["as_of"]).date()
    ensure(asof <= day and asof >= day - timedelta(days=1),
           "source build day is stale or in future")
    countries = src.get("country_evidence", {})
    pairs = src.get("pair_context", {})
    ensure(set(countries) == set(FX) and len(pairs) == 28,
           "missing G8 dimensions or 28 pair coverage")
    for c, row in countries.items():
        ensure(row.get("macro_score") is None and row.get("FX_strength") is None
               and row.get("country_relative_rank") is None
               and row.get("not_a_trade_or_policy_signal") is True
               and all(isinstance(row.get(k), dict) for k in ("growth", "labour", "inflation"))
               and row["growth"].get("is_growth_strength_score") is False,
               c + " operational currency-score contamination")
        for k in ("labour", "inflation"):
            observed = row[k]
            ensure(observed.get("observed_history_revised_not_historic_PIT") is True
                   and observed.get("observation_period_is_not_release_instant") is True
                   and observed.get("normalization_not_required_for_observed_value") is True
                   and observed.get("change_direction") in ("UP", "DOWN", "FLAT")
                   and observed.get("observation_period") and observed.get("series_id")
                   and isinstance(observed.get("observation_value"), (int, float)),
                   c + " source observation not provenance-dated")
    for pair, row in pairs.items():
        ensure(pair == row.get("base", "") + "/" + row.get("quote", "")
               and row.get("pair_trade_bias") is None
               and row.get("estimated_FX_expected_return") is None
               and row.get("recalculated_structural_thesis") is False
               and row.get("labour_change_does_not_prove_FX_appreciation") is True,
               pair + " cannot be a new pair trading signal")

    result = {
        "schema": SCHEMA,
        "status": "OBSERVED_ECONOMIC_CONTEXT_NOT_FX_SIGNAL",
        "generated_europe_rome_day": src["as_of"],
        "canonical_D_macro_baseline_as_of": src["canonical_D_macro_baseline_as_of"],
        "fx_price_as_of": src["fx_price_as_of"],
        "economic_data_coverage": src["economic_data_coverage"],
        "source_value_quality": src["source_value_quality"],
        "source_receipt_sha256": src["receipt_sha256"],
        "source_observation_periods_not_release_days": True,
        "historic_PIT_OOS_not_certified": True,
        "safe_to_republish_D": False,
        "safe_to_recompute_structural_pair_theses": False,
        "eligible_for_trading_or_forward_backtest": False,
        "countries": countries,
        "pair_context": pairs,
        "summary": src["summary"],
    }
    if momentum is not None:
        ensure(momentum.get("schema") == "GMFQ_G8_CURRENT_ACTIVITY_MOMENTUM_RESEARCH_V1"
               and momentum.get("as_of") == src["as_of"]
               and momentum.get("safe_to_publish_D") is False
               and momentum.get("safe_to_update_pairs") is False
               and momentum.get("writes_live_data") is False
               and momentum.get("no_cross_country_momentum_aggregation") is True
               and set(momentum.get("countries", {})) == set(FX),
               "invalid activity momentum diagnostic")
        result["activity_momentum_research"] = momentum
        result["activity_momentum_status"] = "RESEARCH_ONLY"
    else:
        result["activity_momentum_status"] = "WITHHELD"
    if dynamics is not None:
        ensure(dynamics.get("schema") == "GMFQ_G8_LABOUR_INFLATION_DYNAMICS_RESEARCH_V1"
               and dynamics.get("as_of") == src["as_of"]
               and dynamics.get("safe_to_publish_D") is False
               and dynamics.get("safe_to_update_pairs") is False
               and dynamics.get("historical_PIT_certified") is False
               and dynamics.get("no_cross_country_aggregation") is True
               and dynamics.get("writes_live_data") is False
               and set(dynamics.get("countries", {})) == set(FX),
               "invalid labour inflation dynamics")
        result["labour_inflation_dynamics"] = dynamics
        result["labour_inflation_status"] = "RESEARCH_ONLY"
    else:
        result["labour_inflation_status"] = "WITHHELD"
    if sectors is not None:
        ensure(sectors.get("schema") == "GMFQ_G8_SECTOR_FINANCIAL_DYNAMICS_RESEARCH_V1"
               and sectors.get("as_of") == src["as_of"]
               and sectors.get("safe_to_publish_D") is False
               and sectors.get("safe_to_update_pairs") is False
               and sectors.get("historical_PIT_certified") is False
               and sectors.get("no_cross_country_aggregation") is True
               and sectors.get("writes_live_data") is False
               and set(sectors.get("countries", {})) == set(FX),
               "invalid sector and financial dynamics")
        result["sector_financial_dynamics"] = sectors
        result["sector_financial_status"] = "RESEARCH_ONLY"
    else:
        result["sector_financial_status"] = "WITHHELD"
    result["snapshot_content_sha256"] = hashlib.sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False).encode("utf-8")).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=TARGET)
    parser.add_argument("--as-of", default=None)
    args = parser.parse_args()
    target = args.output.resolve()
    ensure(target == TARGET.resolve() or target.is_relative_to(Path("/tmp")),
           "only fixed public research snapshot or /tmp test output permitted")
    src = run(as_of=args.as_of)
    from validation.macro.v2_current_activity_momentum_v1 import run as activity_run
    try:
        result = snapshot(src, activity_run())
    except (ValueError, KeyError, TypeError, OSError) as exc:
        # Preserve independently verified raw macro observations on diagnostic failure.
        print("ACTIVITY_MOMENTUM_WITHHELD:", type(exc).__name__, str(exc), flush=True)
        result = snapshot(src)
    from validation.macro.v2_labour_inflation_dynamics_v1 import run as dynamics_run
    try:
        result = snapshot(src, result.get("activity_momentum_research"), dynamics_run())
    except (ValueError, KeyError, TypeError, OSError, ArithmeticError) as exc:
        print("LABOUR_INFLATION_WITHHELD:", type(exc).__name__, str(exc), flush=True)
    from validation.macro.v2_sector_financial_dynamics_v1 import run as sectors_run
    try:
        result = snapshot(src, result.get("activity_momentum_research"), result.get("labour_inflation_dynamics"), sectors_run())
    except (ValueError, KeyError, TypeError, OSError, ArithmeticError) as exc:
        print("SECTOR_FINANCIAL_WITHHELD:", type(exc).__name__, str(exc), flush=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    target.write_text(encoded, encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "as_of": result["generated_europe_rome_day"],
        "country_count": len(result["countries"]),
        "pair_count": len(result["pair_context"]),
        "source_receipt_sha256": result["source_receipt_sha256"],
        "output": str(target),
        "replaced_D_scores": 0,
        "new_trade_biases": 0,
        "sector_financial_rows": sum(map(len,result.get("sector_financial_dynamics",{}).get("countries",{}).values())),
        "labour_inflation_rows": sum(map(len,result.get("labour_inflation_dynamics",{}).get("countries",{}).values())),
        "activity_momentum_countries": len(result.get("activity_momentum_research", {}).get("countries", {})),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
