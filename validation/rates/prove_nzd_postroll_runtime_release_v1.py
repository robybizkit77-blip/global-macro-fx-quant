#!/usr/bin/env python3
"""Dry-run the reconciled NZD benchmark in the canonical runtime; never publish."""
import copy
import json
import sys
from datetime import date
from pathlib import Path

from check_nzd_postroll_release_readiness_v1 import RESEARCH, NATIVE, isolated_candidate
from verify_weekly_rate_change_contract_v1 import validate

def build(research, native, asof):
    c = isolated_candidate(research, native, asof)
    out = copy.deepcopy(native)
    old = native["NZD"]
    row = out["NZD"]
    assert old["date"] < c["benchmark_roll_date"], "initial roll release only"
    row["legacy_pre_roll"] = {"date": old["date"], "source": old["source"],
        "history2": copy.deepcopy(old["history2"]), "history10": copy.deepcopy(old["history10"]),
        "tenors": copy.deepcopy(old["tenors"]), "cross_roll_change_allowed": False}
    row["date"] = c["date"]
    row["source"] = c["source"] + " · HTML/XLSX reconciled"
    row["quality"] = "FULL_CURRENT_OFFICIAL_POSTROLL_RECONCILED"
    row["freshness_status"] = "OFFICIAL_POSTROLL_RECONCILED_RELEASE_CANDIDATE"
    row["freshness_note"] = "Isolated release review; B2 same-benchmark government yields. Legacy segment retained separately. No first-release PIT or continuity certification."
    row["benchmark_roll_date"] = c["benchmark_roll_date"]
    row["benchmark_2Y"] = c["benchmark_2Y"]
    row["benchmark_10Y"] = c["benchmark_10Y"]
    row["cross_roll_change_allowed"] = False
    row["first_release_pit_certified"] = False
    row["source_publication_date"] = c["publication_date"]
    row["source_sha256"] = c["source_sha256"]
    row["curve_bp"] = c["curve_bp"]
    ref = c["weekly_reference"]
    for suffix, tenor in (("2", "2Y"), ("10", "10Y")):
        k = "history" + suffix
        row[k] = {"label": old[k]["label"], **c[k]}
        row[tenor] = c[tenor]
        delta = c["weekly_change_bp"][tenor]
        row["chg" + suffix + "_bp"] = delta
        row["weekly" + suffix + "_validation"] = {
            "start_date": ref["date"], "start_value": ref[tenor],
            "end_date": c["date"], "end_value": c[tenor], "change_bp": delta,
            "source": row["source"], "note": "Same post-roll benchmark; observed reference at/before seven-calendar-day cutoff."}
    a,b = row["chg2_bp"], row["chg10_bp"]
    if a == b:
        row["curve_state"] = "Bull parallel" if a < 0 else "Bear parallel" if a > 0 else "Stabile"
    elif a < 0 and b < 0:
        row["curve_state"] = "Bull steepening" if a < b else "Bull flattening"
    elif a > 0 and b > 0:
        row["curve_state"] = "Bear steepening" if b > a else "Bear flattening"
    else:
        row["curve_state"] = "Movimento misto"
    row["tenors"] = [{"tenor": k, "value": c[k], "date": c["date"]} for k in ("2Y","10Y")]
    assert [k for k in out if out[k] != native[k]] == ["NZD"]
    assert row["legacy_pre_roll"]["history2"] == old["history2"]
    assert row["legacy_pre_roll"]["history10"] == old["history10"]
    assert row["history2"]["dates"][0] == row["history10"]["dates"][0] == c["benchmark_roll_date"]
    validate(out) # no automatic-lane exemption; this is a separate release review
    return out

def reviewed_release(research, native, asof):
    """One approved edition only; no recurring automatic Core promotion."""
    if native["NZD"]["date"] >= "2026-10-30":
        return None
    assert native["NZD"]["date"] == "2026-10-16", "reviewed base changed"
    assert research["publication_date"] == "2026-11-27"
    assert research["last_observation_date"] == "2026-11-26"
    assert research["html_sha256"] == "78682ece82c944eb4353ddc1d49f5821bff438d640470f74b2a20fcd8d782b48"
    assert research["xlsx_sha256"] == "011739d660510e1d7d0612d0a9fda7b4b0e27f8dc97b2ac88c59ec9eb907b2fa"
    out = build(research, native, asof)
    row = out["NZD"]
    assert (row["2Y"], row["10Y"]) == (3.79, 4.69)
    row["freshness_status"] = "OFFICIAL_POSTROLL_RECONCILED_ONE_TIME_RELEASE"
    row["freshness_note"] = "RBNZ B2 official HTML and XLSX reconciled. One-time reviewed publication; no recurring automatic canonical promotion or first-release PIT certification. Legacy benchmark retained separately."
    return out

if __name__ == "__main__":
    output = Path(sys.argv[1]).resolve()
    assert output.is_relative_to(Path("/tmp"))
    research, native = json.loads(RESEARCH.read_text()), json.loads(NATIVE.read_text())
    if "--reviewed-release" in sys.argv:
        out = reviewed_release(research, native, date.today())
        if out is None:
            print("NZD_POSTROLL_REVIEWED_RELEASE_ALREADY_ADMITTED")
            sys.exit(0)
    else:
        out = build(research, native, date.fromisoformat(research["publication_date"]))
    output.write_text(json.dumps(out, ensure_ascii=False, separators=(",",":"))+"\n")
    print("NZD_POSTROLL_RUNTIME_CANDIDATE",json.dumps({"date":out["NZD"]["date"],"changed_currencies":["NZD"],"prior_history_retained":True,"production_write":False}))
