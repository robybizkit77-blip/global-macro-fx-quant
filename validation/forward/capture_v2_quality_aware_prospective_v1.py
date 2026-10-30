#!/usr/bin/env python3
"""Future-only V2 QUALITY-AWARE observational capture (separate append-only V1).

Preserves all eight-country growth/inflation/labour research observations and
28 official ECB T0 cross rates even where registered robust z is missing.
This DOES NOT repair/promote the original numerical V2 prospective model,
backfill the legacy ledger, create a trade, backtest, beta, or feed H1.
Registration: 2026-10-30; earliest real capture: 2026-11-02 Rome after 19:00.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, date, timezone
import json
import math
from pathlib import Path

from validation.forward.admit_frozen_core_prospective_capture_v1 import (
    G8, assess, EXPECTED_UNORDERED_G8,
)
from validation.forward.capture_v2_research_prospective_evidence_v1 import (
    ROOT, ROME, canonical, sha, file_sha, cutoff_valid,
)
from validation.forward.observe_official_ecb_reference_outcomes_v1 import (
    cross, source_map,
)
from validation.macro.v2_g8_observed_feature_bridge_v1 import (
    run as economic_run, PILLARS,
)
from validation.macro.v2_zero_mad_ordinal_quality_v1 import (
    build as ordinal_build, POLICY_ID as ORDINAL_POLICY,
    NOT_BEFORE_ROME,
)

SCHEMA = "GMFQ_V2_QUALITY_AWARE_OBSERVATIONAL_FREEZE_V1"
JOURNAL = (ROOT / "validation/forward/candidate_shadow_snapshots/"
           "V2_QUALITY_AWARE_PROSPECTIVE_SNAPSHOTS_V1.jsonl")
SOURCE_PATHS = {
    "ecb": "live_data/sections/ECB_G8_PRICE_HISTORY.json",
    "pair_setup": "live_data/sections/PAIR_SETUP_OPERATIONAL_VIEW.json",
    "legacy_core": "live_data/sections/D.json",
    "macro_series": "live_data/sections/MACRO_SERIES.json",
    "macro_thermometer": "live_data/sections/MACRO_THERMOMETER_DATA.json",
    "macro_registry": "validation/macro/MACRO_SOURCE_REGISTRY_2026-10-08.json",
}
NO_FX_PREDICTION = True
NO_HISTORICAL_BACKFILL = True


def require(ok, message):
    if not ok:
        raise ValueError("V2_QUALITY_AWARE_CAPTURE_BLOCKED: " + message)


def valid_capture_clock(cutoff, now):
    utc, day = cutoff_valid(cutoff, now)
    require(date.fromisoformat(day) >= NOT_BEFORE_ROME,
            "first legitimate local capture is 2026-11-02")
    return utc, day


def validate_snapshot(row):
    require(row.get("schema") == SCHEMA and
            row.get("snapshot_sha256") == sha({
                k:v for k,v in row.items() if k != "snapshot_sha256"
            }), "tampered or incorrect snapshot integrity seal")
    stamp = datetime.fromisoformat(row["capture_at_utc"].replace("Z", "+00:00"))
    require(stamp.tzinfo is not None and stamp.utcoffset() is not None,
            "snapshot timestamp is not aware")
    local = stamp.astimezone(ROME)
    day = local.date().isoformat()
    require(local.weekday() < 5 and local.hour >= 19
            and local.date() >= NOT_BEFORE_ROME
            and row.get("local_date_rome") == day
            and row.get("official_ecb_t0_date") == day
            and row.get("economic_checked_as_of") == day,
            "snapshot dated outside genuine future research cohort")
    require(row.get("status") ==
            "FROZEN_PARTIAL_ECONOMIC_RESEARCH_NO_MODEL_SCORE"
            and row.get("ordinal_protocol") == ORDINAL_POLICY
            and row.get("old_core_recalculated") is False
            and row.get("historical_issuer_PIT_certified") is False
            and row.get("V2_numeric_model_computed") is False
            and row.get("V2_FX_signal_computed") is False
            and row.get("future_outcomes_observed_at_capture") is False
            and row.get("can_feed_preregistered_H1") is False
            and row.get("eligible_for_beta_forward_trading") is False,
            "research-only, non-H1 and no backfilled model guarantees")
    anchors = row.get("observed_t0_ref")
    require(isinstance(anchors, dict) and len(anchors) == 28,
            "all 28 ECB T0 crosses must be present")
    orientations = set()
    for pair, obs in anchors.items():
        require(isinstance(pair, str) and pair.count("/") == 1
                and isinstance(obs,dict) and obs.get("date") == day
                and obs.get("trade_execution_price") is False
                and obs.get("layer") ==
                "ECB_DAILY_REFERENCE_NOT_EXECUTABLE_SPOT"
                and type(obs.get("rate")) in (float,int)
                and math.isfinite(obs["rate"]) and obs["rate"] > 0,
                "wrong ECB cross definition")
        a,b = pair.split("/")
        require(a in G8 and b in G8 and a!=b, "non G8 cross")
        orientations.add(frozenset((a,b)))
    require(orientations == EXPECTED_UNORDERED_G8,
            "28 official crosses do not cover G8")
    # 28 G8 crosses share exactly seven independent ECB/EUR quote levels.
    # A signed but altered FX leg must NOT become a legitimate observation:
    # reconstruct every cross from the same seven reference legs.
    def fx(a, b):
        direct = anchors.get(a + "/" + b)
        if direct is not None:
            return direct["rate"]
        inverse = anchors.get(b + "/" + a)
        require(inverse is not None, "unavailable reverse FX reference leg")
        return 1.0 / inverse["rate"]

    eur_legs = {ccy: (1.0 if ccy == "EUR" else fx("EUR", ccy))
                for ccy in G8}
    for pair, observed_cross in anchors.items():
        a, b = pair.split("/")
        expected = eur_legs[b] / eur_legs[a]
        require(math.isclose(observed_cross["rate"], expected,
                             rel_tol=1e-9, abs_tol=1e-10),
                "signed ECB cross violates EUR seven-leg triangle: " + pair)
    observed = row.get("economic_observations")
    require(isinstance(observed,dict) and set(observed)==set(G8),
            "all 8 economic research dimensions required")
    missing=0
    zero_mad=0
    for currency, c in observed.items():
        require(isinstance(c,dict)
                and isinstance(c.get("growth"),dict)
                and isinstance(c.get("inflation"),dict)
                and isinstance(c.get("labour"),dict),
                currency+" growth/inflation/labour observation missing")
        for pillar in PILLARS:
            f = c[pillar]
            require(f.get("currency")==currency
                    and f.get("pillar")==pillar
                    and f.get("eligible_for_macro_score") is False
                    and f.get("eligible_for_historical_backtest") is False
                    and f.get("source_observation_is_current_revised_history_not_historic_pit") is True,
                    currency+"."+pillar+" feature input promoted unexpectedly")
            z = f.get("research_robust_z")
            require(z is None or (type(z) in (float,int)
                    and math.isfinite(z) and -3 <= z <= 3),
                    "not a finite clipped research z or explicit missing")
            if z is None:
                missing+=1
            if f.get("status") == "NO_Z_ZERO_ROBUST_DISPERSION":
                zero_mad+=1
                require(z is None
                        and isinstance(c.get("zero_mad_context",{}).get(pillar),dict)
                        and c["zero_mad_context"][pillar].get("numeric_replacement_z") is None,
                        "zero-MAD source was silently numerically imputed")
            else:
                require(pillar not in c.get("zero_mad_context",{}),
                        "unexpected zero-MAD annotation on normal feature")
        require(c.get("FX_signal") is None and c.get("trade_entry") is None
                and c.get("growth",{}).get("growth_score") is None,
                "market signal/model score is prohibited")
    require(row.get("strict_robust_z_missing_count")==missing and
            row.get("zero_mad_source_count")==zero_mad and
            row.get("numeric_z_imputation_count")==0,
            "economic source-quality counts altered")
    hashes=row.get("source_file_sha256")
    require(isinstance(hashes,dict) and set(hashes)==set(SOURCE_PATHS)
            and all(isinstance(x,str) and len(x)==64
                    and all(ch in "0123456789abcdef" for ch in x)
                    for x in hashes.values()), "source provenance incomplete")
    # Snapshot identity is not arbitrary metadata: bind it to the certified
    # T0 input, contemporaneous macro source, ordinal observation receipt.
    ordinal_sha = row.get("ordinal_evidence_sha256")
    require(isinstance(ordinal_sha,str) and len(ordinal_sha)==64
            and all(ch in "0123456789abcdef" for ch in ordinal_sha),
            "missing signed ordinal evidence fingerprint")
    expected_id=sha({
        "schema":SCHEMA,"date":day,
        "official_ecb_source_sha":hashes["ecb"],
        "macro_series_source_sha":hashes["macro_series"],
        "ordinal_evidence_sha":ordinal_sha,
    })
    require(row.get("snapshot_id")==expected_id,
            "snapshot identity does not bind immutable source inputs")
    return day


def make(cutoff, now, *, fx, pair_setup, core, observed, ordinal, hashes):
    utc, day = valid_capture_clock(cutoff, now)
    admission=assess(utc,fx,pair_setup,core)
    require(admission["status"]=="ADMITTED_PROSPECTIVE_BASELINE_OBSERVATION",
            "official same-day ECB and canonical 28-pair admission failed "+
            repr(admission["checks"]))
    require(observed.get("checked_as_of") == day
            and observed.get("status") ==
                "OBSERVED_G8_RESEARCH_FEATURES_NOT_CERTIFIED_MACRO_MODEL"
            and observed.get("safe_to_publish_new_D") is False
            and observed.get("safe_to_use_for_forward") is False,
            "revised-history research bridge not contemporaneously stamped")
    require(ordinal.get("schema") ==
            "GMFQ_V2_ZERO_MAD_ORDINAL_QUALITY_RESEARCH_V1"
            and ordinal.get("policy_id")==ORDINAL_POLICY
            and ordinal.get("as_of_observed_economic_bridge")==day
            and ordinal.get("strict_numeric_z_imputation_count")==0
            and ordinal.get("can_write_forward_v2_journal") is False
            and ordinal.get("can_feed_preregistered_H1") is False,
            "unapproved ordinal z-score fallback/protocol drift")
    require(isinstance(hashes,dict) and set(hashes)==set(SOURCE_PATHS),
            "unexpected source input hashes")
    day_fx=source_map(fx).get(utc.astimezone(ROME).date())
    require(day_fx is not None and fx.get("last_as_of")==day,
            "official ECB T0 date unavailable")
    anchors={}
    for key,p in pair_setup["pairs"].items():
        pair=p["canonical_pair"]
        a,b=pair.split("/")
        val=cross(day_fx,a,b)
        require(type(val) is float and math.isfinite(val) and val>0,
                "missing official ECB reference "+pair)
        require(pair not in anchors,"duplicate canonical cross")
        anchors[pair]={
            "rate":val,"date":day,
            "source":SOURCE_PATHS["ecb"],
            "layer":"ECB_DAILY_REFERENCE_NOT_EXECUTABLE_SPOT",
            "trade_execution_price":False,
        }
    inputs=observed.get("inflation_labour",{})
    descriptor=ordinal.get("zero_mad_components",{})
    require(set(inputs)=={f"{c}.{p}" for c in G8 for p in PILLARS}
            and isinstance(descriptor,dict)
            and ordinal.get("zero_mad_component_count")==len(descriptor)
            and set(descriptor)=={
                k for k,v in inputs.items()
                if v.get("status")=="NO_Z_ZERO_ROBUST_DISPERSION"},
            "economic feature completeness or zero-MAD source mask mismatch")
    growth=observed.get("growth_quarterly_gdp_web")
    first_growth=observed.get("growth_quarterly_gdp_initial_web_research_features")
    require(isinstance(growth,dict) and set(growth)==set(G8)
            and isinstance(first_growth,dict) and set(first_growth)==set(G8),
            "eight source GDP observation slots missing")
    countries={}
    for ccy in G8:
        country={
            "growth":copy.deepcopy(growth[ccy]),
            "growth_first_web_research":copy.deepcopy(first_growth[ccy]),
            "inflation":copy.deepcopy(inputs[f"{ccy}.inflation"]),
            "labour":copy.deepcopy(inputs[f"{ccy}.labour"]),
            "zero_mad_context":{
                p:copy.deepcopy(descriptor[f"{ccy}.{p}"])
                for p in PILLARS if f"{ccy}.{p}" in descriptor},
            "FX_signal":None,
            "trade_entry":None,
        }
        countries[ccy]=country
    missed=sum(c[p]["research_robust_z"] is None
               for c in countries.values() for p in PILLARS)
    body={
        "schema":SCHEMA,
        "status":"FROZEN_PARTIAL_ECONOMIC_RESEARCH_NO_MODEL_SCORE",
        "capture_at_utc":utc.isoformat().replace("+00:00","Z"),
        "local_date_rome":day,
        "economic_checked_as_of":day,
        "official_ecb_t0_date":day,
        "observed_t0_ref":anchors,
        "old_core_as_of":core["asOf"],
        "economic_observations":countries,
        "strict_robust_z_missing_count":missed,
        "zero_mad_source_count":len(descriptor),
        "numeric_z_imputation_count":0,
        "ordinal_protocol":ORDINAL_POLICY,
        "observed_research_receipt_sha256":observed["input_fingerprint_sha256"],
        "ordinal_evidence_sha256":ordinal["evidence_fingerprint_sha256"],
        "source_file_sha256":hashes,
        "source_history_is_revised_not_publication_vintage":True,
        "economic_period_not_release_timestamp":True,
        "historical_issuer_PIT_certified":False,
        "old_core_recalculated":False,
        "V2_numeric_model_computed":False,
        "V2_FX_signal_computed":False,
        "future_outcomes_observed_at_capture":False,
        "eligible_for_beta_forward_trading":False,
        "can_feed_preregistered_H1":False,
        "can_merge_with_original_V2_cohort_as_identical_model":False,
    }
    body["snapshot_id"]=sha({
        "schema":SCHEMA,"date":day,"official_ecb_source_sha":hashes["ecb"],
        "macro_series_source_sha":hashes["macro_series"],
        "ordinal_evidence_sha":body["ordinal_evidence_sha256"],
    })
    body["snapshot_sha256"]=sha(body)
    validate_snapshot(body)
    return body


def read_journal(path=JOURNAL):
    if not path.is_file():
        return []
    return [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines()
            if s.strip()]


def verify_journal(entries):
    require(isinstance(entries,list), "journal must contain complete JSONL rows")
    seen=set()
    for row in entries:
        day=validate_snapshot(row)
        require(day not in seen, "duplicate immutable capture date")
        seen.add(day)
    return seen


def append(snapshot, *, path=JOURNAL, dry_run=False):
    seen=verify_journal(read_journal(path))
    day=validate_snapshot(snapshot)
    if day in seen:
        return "EXISTING_QUALITY_AWARE_DATE_FROZEN_NO_OVERWRITE"
    if dry_run:
        return "VALID_QUALITY_AWARE_PROSPECTIVE_DRY_RUN_NO_WRITE"
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("ab") as f:
        f.write(canonical(snapshot))
    return "QUALITY_AWARE_PROSPECTIVE_SNAPSHOT_APPEND_OK"


def attempt(*, cutoff, now, dry_run=False, path=JOURNAL):
    utc,day=valid_capture_clock(cutoff,now)
    if day in verify_journal(read_journal(path)):
        return {"status":"EXISTING_QUALITY_AWARE_DATE_FROZEN_NO_OVERWRITE",
                "local_date":day,"appended":0}
    read=lambda key:json.loads((ROOT/SOURCE_PATHS[key]).read_text(encoding="utf-8"))
    fx,pair,core=(read(k) for k in ("ecb","pair_setup","legacy_core"))
    admission=assess(utc,fx,pair,core)
    if admission["status"]!="ADMITTED_PROSPECTIVE_BASELINE_OBSERVATION":
        return {"status":"BLOCKED_NO_OFFICIAL_SAME_DAY_ECB_T0",
                "local_date":day,"admission_checks":admission["checks"],"appended":0}
    hashes_before={key:file_sha(path) for key,path in SOURCE_PATHS.items()}
    observed=economic_run(as_of=day)
    from validation.macro.v2_zero_mad_ordinal_quality_v1 import (
        SOURCE as SERIES, REGISTRY
    )
    ordinal=ordinal_build(
        observed,json.loads(SERIES.read_text(encoding="utf-8")),
        json.loads(REGISTRY.read_text(encoding="utf-8")),
        today=date.fromisoformat(day))
    hashes_after={key:file_sha(path) for key,path in SOURCE_PATHS.items()}
    require(hashes_before==hashes_after,
            "source changed during research freeze")
    require(sha(fx)==sha(read("ecb")) and
            sha(pair)==sha(read("pair_setup")) and
            sha(core)==sha(read("legacy_core")),
            "market/source input mutated during freeze")
    snapshot=make(utc,now,fx=fx,pair_setup=pair,core=core,
                  observed=observed,ordinal=ordinal,hashes=hashes_after)
    status=append(snapshot,path=path,dry_run=dry_run)
    return {"status":status,"local_date":day,
            "snapshot_id":snapshot["snapshot_id"],
            "snapshot_sha256":snapshot["snapshot_sha256"],
            "economic_dimension_slots":24,
            "robust_z_missing_count":snapshot["strict_robust_z_missing_count"],
            "zero_mad_source_count":snapshot["zero_mad_source_count"],
            "new_FX_signals":0,"forward_H1_eligible":False,
            "appended":int(status=="QUALITY_AWARE_PROSPECTIVE_SNAPSHOT_APPEND_OK")}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--dry-run",action="store_true")
    args=parser.parse_args()
    # The real process samples now; no --as-of/cutoff override/backfill.
    now=datetime.now(timezone.utc)
    result=attempt(cutoff=now,now=now,dry_run=args.dry_run)
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
