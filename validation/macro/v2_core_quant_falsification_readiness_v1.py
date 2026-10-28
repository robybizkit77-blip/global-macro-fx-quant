#!/usr/bin/env python3
"""Read-only Macro V2 quantitative falsification/readiness gate.

Joins the already-versioned 8-country explicit domestic formula candidate,
frozen canonical 28-pair universe, historical pseudo-OOS research, Beta
PDF gates, and append-only Forward DECISION journal vs receipt provenance.

This is not model performance validation. No alpha/rank/backtest/pair scoring
is invented. Successful CI validates the logic of the NOT-READY gates, NOT
trading quality or a new Core. No write outside /tmp.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from collections import Counter
from datetime import date
from pathlib import Path

from validation.macro.v2_domestic_candidate_explicit_formula_v1 import (
    FORMULA, G8, build as candidate_build, run as candidate_run
)
from validation.forward.audit_beta_forward_launch_readiness_v1 import (
    BETA, SCHEMA as FORWARD_SCHEMA, DECISIONS, OUTCOMES, ROOT,
    _read_lines, inspect as forward_inspect,
)

SCHEMA="GMFQ_MACRO_V2_CORE_QUANT_PRELAUNCH_FALSIFICATION_READINESS_V1"
CORE=ROOT/"live_data/sections/D.json"
PAIR=ROOT/"live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json"
WALKFORWARD=ROOT/"validation/HISTORICAL_WALKFORWARD_V93_CONCLUSION_2026-10-01.json"
RECEIPTS=ROOT/"validation/forward/receipts"
EVALUATION_DAY="2026-10-28"
CANDIDATE_DAY="2026-10-27"

def need(ok,why):
    if not ok:
        raise ValueError("MACRO_CORE_QUANT_FALSIFICATION_GATE_REJECTED: "+why)

def prior_pair_universe(core, setup):
    valid_pairs={frozenset((a,b)) for a,b in itertools.combinations(G8,2)}
    core_rows=core.get("pairs")
    setup_rows=setup.get("pairs")
    need(core.get("asOf")=="2026-09-25" and
         set(core.get("macro",{}))==set(G8) and
         len(core_rows or [])==28 and isinstance(setup_rows,dict) and
         len(setup_rows)==28 and setup.get("pair_count")==28 and
         setup.get("macro_baseline_asof")==core["asOf"] and
         setup.get("schema")=="GMFQ_PAIR_SETUP_OPERATIONAL_VIEW_V1",
         "frozen G8 Core and 28 pair setup baseline integrity")
    keys=[r.get("pair") if isinstance(r,dict) else None for r in core_rows]
    need(len(set(keys))==28 and set(keys)==
         {r.get("canonical_pair") for r in setup_rows.values()} and
         set(core.get("pairStates",{}))==set(keys),
         "same 28 pair keys must exist in frozen Core, states, and setup")
    pair_set=set()
    for k in keys:
        need(isinstance(k,str) and k.count("/")==1, "pair label")
        a,b=k.split("/")
        need(a in G8 and b in G8 and a!=b and frozenset((a,b)) in valid_pairs,
             "not a valid unordered G8 cross")
        pair_set.add(frozenset((a,b)))
    need(pair_set==valid_pairs and len(pair_set)==28,
         "full 28 combination coverage, no directional duplicates")
    return {
        "currencies":8,"canonical_unique_unordered_pairs":28,
        "macro_baseline_as_of":core["asOf"],
        "pair_price_as_of":setup.get("price_asof"),
        "baseline_matches_pair_engine":True,
        "same_date_macro_and_fx_prices":core["asOf"]==setup.get("price_asof"),
    }

def receipt_reconciliation(receipts,decisions):
    # Receipt is evidence of a command's reported result, NOT the actual
    # append-only journal. Reconcile by explicit run ID and UTC cutoff.
    by_batch=Counter((x.get("run_id"),x.get("decision_cutoff")) for x in decisions)
    rows=[]
    for x in sorted(receipts,key=lambda r:(r["decision_cutoff"],r["run_id"])):
        r=x.get("result") or {}
        need(x.get("schema")=="GMFQ_CORE_FORWARD_DECISION_LOGGER_RECEIPT_V1"
             and x.get("status")=="PASS" and
             x.get("no_forward_outcomes_in_snapshot") is True
             and x.get("observational_only") is True
             and isinstance(x.get("run_id"),str)
             and isinstance(x.get("decision_cutoff"),str)
             and type(r.get("total_candidates")) is int
             and r["total_candidates"]==28
             and type(r.get("written")) is int
             and 0<=r["written"]<=28
             and type(r.get("duplicates_skipped")) is int
             and 0<=r["duplicates_skipped"]<=28,
             "dated forward receipt provenance and count format")
        stored=by_batch[(x["run_id"],x["decision_cutoff"])]
        missing=max(0,r["written"]-stored)
        rows.append({
            "run_id":x["run_id"],
            "decision_cutoff":x["decision_cutoff"],
            "receipt_reported_writes":r["written"],
            "receipt_reported_duplicate_skips":r["duplicates_skipped"],
            "persisted_matching_decision_rows":stored,
            "unreconciled_claimed_writes":missing,
            "receipt_does_not_replace_decision_journal":True,
            "can_count_as_prospective_OOS_sample":False,
            "status":("RECEIPT_REPORTS_WRITES_NOT_IN_ARCHIVED_JOURNAL"
                      if missing else
                      "MATCHED_JOURNAL_OR_ZERO_WRITES_NOT_PERFORMANCE")
        })
    return rows

def evaluate(*,candidate,forward,history,core,setup,receipts,decisions,as_of=EVALUATION_DAY):
    need(as_of==EVALUATION_DAY,"dated 28 October audit only, not live intraday claim")
    universe=prior_pair_universe(core,setup)
    need(date.fromisoformat(universe["macro_baseline_as_of"]) <= date.fromisoformat(as_of)
         and date.fromisoformat(universe["pair_price_as_of"]) <= date.fromisoformat(as_of),
         "no future-dated macro or FX prices")
    need(candidate.get("schema")=="GMFQ_MACRO_V2_EXPLICIT_DOMESTIC_CANDIDATE_V1"
         and candidate.get("formula_version")==FORMULA
         and candidate.get("economic_as_of")==CANDIDATE_DAY
         and candidate.get("legacy_core_as_of")==core["asOf"]
         and candidate.get("historical_first_publication_PIT_not_certified") is True
         and candidate.get("out_of_sample_falsification_not_completed") is True
         and candidate.get("canonical_core_score_formula_recovered") is False
         and candidate.get("safe_to_publish_D") is False
         and candidate.get("safe_to_use_for_beta") is False
         and candidate.get("safe_to_use_for_forward") is False
         and candidate.get("writes_live_data") is False,
         "only unpromoted transparent domestic formula candidate")
    country=candidate.get("countries")
    need(isinstance(country,dict) and set(country)==set(G8) and
         candidate.get("summary",{}).get("currencies")==8 and
         candidate.get("summary",{}).get("axes")==24 and
         candidate["summary"].get("FX_scores_produced")==0 and
         candidate["summary"].get("D_json_rebuilt") is False,
         "24 within-country axes, zero currency signals")
    stable,unstable=[],[]
    caveated,estimated=[],[]
    for c in G8:
        x=country[c]
        need(x.get("FX_strength_candidate") is None and
             x.get("eligible_to_recalculate_28_pairs") is False and
             x.get("eligible_for_beta_forward") is False and
             x.get("legacy_D_numbers_are_NOT_in_new_candidate_units") is True
             and x.get("weights_growth_labour")==[0.5,0.5],
             "candidate local economic axis cannot be FX strength or legacy D scalar")
        g,l,p=(x["growth_within_history_z"],
               x["unemployment_tightness_within_history_z"],
               x["inflation_pressure_within_history_z"])
        need(all(type(v) in (float,int) and math.isfinite(v) for v in (g,l,p))
             and abs(x["domestic_activity_candidate_z"]-(0.5*g+0.5*l))<1e-10,
             "50/50 equation must reproduce candidate output; inflation separate")
        scenarios=x["growth_weight_sensitivity_z"]
        need(set(scenarios)=={"25","50","75"} and
             all(abs(scenarios[str(w)]-((w/100)*g+(1-w/100)*l))<1e-10
                 for w in (25,50,75)),
             "fixed 25/50/75 stress scenarios, not tuned to market outcomes")
        stability=x["activity_class_stable_across_25_50_75pct_growth"]
        need(type(stability) is bool, "weight sensitivity must be measured")
        (stable if stability else unstable).append(c)
        if x["source_quality_flags"]:caveated.append(c)
        if any(z.get("is_estimate") is True for z in
               x.get("source_quality_details",{}).values()):estimated.append(c)
    need(candidate["summary"]["countries_unstable_to_weights"]==len(unstable)
         and candidate["summary"]["countries_with_estimates"]==len(estimated),
         "candidate reported sensitivity/uncertainty not recomputable")

    need(history.get("status")=="NO_RULE_CHANGE__PSEUDO_OOS_ONLY"
         and history.get("model_rules_version")=="9.3-pair-attention-hierarchy",
         "historical study must remain original legacy pseudo-OOS only")
    finding=history["findings"]["strong_12w"]
    nonoverlap=finding["nonoverlap_quarterly_basket"]
    need(type(nonoverlap.get("n_checkpoints")) is int
         and nonoverlap["n_checkpoints"]>0
         and type(nonoverlap.get("mean_pct")) in (int,float)
         and history["findings"]["partial_12w"]["n"]>0,
         "the frozen legacy historical OOS summary needs actual tested observations")
    need(forward.get("state")=="NOT_READY_FOR_FINAL_LAUNCH_SIGNOFF"
         and forward.get("beta_promoted") is False
         and forward.get("forward_performance_promoted") is False
         and forward["forward"]["performance_verified_oos"] is False
         and forward["beta"]["strategy_beta_validated"] is False,
         "forward and Beta independent truth gate cannot be promoted")
    need(forward["forward"]["decision_rows"]==len(decisions),
         "forward audit must reflect actual persisted JSONL journal")
    receipt_rows=receipt_reconciliation(receipts,decisions)
    mismatch=[x for x in receipt_rows if x["unreconciled_claimed_writes"]>0]
    latest_journal=max((r["decision_cutoff"] for r in decisions),default=None)
    required=[
      {"gate":"CURRENT_FORMULA_NUMERIC_REPRODUCTION",
       "state":"VERIFIED_RESEARCH_MATH_ONLY",
       "reason":"8 within-country 50/50 equations and 25/50/75 stress cases independently checked"},
      {"gate":"SOURCE_RELEASE_DAY_PIT_24_AXES",
       "state":"BLOCKED",
       "reason":"GDP/Inflation/Labour true joint issuer-date source vintages not certified"},
      {"gate":"CROSS_COUNTRY_COMPARABLE_FX_STRENGTH",
       "state":"BLOCKED",
       "reason":"within-series Z scores and domestic activity cannot be used as G8 relative FX ranking"},
      {"gate":"INDEPENDENT_HISTORIC_OOS_FALSIFICATION",
       "state":"BLOCKED",
       "reason":"existing 2018–2026 v9.3 study uses retrospectively revised histories, pseudo-OOS only"},
      {"gate":"FORWARD_REALTIME_DECISION_JOURNAL",
       "state":"BLOCKED",
       "reason":"legacy one-date smoke archive and some receipt claims lack archived matching decisions"},
      {"gate":"FORWARD_REALIZED_OUTCOMES_AND_COSTS",
       "state":"BLOCKED",
       "reason":"no independently validated future outcomes or price/cost evidence"},
      {"gate":"BETA_PDF_OOS_HEDGE_VARIANCE",
       "state":"BLOCKED",
       "reason":"52W observational beta and pseudo-OOS do not certify point-in-time sources or OOS hedge effectiveness"},
      {"gate":"REBUILD_CORE_D_AND_RECOMPUTE_28_PAIRS",
       "state":"BLOCKED",
       "reason":"original legacy scoring generator unavailable; new candidate not calibrated, PIT certified or forward tested"},
    ]
    output={
      "schema":SCHEMA,
      "research_as_of":as_of,
      "status":"RESEARCH_QUANT_MATH_CHECKED__PIT_OOS_AND_OPERATIONAL_PROMOTION_BLOCKED",
      "model_under_test":"NEW_EXPLICIT_50_50_DOMESTIC_ACTIVITY_NOT_LEGACY_D_NOT_FX_STRENGTH",
      "candidate_formula_version":FORMULA,
      "research_math_not_predictive_validation":True,
      "universe":universe,
      "formula_stress":{
          "eight_currencies":8,"economic_axes":24,
          "tested_growth_weights":[0.25,0.50,0.75],
          "stable_across_weights":stable,"unstable_across_weights":unstable,
          "source_caveat_currencies":caveated,
          "source_estimate_currencies":estimated,
          "candidate_has_no_28_pair_signal":True,
      },
      "historical_legacy_pseudo_OOS":{
          "model_rules_version":history["model_rules_version"],
          "study_status":history["status"],
          "nonoverlap_quarterly_strong_12w_basket_checkpoints":nonoverlap["n_checkpoints"],
          "nonoverlap_quarterly_strong_12w_basket_mean_pct":nonoverlap["mean_pct"],
          "cannot_reuse_as_new_domestic_formula_OOS":True,
          "proven_new_model_out_of_sample_performance":False,
      },
      "forward_truth":{
          "decision_rows_in_actual_journal":forward["forward"]["decision_rows"],
          "journal_unique_cutoffs":forward["forward"]["unique_cutoff_instants"],
          "journal_distinct_runs":forward["forward"]["distinct_run_ids"],
          "last_actual_journal_cutoff":latest_journal,
          "realized_outcome_rows":forward["forward"]["outcome_rows"],
          "receipt_records":receipt_rows,
          "receipt_batches_claiming_written_rows_absent_from_journal":len(mismatch),
          "some_receipts_do_not_establish_archived_decisions":len(mismatch)>0,
          "snapshots_not_equivalent_to_trading_evidence":True,
          "first_forward_eval_certified":False,
      },
      "beta_truth":{
          "observational_contract_present":forward["beta"]["observational_contract_present"],
          "strategy_beta_validated":False,
          "historical_PIT_52w_panel_certified":False,
          "strict_OOS_variance_reduction_certified":False,
      },
      "gates":required,
      "summary":{
          "mathematical_research_gates_checked":1,
          "unmet_or_blocked_launch_quant_gates":sum(g["state"]=="BLOCKED" for g in required),
          "source_first_release_completeness_certified":False,
          "FX_backtest_evidence_certified":False,
          "Beta_forward_validation_complete":False,
          "new_core_scores_published":0,
          "FX_pair_rankings_recomputed":0,
      },
      "safe_to_publish_new_D":False,
      "safe_to_recalculate_28_pairs":False,
      "safe_to_claim_quantitative_predictive_validation":False,
      "safe_to_claim_Beta_forward_OOS_success":False,
      "writes_live_data":False,
    }
    output["receipt_sha256"]=hashlib.sha256(json.dumps(output,sort_keys=True,
                 separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    return output

def run(*,as_of=EVALUATION_DAY):
    candidate=candidate_run(as_of=CANDIDATE_DAY)
    core=json.loads(CORE.read_text(encoding="utf-8"))
    setup=json.loads(PAIR.read_text(encoding="utf-8"))
    historical=json.loads(WALKFORWARD.read_text(encoding="utf-8"))
    decisions=_read_lines(DECISIONS)
    forward=forward_inspect(json.loads(BETA.read_text()),
                            json.loads(FORWARD_SCHEMA.read_text()),
                            decisions,_read_lines(OUTCOMES))
    files=sorted(RECEIPTS.glob("2026-10-*_V1.json"))
    # All canonical V1 receipts in the archived directory, no network.
    files=sorted(RECEIPTS.glob("*__*__V1.json"))
    receipts=[json.loads(p.read_text(encoding="utf-8")) for p in files]
    need(len(files)>=3,"need source receipts including Oct14/26/27")
    return evaluate(candidate=candidate,forward=forward,history=historical,
                    core=core,setup=setup,receipts=receipts,decisions=decisions,
                    as_of=as_of)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--as-of",default=EVALUATION_DAY)
    p.add_argument("--out",type=Path)
    opts=p.parse_args()
    if opts.out: need(opts.out.resolve().is_relative_to(Path("/tmp")),
                      "only dated research receipts in /tmp")
    output=run(as_of=opts.as_of)
    if opts.out:
        opts.out.parent.mkdir(parents=True,exist_ok=True)
        opts.out.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":output["status"],
      "formula":output["candidate_formula_version"],
      "gate_states":{x["gate"]:x["state"] for x in output["gates"]},
      "unreconciled_forward_receipt_batches":
          output["forward_truth"]["receipt_batches_claiming_written_rows_absent_from_journal"],
      "safe_to_publish_new_D":False},sort_keys=True))

if __name__=="__main__":
    main()
