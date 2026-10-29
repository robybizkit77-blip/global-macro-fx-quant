#!/usr/bin/env python3
"""Capture today's V2 domestic RESEARCH context alongside certified ECB T0.

This is a feature-observation freeze, NOT a new Core, trade, signal, PIT
backtest, or validated forward forecast. Only the actual after-19:00 Rome
cutoff is admissible; no past days can be backfilled as if observed live.

The capture is independent of the legacy Core decision journal. It only
freezes contemporaneously available research features so future, genuinely
observed ECB prices can be compared without revising these features.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from validation.forward.admit_frozen_core_prospective_capture_v1 import (
    assess, G8
)
from validation.forward.observe_official_ecb_reference_outcomes_v1 import (
    cross, source_map
)
from validation.macro.v2_domestic_candidate_explicit_formula_v1 import (
    run as domestic_run
)
from validation.macro.v2_core_beta_evidence_desk_v1 import (
    build as evidence_build, read as read_live
)

ROOT = Path(__file__).resolve().parents[2]
JOURNAL = ROOT / "validation/forward/candidate_shadow_snapshots/V2_MACRO_EVIDENCE_SNAPSHOTS_V1.jsonl"
ROME = ZoneInfo("Europe/Rome")
SCHEMA = "GMFQ_V2_PROSPECTIVE_RESEARCH_FEATURE_FREEZE_V1"
SOURCE = "live_data/sections/ECB_G8_PRICE_HISTORY.json"
PAIR_SOURCE = "live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json"
HISTORICAL_BACKFILL_ALLOWED = False


def require(ok, label):
    if not ok:
        raise ValueError("V2_PROSPECTIVE_RESEARCH_CAPTURE_BLOCKED: " + label)


def canonical(item):
    return (json.dumps(item, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def sha(item):
    return hashlib.sha256(canonical(item)).hexdigest()


def file_sha(name):
    return hashlib.sha256((ROOT/name).read_bytes()).hexdigest()


def cutoff_valid(cutoff, current):
    require(isinstance(cutoff, datetime) and cutoff.tzinfo is not None
            and cutoff.utcoffset() is not None, "UTC-aware cutoff required")
    require(isinstance(current, datetime) and current.tzinfo is not None
            and current.utcoffset() is not None, "actual now required")
    utc = cutoff.astimezone(timezone.utc)
    now = current.astimezone(timezone.utc)
    # A CLI invocation cannot pass in an old or a future cutoff and thereby
    # fabricate prospective economic features out of revised archives.
    require(0 <= (now-utc).total_seconds() <= 300,
            "no historical replay or future cutoff; maximum actual lag 5 min")
    local = utc.astimezone(ROME)
    require(local.weekday() < 5 and local.hour >= 19,
            "only real observed evening weekday captures")
    return utc, local.date().isoformat()


def two_year_instrument_identity(rates, ccy, observed_yield):
    """Freeze comparable sovereign 2Y series metadata, never infer a trade.

    Existing pre-feature snapshots remain untouched and intentionally lack
    this fingerprint. Normalization removes source publication dates ONLY;
    issuer, curve definition and series label stay in the original record.
    A missing/inconsistent source is H1-ineligible, NOT a V2 capture failure.
    """
    item=rates.get(ccy, {})
    raw=item.get("source")
    history=item.get("history2")
    tenors=item.get("tenors")
    if not isinstance(raw,str) or not isinstance(history,dict) or not isinstance(tenors,list):
        return None
    label=history.get("label")
    entry=next((v for v in tenors if isinstance(v,dict) and v.get("tenor")=="2Y"), None)
    reported=item.get("2Y")
    if (not isinstance(label,str) or not label.strip()
            or not raw.strip() or not isinstance(entry,dict)
            or type(reported) not in (int,float)
            or type(observed_yield) not in (int,float)
            or type(entry.get("value")) not in (int,float)
            or not all(math.isfinite(float(v)) for v in
                       (reported, observed_yield, entry["value"]))
            or not math.isclose(reported,observed_yield,rel_tol=1e-8,abs_tol=1e-8)
            or not math.isclose(entry["value"],observed_yield,rel_tol=1e-8,abs_tol=1e-8)):
        return None
    definition=re.sub(r"\\s*·\\s*20\\d{2}-\\d{2}-\\d{2}","",raw).strip()
    return definition+" | "+label.strip()+" | 2Y"


def make(cutoff, now, *, fx, pair_setup, legacy, candidate, banks, ois, rates,
         source_hashes):
    utc, day = cutoff_valid(cutoff, now)
    admitted = assess(utc, fx, pair_setup, legacy)
    require(admitted["status"] == "ADMITTED_PROSPECTIVE_BASELINE_OBSERVATION",
            "existing official ECB 28-pair admission rejected: " +
            ",".join(admitted["checks"]))
    require(candidate["economic_as_of"] == day,
            "V2 economic research must be recomputed/re-frozen for actual date")
    evidence = evidence_build(candidate, legacy, pair_setup, banks, ois,
                              rates, as_of=day)
    require(evidence["summary"]["new_country_FX_scores"] == 0
            and evidence["summary"]["new_pair_theses"] == 0
            and evidence["safe_to_republish_D"] is False
            and evidence["eligible_for_forward_trade_attribution"] is False,
            "shadow evidence is not an authorized market predictor")
    dates = source_map(fx)
    obs = dates.get(utc.astimezone(ROME).date())
    require(obs is not None and fx.get("last_as_of") == day,
            "no current actual ECB reference fixing")
    hashes = source_hashes
    require(set(hashes) == {"ecb","pair_setup","legacy_core","candidate",
                           "native_cb","ois_view","native_rates"}
            and all(isinstance(v,str) and len(v)==64 and
                    all(ch in "0123456789abcdef" for ch in v) for v in hashes.values()),
            "immutable named input digests")
    require(hashes["candidate"] == sha(candidate),
            "candidate feature hash must exactly match assembled vector")
    # Purely observed ECB reference FX ratio at capture, NOT executable spot.
    # No market direction, trade side, entry, prediction or model output.
    t0 = {}
    for row in evidence["pairs"]:
        pair = row["pair"]
        a,b = pair.split("/")
        r = cross(obs, a, b)
        require(type(r) is float and math.isfinite(r) and r>0,
                "missing certified T0 pair reference: "+pair)
        t0[pair] = {
            "rate": r, "date": day, "source": SOURCE,
            "layer": "ECB_DAILY_REFERENCE_NOT_EXECUTABLE_SPOT",
            "trade_execution_price": False
        }
    require(len(t0) == 28, "all 28 reference prices must freeze together")
    features = {}
    for ccy in G8:
        row = evidence["countries"][ccy]
        source = candidate["countries"][ccy]
        require(source["eligible_for_beta_forward"] is False
                and source["FX_strength_candidate"] is None,
                ccy+" cannot claim approved FX strength")
        features[ccy] = {
            "economic_observation_as_of": day,
            "domestic_activity_z_within_own_history": source[
                "domestic_activity_candidate_z"],
            "growth_z_own_history": source["growth_within_history_z"],
            "labour_tightness_z_own_history": source[
                "unemployment_tightness_within_history_z"],
            "inflation_pressure_z_own_history": source[
                "inflation_pressure_within_history_z"],
            "central_activity_class": row["domestic_class_central_50pct"],
            "weight_invariant_class_only": row[
                "domestic_class_robust_25to75pct"],
            "source_quality": source["source_quality_details"],
            "economic_quality_flags": source["source_quality_flags"],
            "cb_statement_date": row["cb_statement_date"],
            "cb_communicated_WANT_not_prediction": row[
                "cb_communicated_bias_snapshot"],
            "cb_CAN_not_calibrated": True,
            "six_month_rate_source_class": row["six_month_source_class"],
            "six_month_rate_pct_context_only": row[
                "six_month_rate_pct_descriptive_only"],
            "six_month_policy_delta_bp": row["six_month_policy_delta_bp"],
            "bond_date": row["official_bond_date"],
            "bond_age_days_at_capture": row["bond_age_days"],
            "two_year_observed_yield_pct": row["two_year_yield_pct"],
            "two_year_instrument_identity": two_year_instrument_identity(
                rates, ccy, row["two_year_yield_pct"]),
            "ten_year_observed_yield_pct": row["ten_year_yield_pct"],
            "FX_signal": None, "trade_entry": None
        }
    frozen_legacy = {p["pair"]: {
        "quality":p["existing_legacy_setup_quality_NOT_recalculated"],
        "price_state":p["existing_legacy_price_state"],
        "source":"LEGACY_SEP25_D_PLUS_OCT_OBSERVED_PRICE_NOT_NEW_V2"}
        for p in evidence["pairs"]}
    body = {
        "schema": SCHEMA,
        "status": "OBSERVATIONAL_FEATURES_FROZEN_RESEARCH_ONLY_NOT_FORWARD_MODEL",
        "capture_at_utc": utc.isoformat().replace("+00:00","Z"),
        "local_date_rome": day,
        "economic_checked_as_of": candidate["economic_as_of"],
        "old_core_as_of": legacy["asOf"],
        "official_ecb_t0_date": day,
        "observed_t0_ref": t0,
        "domestic_v2_features": features,
        "old_core_pair_context_UNCHANGED": frozen_legacy,
        "original_source_sha256": hashes,
        "candidate_receipt_sha256": candidate["receipt_sha256"],
        "integrated_evidence_receipt_sha256": evidence["receipt_sha256"],
        "snapshot_may_be_compared_later_with_independent_ecb_reference_returns": True,
        "historical_issuer_PIT_backtest_certified": False,
        "future_outcomes_observed_at_capture": False,
        "executable_t0_prices_certified": False,
        "V2_currency_FX_strength_calibrated": False,
        "V2_pair_directional_predictions": False,
        "FX_COT_OIS_causality_calibrated": False,
        "allowed_for_beta_hedge_performance": False,
        "eligible_for_real_trading_or_sizing": False,
        "core_D_recalculated": False,
        "pair_rankings_recalculated": False,
    }
    body["snapshot_id"] = sha({
        "schema":SCHEMA,"local_date_rome":day,
        "t0_source_sha256": hashes["ecb"],
        "candidate_sha256": hashes["candidate"]
    })
    body["snapshot_sha256"] = sha(body)
    return body


def verify_journal(entries):
    days=set()
    for e in entries:
        require(e.get("schema")==SCHEMA and
                e.get("snapshot_sha256") == sha({
                    k:v for k,v in e.items() if k!="snapshot_sha256"
                }), "modified existing shadow snapshot")
        d=e.get("local_date_rome")
        require(d not in days and e.get("official_ecb_t0_date")==d,
                "duplicate or mismatched prospective capture dates")
        days.add(d)
        require(e.get("future_outcomes_observed_at_capture") is False and
                e.get("V2_pair_directional_predictions") is False and
                e.get("core_D_recalculated") is False,
                "past journal may not be promoted")
    return days


def append(snapshot, *, path=JOURNAL, dry_run=False):
    entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip()] if path.is_file() else []
    dates = verify_journal(entries)
    require(snapshot.get("schema")==SCHEMA
            and snapshot.get("snapshot_sha256")==sha({
                k:v for k,v in snapshot.items() if k!="snapshot_sha256"
            }), "candidate snapshot has incorrect integrity seal")
    if snapshot["local_date_rome"] in dates:
        return "EXISTING_DATE_ALREADY_FROZEN_NO_OVERWRITE"
    if dry_run:
        return "VALID_FIRST_DAY_DRY_RUN_NO_WRITE"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as f:
        f.write(canonical(snapshot))
    return "PROSPECTIVE_SHADOW_RESEARCH_SNAPSHOT_APPEND_OK"


def attempt(*, cutoff, now, dry_run=False, path=JOURNAL):
    utc, day = cutoff_valid(cutoff, now)
    existing = [json.loads(v) for v in path.read_text(encoding="utf-8").splitlines()
                if v.strip()] if path.exists() else []
    if day in verify_journal(existing):
        return {"status":"EXISTING_DATE_ALREADY_FROZEN_NO_OVERWRITE",
                "local_date":day,"appended":0}
    fx=read_live("ECB_G8_PRICE_HISTORY")
    pairs=read_live("PAIR_SETUP_OPERATIONAL_VIEW")
    core=read_live("D")
    admission=assess(utc,fx,pairs,core)
    if admission["status"]!="ADMITTED_PROSPECTIVE_BASELINE_OBSERVATION":
        return {"status":"BLOCKED_NO_OFFICIAL_SAME_DAY_T0_NO_V2_CAPTURE",
                "local_date":day,"admission_checks":admission["checks"],
                "appended":0}
    candidate=domestic_run(as_of=day)
    source_paths={
        "ecb":"live_data/sections/ECB_G8_PRICE_HISTORY.json",
        "pair_setup":"live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json",
        "legacy_core":"live_data/sections/D.json",
        "native_cb":"live_data/sections/NATIVE_CB_DATA.json",
        "ois_view":"live_data/sections/OIS_OPERATIONAL_VIEW.json",
        "native_rates":"live_data/sections/NATIVE_RATES_DATA.json",
    }
    hashes={key:file_sha(name) for key,name in source_paths.items()}
    hashes["candidate"]=sha(candidate)
    snap=make(utc, now,fx=fx,pair_setup=pairs,legacy=core,
              candidate=candidate,banks=read_live("NATIVE_CB_DATA"),
              ois=read_live("OIS_OPERATIONAL_VIEW"),
              rates=read_live("NATIVE_RATES_DATA"),source_hashes=hashes)
    status=append(snap,path=path,dry_run=dry_run)
    return {"status":status,"local_date":day,
            "snapshot_id":snap["snapshot_id"],
            "snapshot_sha256":snap["snapshot_sha256"],
            "new_V2_pair_signals":0, "future_outcomes_at_capture":0,
            "appended":int(status=="PROSPECTIVE_SHADOW_RESEARCH_SNAPSHOT_APPEND_OK")}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--dry-run",action="store_true")
    args=parser.parse_args()
    # Time is sampled by this process only; NO --as-of or --decision-cutoff
    # option intentionally exists to prevent forged backfilled snapshots.
    now=datetime.now(timezone.utc)
    report=attempt(cutoff=now,now=now,dry_run=args.dry_run)
    print(json.dumps(report,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
