#!/usr/bin/env python3
"""Current Macro rebase dependency ledger: 8 legs, 28 pairs, NO new FX score.

Read-only join of already certified source-to-engine/release diagnostics. A
fresh market price or a visually complete estimated rates curve cannot create
a valid new score or a PIT-certified structural preference. Output /tmp only.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from datetime import date
from pathlib import Path

from validation.macro.rebase_joint_gate_v1 import ROOT, run as joint_run
from validation.macro.score_formula_provenance_v1 import run as score_run

SCHEMA = "GMFQ_MACRO_G8_28PAIR_REBASE_DEPENDENCIES_V1"
CCYS = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
H = ("3m", "6m", "12m")
GATES = (
    "NEW_VERSIONED_G8_MACRO_SCORE_EQUATIONS_NOT_CERTIFIED",
    "FULL_HISTORICAL_FIRST_RELEASE_PIT_VINTAGES_NOT_CERTIFIED",
    "RELATIVE_POLICY_AND_FX_MAPPING_NOT_CERTIFIED",
    "INDEPENDENT_28PAIR_OOS_AND_REVISION_VALIDATION_NOT_COMPLETED",
)


def require(ok, reason):
    if not ok:
        raise ValueError("MACRO_REBASE_28PAIR_DEPENDENCIES_REJECTED: " + reason)


def number(x):
    return type(x) in (int, float) and math.isfinite(x)


def validated_day(x, today, label):
    require(isinstance(x, str) and len(x) == 10
            and date.fromisoformat(x).isoformat() == x,
            label + ": noncanonical date")
    day = date.fromisoformat(x)
    require(day <= today, label + ": future observation")
    return day


def build(gate, score, model, setup, rates, ois):
    require(gate.get("schema") == "GMFQ_MACRO_JOINT_REBASE_GATE_V1"
            and gate.get("status") == "AUDITED_NOT_AUTHORIZED_FOR_MACRO_REBASE"
            and gate.get("source_lineage") == "PASS"
            and gate.get("currency_count") == 8
            and gate.get("pair_count") == 28
            and gate.get("source_rows_compared") == 16
            and gate.get("safe_to_publish_new_D") is False
            and gate.get("safe_to_update_pair_thesis") is False
            and gate.get("writes_live_data") is False,
            "upstream joint PIT rebase gate not fail-closed")
    require(score.get("schema") == "GMFQ_MACRO_SCORE_PROVENANCE_BOUNDARY_V1"
            and score.get("status") ==
            "PASS_HISTORICAL_SCORE_READERS_IDENTIFIED_NO_SCORE_GENERATOR_CERTIFIED"
            and score.get("ready_for_numeric_macro_rebase") is False
            and score.get("safe_to_publish_new_D") is False
            and score.get("historical_values_locked_to_first_repo_snapshot") is True
            and score.get("historical_scalar_scores") == 24
            and score.get("pairs_in_source_snapshot") == 28,
            "historical numeric score provenance certification drift")
    require(model.get("asOf") == setup.get("macro_baseline_asof")
            == gate.get("macro_baseline_as_of") == score.get("model_as_of")
            and gate.get("as_of") == score.get("audit_as_of"),
            "canonical Macro/price/model audit dates drift")
    frozen = {ccy: {p: (model.get("macro") or {}).get(ccy, {}).get(p)
                    for p in ("growth", "labour", "inflation", "cycle")}
              for ccy in CCYS}
    actual_sha = hashlib.sha256(json.dumps(
        frozen, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    require(actual_sha == score.get("historical_scores_sha256"),
            "one of 24 frozen scores or eight cycles changed without independent proof")
    require(set(model.get("macro") or {}) == set(CCYS)
            and set(gate.get("currency_gates") or {}) == set(CCYS)
            and set(rates) == set(CCYS)
            and set(ois.get("currencies") or {}) == set(CCYS),
            "canonical G8 source inventory incomplete")
    require(set(gate.get("release_grades") or {}) ==
            {"FULL_RELEASE_INSTANT", "DATE_ONLY",
             "WITHHELD_EXACT_PERIOD_EVIDENCE",
             "WITHHELD_OFFICIAL_SOURCE_VALUE_CONFLICT"}
            and sum(gate["release_grades"].values()) == 16,
            "16 released Inflation/Labour source statuses missing")
    require(setup.get("schema") == "GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1"
            and setup.get("status") == "CURRENT_CANONICAL_ENGINE"
            and setup.get("pair_count") == 28
            and len(setup.get("pairs") or {}) == 28
            and setup.get("entry_level_published") is False
            and setup.get("thesis_is_not_entry") is True,
            "pair operational state is not canonical no-entry")
    require(setup.get("price_asof") == gate.get("price_as_of")
            == score.get("price_as_of"),
            "price layer is not synchronized between validated inventories")
    today = validated_day(gate["as_of"], date.fromisoformat(gate["as_of"]), "run as-of")
    baseline = validated_day(model["asOf"], today, "Macro baseline")
    price = validated_day(setup["price_asof"], today, "ECB price")
    require(baseline <= price, "price predates frozen Macro baseline")
    legs = {}
    for c in CCYS:
        row = gate["currency_gates"][c]
        rate = rates[c]
        ois_row = ois["currencies"][c]
        require(row.get("country") == c
                and row.get("macro_baseline_as_of") == model["asOf"]
                and row.get("historical_scores_preserved") is True
                and row.get("structural_score_status") ==
                    "BLOCKED_VERSIONED_SCORE_AND_COMPLETE_PIT"
                and row.get("growth_rule") == "VERSIONED_RULE_NOT_CERTIFIED",
                c + ": model generation not locked")
        release = row["source_ready"]
        require(set(release) == {"labour", "inflation"}
                and all(d["archival_vintage_certified"] is False
                        and d["score_transform_certified"] is False
                        for d in release.values()),
                c + ": source release mistakenly upgraded to score vintage")
        for pillar in ("growth", "labour", "inflation"):
            require(number(model["macro"][c].get(pillar)),
                    c + ": missing original model pillar")
        rday = validated_day(rate.get("date"), today, c + " government 2Y date")
        oday = validated_day(ois_row.get("as_of"), today, c + " monetary curve date")
        require(ois_row.get("operational_status") in
                ("GREEN_OFFICIAL", "GREEN_ESTIMATED", "WITHHELD"),
                c + ": unknown curve state")
        official_rate = (
            row.get("rates") == "OFFICIAL_CURRENT"
            and "OFFICIAL" in str(rate.get("quality"))
            and number(rate.get("2Y"))
            and number(rate.get("10Y"))
            and (today - rday).days <= 5
        )
        official_ois = (
            row.get("policy_pricing") == "OFFICIAL_CURRENT"
            and ois_row["operational_status"] == "GREEN_OFFICIAL"
            and ois_row.get("quality") == "OFFICIAL_CERTIFIED"
            and ois_row.get("official_status") == "ACTIVE"
            and number((ois_row.get("horizons") or {}).get("6m", {}).get("rate"))
            and (today - oday).days <= 5
        )
        # Estimated/proxy instruments can be visible without becoming official
        # OIS or score features. A conflicted proxy remains descriptive only.
        indicative = (
            ois_row["operational_status"] == "GREEN_ESTIMATED"
            and ois_row.get("backtest_eligible_as_official") is False
            and number((ois_row.get("horizons") or {}).get("6m", {}).get("rate"))
        )
        require(not (official_ois and indicative),
                c + ": estimated futures incorrectly upgraded to official")
        if ois_row["operational_status"] == "WITHHELD":
            require(not official_ois and not indicative,
                    c + ": withheld curve admitted")
        legs[c] = {
            "latest_inflation_observation_period": release["inflation"]["latest_observation_period"],
            "inflation_latest_release_grade": release["inflation"]["latest_release_grade"],
            "latest_labour_observation_period": release["labour"]["latest_observation_period"],
            "labour_latest_release_grade": release["labour"]["latest_release_grade"],
            "growth_series_inventoried": row["growth_sources_inventoried"],
            "growth_score_transform_approved": False,
            "historical_source_vintages_approved": False,
            "government_2y10y_as_of": rday.isoformat(),
            "government_2y10y_official_recent": bool(official_rate),
            "government_yield_instrument_comparability_approved": False,
            "monetary_curve_as_of": oday.isoformat(),
            "monetary_curve_source_status": ois_row["operational_status"],
            "official_monetary_6m_recent": bool(official_ois),
            "indicative_monetary_6m_visible": bool(indicative),
            "monetary_curve_conflicted": ois_row.get("source_conflict_status") ==
                "UNRESOLVED_SECONDARY_SOURCE_SAME_DAY_CONFLICT",
            "monetary_policy_repricing_approved": False,
            "new_legacy_compatible_macro_score": None,
            "new_fx_currency_strength": None,
        }
    expected_universe = {frozenset(c) for c in itertools.combinations(CCYS, 2)}
    observed = set()
    pairs = {}
    for code, item in sorted(setup["pairs"].items()):
        require(len(code) == 6 and code[:3] in legs and code[3:] in legs
                and code[:3] != code[3:], "invalid G8 currency pair")
        a, b = code[:3], code[3:]
        unordered = frozenset((a, b))
        require(unordered not in observed, "duplicate inverted G8 pair")
        observed.add(unordered)
        require(item.get("canonical_pair") == a + "/" + b
                and isinstance(item.get("decision_frame"), dict)
                and isinstance(item.get("setup"), dict),
                code + ": incomplete historical Pair decision")
        p, q = legs[a], legs[b]
        both_2y = p["government_2y10y_official_recent"] and q["government_2y10y_official_recent"]
        both_ois = p["official_monetary_6m_recent"] and q["official_monetary_6m_recent"]
        same_2y = (both_2y and p["government_2y10y_as_of"] == q["government_2y10y_as_of"])
        same_ois = (both_ois and p["monetary_curve_as_of"] == q["monetary_curve_as_of"])
        entire = (same_2y and same_ois and
                  p["government_2y10y_as_of"] == p["monetary_curve_as_of"])
        local = []
        for c in (a, b):
            leg = legs[c]
            if not leg["government_2y10y_official_recent"]:
                local.append(c + ":GOVERNMENT_YIELDS_NOT_CURRENT_OFFICIAL")
            if not leg["official_monetary_6m_recent"]:
                local.append(c + ":NO_CURRENT_OFFICIAL_OIS_6M")
            if leg["monetary_curve_conflicted"]:
                local.append(c + ":SECONDARY_FUTURES_QUOTE_CONFLICT")
            if any(leg[d + "_latest_release_grade"] != "FULL_RELEASE_INSTANT"
                   for d in ("inflation", "labour")):
                local.append(c + ":LATEST_MACRO_RELEASE_TIMESTAMP_NOT_COMPLETE")
        if both_2y and not same_2y:
            local.append("GOVERNMENT_2Y_DATES_DIFFER")
        if both_ois and not same_ois:
            local.append("OFFICIAL_OIS_6M_DATES_DIFFER")
        if same_2y and same_ois and not entire:
            local.append("RATE_AND_OIS_REFERENCE_DATES_DIFFER")
        pairs[code] = {
            "canonical_pair": a + "/" + b,
            "historical_macro_baseline_as_of": baseline.isoformat(),
            "historical_favored": item["setup"].get("structuralFav"),
            "historical_macro_side": item["decision_frame"].get("macroSide"),
            "historical_policy_side": item["decision_frame"].get("policySide"),
            "base_currency": a, "quote_currency": b,
            "current_government_2y_both_official": bool(both_2y),
            "current_government_2y_dates_equal": bool(same_2y),
            "current_monetary_6m_both_official": bool(both_ois),
            "current_monetary_6m_dates_equal": bool(same_ois),
            "full_same_day_2y_and_ois_6m_both_legs": bool(entire),
            "local_data_or_clock_blockers": sorted(set(local)),
            "global_model_blockers": list(GATES),
            "candidate_macro_side": None,
            "candidate_policy_side": None,
            "candidate_favored": None,
            "candidate_score_delta": None,
            "eligible_to_recalculate_structural_fx_thesis": False,
        }
    require(observed == expected_universe and len(pairs) == 28,
            "28 canonical unique G8 pairs not covered")
    require(sum(x["full_same_day_2y_and_ois_6m_both_legs"]
                for x in pairs.values()) <=
            sum(x["current_monetary_6m_both_official"] for x in pairs.values()),
            "source dates promoted beyond official leg coverage")
    result = {
        "schema": SCHEMA,
        "status": "28PAIR_DEPENDENCY_MATRIX_COMPLETE_REBASE_NOT_AUTHORIZED",
        "audit_as_of": gate["as_of"],
        "historical_macro_baseline_as_of": baseline.isoformat(),
        "latest_ecb_price_as_of": price.isoformat(),
        "historical_macro_age_calendar_days": (today - baseline).days,
        "price_minus_baseline_calendar_days": (price - baseline).days,
        "historical_score_provenance_sha256": score["historical_scores_sha256"],
        "source_to_score_generator_certified": False,
        "complete_historical_point_in_time_vintages_certified": False,
        "countries": legs, "pairs": pairs,
        "summary": {
            "currencies": 8, "macro_axes_historical": 24,
            "latest_labour_inflation_source_rows": 16,
            "pairs": 28,
            "countries_government_2y10y_official_recent": sum(
                p["government_2y10y_official_recent"] for p in legs.values()),
            "countries_official_monetary_6m_recent": sum(
                p["official_monetary_6m_recent"] for p in legs.values()),
            "countries_with_conflicted_secondary_quotes": sum(
                p["monetary_curve_conflicted"] for p in legs.values()),
            "pairs_both_2y_official_recent": sum(
                p["current_government_2y_both_official"] for p in pairs.values()),
            "pairs_both_monetary_6m_official_recent": sum(
                p["current_monetary_6m_both_official"] for p in pairs.values()),
            "pairs_full_same_day_2y_ois_6m": sum(
                p["full_same_day_2y_and_ois_6m_both_legs"] for p in pairs.values()),
            "pairs_allowed_to_rebase_structural": 0,
            "new_fx_strength_scores": 0,
            "new_fx_direction_signals": 0,
        },
        "mandatory_global_model_blockers": list(GATES),
        "candidate_D_json": None,
        "candidate_pair_state": None,
        "safe_to_publish_D_json": False,
        "safe_to_update_28_pairs": False,
        "safe_for_beta": False,
        "safe_for_forward": False,
        "writes_live_data": False,
    }
    result["receipt_sha256"] = hashlib.sha256(json.dumps(
        result, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")).hexdigest()
    return result


def run(root=ROOT, as_of="2026-10-31"):
    root = Path(root)
    today = date.fromisoformat(as_of)
    gate = joint_run(root=root, today=today)
    score = score_run(root=root, today=today)
    read = lambda path: json.loads((root / path).read_text(encoding="utf-8"))
    return build(gate, score, read("live_data/sections/D.json"),
                 read("live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json"),
                 read("live_data/sections/NATIVE_RATES_DATA.json"),
                 read("live_data/sections/OIS_OPERATIONAL_VIEW.json"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default="2026-10-31")
    parser.add_argument("--out", type=Path)
    a = parser.parse_args()
    if a.out is not None:
        require(a.out.resolve().is_relative_to(Path("/tmp")),
                "read-only receipt must remain under /tmp")
    result = run(as_of=a.as_of)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    print(json.dumps({"status": result["status"], **result["summary"],
                      "safe_to_publish_D_json": False}, sort_keys=True))


if __name__ == "__main__":
    main()
