#!/usr/bin/env python3
"""Same-benchmark NZD observational continuation; no Core/PIT/FX admission."""
import copy
import json
import sys
from datetime import date
from pathlib import Path

if __package__:
    from .check_nzd_postroll_release_readiness_v1 import RESEARCH, NATIVE, isolated_candidate, require, build as preflight
    from .verify_weekly_rate_change_contract_v1 import validate as weekly_validate
else:
    from check_nzd_postroll_release_readiness_v1 import RESEARCH, NATIVE, isolated_candidate, require, build as preflight
    from verify_weekly_rate_change_contract_v1 import validate as weekly_validate

ROOT = Path(__file__).resolve().parents[2]
ANCHOR = ROOT / "validation/fixtures/rbnz_b2_postroll_2026-11-26_reviewed_release.json"
REGISTRY = ROOT / "validation/RATES_SOURCE_ADAPTERS_V1_2026-10-05.json"
POLICY = {"status":"SAME_BENCHMARK_OBSERVATIONAL_ONLY",
          "benchmark_roll_date":"2026-10-30","benchmark_2Y":"April 2029","benchmark_10Y":"April 2037",
          "same_edition_html_xlsx_required":True,"append_only":True,"cross_roll_allowed":False,
          "core_pit_fx_backtests_allowed":False}

def prefix(old, new):
    require(len(new) >= len(old) and new[:len(old)] == old, "previous paired history changed or removed")

def make_row(anchor, receipt, asof):
    native = {"NZD":anchor["canonical_row"]}
    c = isolated_candidate(receipt, native, asof)
    prefix(anchor["reconciled_source"]["observations"], receipt["observations"])
    row = copy.deepcopy(native["NZD"])
    row.update(date=c["date"], source=c["source"]+" · HTML/XLSX reconciled",
        freshness_status="OFFICIAL_POSTROLL_RECONCILED_RECURRING_OBSERVATION",
        freshness_note="Same-benchmark official B2 HTML/XLSX append-only observation; no first-release PIT, Core or FX signal admission.",
        source_publication_date=c["publication_date"], source_sha256=c["source_sha256"], curve_bp=c["curve_bp"],
        reconciled_release_receipt=copy.deepcopy(receipt))
    ref = c["weekly_reference"]
    for suffix, tenor in (("2","2Y"),("10","10Y")):
        key = "history"+suffix
        row[key] = {"label":row[key]["label"], **c[key]}
        row[tenor] = c[tenor]
        delta = c["weekly_change_bp"][tenor]
        row["chg"+suffix+"_bp"] = delta
        row["weekly"+suffix+"_validation"] = {"start_date":ref["date"],"start_value":ref[tenor],
            "end_date":c["date"],"end_value":c[tenor],"change_bp":delta,"source":row["source"],
            "note":"Same post-roll benchmark; observed reference at/before seven-calendar-day cutoff."}
    a,b = row["chg2_bp"],row["chg10_bp"]
    row["curve_state"] = (("Bull parallel" if a<0 else "Bear parallel" if a>0 else "Stabile") if a==b
        else ("Bull steepening" if a<b else "Bull flattening") if a<0 and b<0
        else ("Bear steepening" if b>a else "Bear flattening") if a>0 and b>0 else "Movimento misto")
    row["tenors"] = [{"tenor":k,"value":c[k],"date":c["date"]} for k in ("2Y","10Y")]
    return row

def verify_row(row, anchor, latest, policy):
    require(policy == POLICY, "recurring observational contract changed")
    stored = row["reconciled_release_receipt"]
    # Stored accepted edition remains verifiable after newer research is published.
    require(stored["publication_date"] <= latest["publication_date"], "source edition rollback")
    preflight(latest, {"NZD":anchor["canonical_row"]}, date.fromisoformat(latest["publication_date"]))
    prefix(stored["observations"], latest["observations"])
    if stored["publication_date"] == latest["publication_date"]:
        require(stored == latest, "same-edition receipt disagreement")
    require(row == make_row(anchor, stored, date.fromisoformat(stored["publication_date"])),
            "canonical continuation differs from reconciled source")
    return row

def advance(native, latest, anchor, policy, asof):
    require(policy == POLICY, "recurring observational contract changed")
    old = native["NZD"]
    if old["date"] == anchor["canonical_row"]["date"]:
        require(old == anchor["canonical_row"], "approved anchor differs")
        prior = anchor["reconciled_source"]
    else:
        verify_row(old, anchor, latest, policy)
        prior = old["reconciled_release_receipt"]
    preflight(latest, native, asof)
    require(latest["publication_date"] >= prior["publication_date"], "source edition rollback")
    prefix(prior["observations"], latest["observations"])
    if latest["publication_date"] == prior["publication_date"]:
        require(latest == prior, "same-edition receipt changed")
    if latest["last_observation_date"] == old["date"]:
        return None
    require(latest["last_observation_date"] > old["date"], "source observation rollback")
    out = copy.deepcopy(native)
    out["NZD"] = make_row(anchor, latest, asof)
    require([k for k in out if out[k] != native[k]] == ["NZD"], "scope changed")
    require(out["NZD"]["legacy_pre_roll"] == old["legacy_pre_roll"], "legacy history changed")
    weekly_validate(out)
    return out

if __name__ == "__main__":
    output = Path(sys.argv[1]).resolve()
    require(output.is_relative_to(Path("/tmp")), "output must be temporary")
    native, latest, anchor, registry = [json.loads(p.read_text()) for p in (NATIVE, RESEARCH, ANCHOR, REGISTRY)]
    out = advance(native, latest, anchor, registry["currencies"]["NZD"]["postroll_recurring_observations"], date.today())
    if out is None:
        print("NZD_RECURRING_NO_NEW_OBSERVATION")
    else:
        output.write_text(json.dumps(out, ensure_ascii=False,separators=(",",":"))+"\n")
        print("NZD_RECURRING_CANDIDATE",out["NZD"]["date"])
