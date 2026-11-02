#!/usr/bin/env python3
"""Stage independently recovered same-date SNB 2Y/10Y history; never publish."""
import argparse, json, hashlib
from pathlib import Path
from datetime import date
from build_chf_nzd_official_rates_staging_v1 import validate_existing
from rates.recover_chf_snb_paired_history_v1 import SCHEMA as SOURCE_SCHEMA

def stage(rates, evidence, today):
    old=rates["CHF"]
    assert validate_existing(rates,"CHF")==date(2026,9,30)
    assert evidence["schema"]==SOURCE_SCHEMA
    assert evidence["status"]=="PAIRED_OFFICIAL_HISTORY_READY_FOR_REVIEW"
    assert evidence["writes_operational_rates"] is False
    assert evidence["eligible_for_automatic_promotion"] is False
    assert evidence["historic_gap_backfilled_from_observations_not_interpolated"] is True
    assert evidence["unmatched_or_weekend_dates_fabricated"] is False
    assert evidence["base_date"]==old["date"]
    assert len(evidence["source_response_sha256"])==64
    assert evidence["new_paired_rows"]>=1
    rows=evidence["paired_source_rows"]
    assert len(rows)==evidence["matched_paired_rows"]==evidence["new_paired_rows"]+1
    assert rows[0]["date"]==old["date"]
    assert rows[0]["2Y"]==old["2Y"] and rows[0]["10Y"]==old["10Y"]
    assert rows[-1]["date"]==evidence["last_common_date"]
    assert rows[-1]["2Y"]==evidence["last_common_2Y"]
    assert rows[-1]["10Y"]==evidence["last_common_10Y"]
    assert 0<=(today-date.fromisoformat(rows[-1]["date"])).days<=5
    assert len(rows)>2 and rows==sorted(rows,key=lambda x:x["date"])
    assert len(set(x["date"] for x in rows))==len(rows)
    for row in rows:
        d=date.fromisoformat(row["date"])
        assert d.weekday()<5 and d<=today
        assert all(isinstance(row[t],(int,float)) and not isinstance(row[t],bool)
                   and -5<=row[t]<=25 for t in ("2Y","10Y"))
        assert abs((row["10Y"]-row["2Y"])*100-row["curve_bp"])<0.002
    import copy
    updated=copy.deepcopy(rates)
    c=updated["CHF"]
    for row in rows[1:]:
        for tenor,h in (("2Y","history2"),("10Y","history10")):
            assert row["date"]>c[h]["dates"][-1]
            c[h]["dates"].append(row["date"])
            c[h]["values"].append(row[tenor])
    end=rows[-1]
    c.update(date=end["date"],**{"2Y":end["2Y"],"10Y":end["10Y"]},
        curve_bp=round((end["10Y"]-end["2Y"])*100,1),
        quality="FULL_CURRENT_OFFICIAL_STAGING_REVIEW_REQUIRED",
        freshness_status="OFFICIAL_STAGING_REVIEW_REQUIRED",
        freshness_note="Same-source historical backfill; human review required; never automatically published.")
    for item in c["tenors"]:
        if item["tenor"] in ("2Y","10Y"):
            item["date"]=end["date"]
            item["value"]=end[item["tenor"]]
    assert all(updated[k]==rates[k] for k in rates if k!="CHF")
    return updated,{"status":"CHF_PAIRED_HISTORY_STAGING_REVIEW_REQUIRED",
        "official_rows_backfilled":len(rows)-1,"last_date":end["date"],
        "source_sha256":evidence["source_response_sha256"],
        "writes_live_data":False,"eligible_for_automatic_promotion":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--rates",default="live_data/sections/NATIVE_RATES_DATA.json")
    p.add_argument("--evidence",required=True)
    p.add_argument("--output",required=True)
    args=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    target=Path(args.output).resolve()
    assert not target.is_relative_to(root)
    base=json.loads(Path(args.rates).read_text())
    evidence=json.loads(Path(args.evidence).read_text())
    result,receipt=stage(base,evidence,date.today())
    target.write_text(json.dumps({"candidate":result,"receipt":receipt},ensure_ascii=False)+"\n")
    print(json.dumps(receipt))
if __name__=="__main__":
    main()
