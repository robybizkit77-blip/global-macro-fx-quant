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

if __name__ == "__main__":
    output = Path(sys.argv[1]).resolve()
    assert output.is_relative_to(Path("/tmp"))
    research, native = json.loads(RESEARCH.read_text()), json.loads(NATIVE.read_text())
    out = build(research, native, date.fromisoformat(research["publication_date"]))
    output.write_text(json.dumps(out, ensure_ascii=False, separators=(",",":"))+"\n")
    print("NZD_POSTROLL_RUNTIME_CANDIDATE",json.dumps({"date":out["NZD"]["date"],"changed_currencies":["NZD"],"prior_history_retained":True,"production_write":False}))
