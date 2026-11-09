#!/usr/bin/env python3
"""Promote two verified BEA/FRED revised US real LEVEL histories as one vintage.

This is a PREPARATION gate. It emits a full replacement MACRO_SERIES under
/tmp; the caller uses canonical direct-section + manifest + runtime checks.
It never mutates live data itself. No first-release/PIT or trading claims.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime,timezone,date
from hashlib import sha256
import json
import math
from pathlib import Path

from validation.macro import reconcile_us_real_households_countrybook_v2 as research
from validation.macro.collect_us_nz_household_firm_sources_v1 import FRED_IDS,LIVE

SCHEMA="GMFQ_US_REAL_HOUSEHOLD_REVISION_PROMOTION_PREP_V1"
DEST=Path("/tmp/macro-persistent/MACRO_SERIES_US_REVISED_PREP.json")
REPORT=Path("/tmp/macro-persistent/us-households-revised-promotion-preflight-v1.json")
EXPECTED_UNIT=research.SAAR_UNIT
EXPECTED_IDS=frozenset(FRED_IDS.values())


def gate(ok,reason):
    if not ok:
        raise ValueError("US_REVISED_PROMOTION_REJECTED: "+reason)


def prepare(note, current, *, as_of=None):
    at=as_of or datetime.now(timezone.utc)
    gate(isinstance(at,datetime) and at.tzinfo is not None and
         at.utcoffset() is not None,"aware observation clock required")
    gate(note.get("schema")==research.SCHEMA and
         note.get("status")==
         "TWO_REVISED_REAL_SERIES_RECONCILED_WITH_BEA_ISSUER_RESEARCH_ONLY" and
         note.get("series_pit_certified") is False and
         note.get("replaces_live_macro_series") is False and
         note.get("affects_28_pair_core") is False and
         note.get("fx_signal") is None,
         "research issuer gate or no-trade contract invalid")
    gate(note["bea_issuer"].get("issuer_release_first_seen_PIT") is False and
         note["bea_issuer"]["url"].startswith(
             "https://www.bea.gov/news/") and
         len(note["bea_issuer"]["issuer_html_sha256"])==64,
         "BEA source issuer not attested")
    period=note["latest_release_month"]
    gate(period==note["bea_issuer"]["period"] and
         period+"-01"<=at.date().isoformat() and
         "revised_series" in note and
         set(note["revised_series"])==set(FRED_IDS),
         "issuer month or FRED input mismatch")
    gate(isinstance(current,dict) and set(current)==
         {"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"},
         "G8 canonical currency contract mismatch")
    out=copy.deepcopy(current)
    rows=out["USD"]
    before={r["id"]:r for r in current["USD"]}
    gate(len(before)==len(current["USD"]) and EXPECTED_IDS<=set(before),
         "missing or duplicate US macro series identity")
    original_sha=sha256(json.dumps(current,sort_keys=True).encode()).hexdigest()
    changes=[]
    for fred,ident in FRED_IDS.items():
        r=next(x for x in rows if x["id"]==ident)
        old=before[ident]
        x=note["revised_series"][fred]
        gate(x["id"]==ident and x["source_fred_id"]==fred and
             x["source_fred_url"]=="https://fred.stlouisfed.org/series/"+fred and
             x["source_revised_vintage_not_point_in_time"] is True and
             x["expected_unit"]==EXPECTED_UNIT and
             len(x["source_csv_sha256"])==64 and
             x["latest_month"]==period,
             fred+" source definition/vintage mismatch")
        gate(old["source_file"]=="US_"+fred+"_history.csv",
             fred+" original import identity drift")
        gate(old.get("unit") in ("",EXPECTED_UNIT),
             fred+" source unit changed to incompatible definition")
        gate(old.get("frequency") in ("","M"),
             fred+" source frequency cannot be rewritten")
        obs=x["complete_revised_history"]
        ds=[z["date"] for z in obs];vs=[z["value"] for z in obs]
        gate(len(ds)>=len(old["dates"]) and
             len(ds)==len(vs)==x["historical_revised_months"] and
             len(ds)==len(set(ds)) and ds==sorted(ds) and
             ds[-1]==period+"-01" and ds[0]==old["dates"][0],
             fred+" complete reconciled historical window invalid")
        gate(all(research._months(a,b)==1 for a,b in zip(ds,ds[1:])) and
             all(type(z) in (float,int) and math.isfinite(z) and z>0
                 for z in vs),
             fred+" gap, future or bad numeric revised history")
        gate(all(d in set(ds) for d in old["dates"]),
             fred+" revised history does not cover canonical past")
        gate(math.isclose(vs[-1],x["latest_level"],rel_tol=0,abs_tol=1e-7)
             and x["original_last_month"]==old["last_date"] and
             math.isclose(x["old_last_level"],old["last_value"],rel_tol=0,
                          abs_tol=1e-6),
             fred+" research notes not tied to actual canonical base")
        # The BEA issuer independently checked the current monthly rate.
        gate(abs(x["latest_mom_pct_from_revised_levels"]-
                 x["latest_mom_pct_BEA_published"])<=0.051,
             fred+" levels no longer agree with BEA latest monthly rate")
        newer=ds[-1]>=old["last_date"]
        gate(newer,fred+" cannot regress to an older vintage")
        # Idempotence: do not rewrite provenance or create a new commit when
        # the fully revised vintage has not changed since yesterday.
        old_prov=old.get("current_vintage_provenance",{})
        same_data=(
            old.get("dates")==ds and old.get("values")==vs
            and old.get("unit")==EXPECTED_UNIT and old.get("frequency")=="M"
            and old_prov.get("source_csv_sha256")==x["source_csv_sha256"]
            and old_prov.get("source_html_sha256")==
                note["bea_issuer"]["issuer_html_sha256"]
            and old_prov.get("source_series_first_release_PIT_certified") is False
        )
        if same_data:
            changes.append({"id":ident,"before_last_date":old["last_date"],
                            "after_last_date":ds[-1],
                            "old_unit":old.get("unit",""),
                            "new_unit":EXPECTED_UNIT,
                            "fully_replaced_observations":len(ds),
                            "revised_overlap_count":0,"changed":False})
            continue
        r["dates"]=ds
        r["values"]=vs
        r["last_date"]=ds[-1]
        r["last_value"]=vs[-1]
        # The original DSPIC96 row did not declare unit or frequency.
        # These are documented in FRED series/BEA NIPA A067RX. Source is
        # publisher's metadata, not inferred from the level magnitude.
        r["unit"]=EXPECTED_UNIT
        r["frequency"]="M"
        r["current_vintage_provenance"]={
            "status":"BEA_REVISED_HISTORY_VIA_FRED_CURRENT_NOT_PIT",
            "source_series_id":fred,
            "issuer":"US_BEA",
            "data_mirror":"FRED_ST_LOUIS_FED",
            "issuer_release_url":note["bea_issuer"]["url"],
            "issuer_release_reference_month":period,
            "source_csv_sha256":x["source_csv_sha256"],
            "source_html_sha256":note["bea_issuer"]["issuer_html_sha256"],
            "runner_first_seen_utc":note["source_observed_at_utc"],
            "research_verified_utc":note["research_processed_at_utc"],
            "unit_source_url":"https://fred.stlouisfed.org/series/"+fred,
            "unit_verified_from_publisher_metadata":True,
            "source_series_first_release_PIT_certified":False,
            "historical_levels_may_be_revised_again":True,
            "source_history_old_commit_retained_in_git":True,
        }
        changed=(r!=old)
        changes.append({"id":ident,"before_last_date":old["last_date"],
                        "after_last_date":ds[-1],
                        "old_unit":old.get("unit",""),
                        "new_unit":EXPECTED_UNIT,
                        "fully_replaced_observations":len(ds),
                        "revised_overlap_count":x["overlap_revised_observation_count"],
                        "changed":changed})
    gate(len(changes)==2 and all(x["after_last_date"]==period+"-01"
                                 for x in changes),"partial revised promotion")
    gate(all(out[c]==current[c] for c in out if c!="USD"),
         "non-US currency mutated")
    gate(all(out["USD"][i]==current["USD"][i]
             for i in range(len(rows))
             if rows[i]["id"] not in EXPECTED_IDS),
         "non-household US series mutated")
    # No PIT label, core signal or new model input is inferred by the migration.
    changed=out!=current
    return out,{
        "schema":SCHEMA,
        "status":"REVISED_US_HOUSEHOLDS_READY_FOR_CANONICAL_APPLY"
                 if changed else "NO_CHANGE_VERIFIED_REVISED_VINTAGE",
        "as_of_utc":at.astimezone(timezone.utc).isoformat(),
        "base_macro_series_sha256":original_sha,
        "reference_month":period,
        "series":changes,
        "g8_unchanged_other_than_two_us_household_series":True,
        "full_revised_history_not_spliced":True,
        "first_release_pit_eligible":False,
        "signals_or_28_pairs_recalculated":False,
        "requires_atomic_payload_manifest_update":changed,
        "committed_to_main":False,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--research-note",type=Path,
        default=Path("/tmp/macro-persistent/us-households-revised-countrybook-v2.json"))
    p.add_argument("--series",type=Path,default=LIVE)
    p.add_argument("--candidate-out",type=Path,default=DEST)
    p.add_argument("--report-out",type=Path,default=REPORT)
    args=p.parse_args()
    gate(all(q.resolve().is_relative_to(Path("/tmp"))
             for q in (args.research_note,args.candidate_out,args.report_out)),
         "all research input/output must live under /tmp")
    note=json.loads(args.research_note.read_text(encoding="utf-8"))
    current=json.loads(args.series.read_text(encoding="utf-8"))
    out,report=prepare(note,current)
    args.candidate_out.parent.mkdir(parents=True,exist_ok=True)
    args.candidate_out.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",
                                  encoding="utf-8")
    args.report_out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",
                               encoding="utf-8")
    print(json.dumps({"status":report["status"],"changed":report
        ["requires_atomic_payload_manifest_update"],
        "reference_month":report["reference_month"],
        "PIT":False,"signals_touched":False},sort_keys=True))


if __name__=="__main__":
    main()
