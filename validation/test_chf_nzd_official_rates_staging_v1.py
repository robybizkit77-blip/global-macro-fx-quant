#!/usr/bin/env python3
"""Offline adversarial QA for CHF/NZD official-staging only, using synthetic fixtures."""
import copy
import datetime as dt
import hashlib
import io
import json
from pathlib import Path

from openpyxl import Workbook

from build_chf_nzd_official_rates_staging_v1 import (
    BASE, BASIS, RBNZ_B2, make_candidate, parse_rbnz_b2_xlsx, validate_existing
)
from probe_chf_nzd_rates_sources_v1 import parse_snb_csv


def must_reject(action, marker):
    try:
        action()
    except (ValueError, AssertionError) as e:
        print("PASS: REJECT", marker, str(e)[:100])
        return
    raise AssertionError("Expected fail-closed rejection: " + marker)


def main():
    rates = json.loads(BASE.read_text(encoding="utf8"))
    today = dt.date(2026,10,18)
    before = json.dumps(rates, sort_keys=True)

    assert validate_existing(rates,"CHF") == dt.date(2026,9,30)
    # Actual production NZD rates can legitimately advance beyond the
    # original Oct 5 fixture. Never assert a frozen date against live data.
    assert validate_existing(rates,"NZD") == dt.date.fromisoformat(rates["NZD"]["date"])
    snb = ("Date;D0;D1;Value\n"
           "2026-10-16;CHF;2J;0.32\n"
           "2026-10-16;CHF;10J;0.64\n").encode()
    official = parse_snb_csv(snb)
    o = {"date":official["as_of"], "2Y":official["2Y"],"10Y":official["10Y"]}
    candidate, receipt=make_candidate(rates,"CHF",o,
        source_sha256=hashlib.sha256(snb).hexdigest(),
        mode="SYNTHETIC_SNB_FIXTURE_QA",today=today)
    assert receipt["status"]=="GATED_CANDIDATE_REVIEW_REQUIRED"
    assert receipt["review"]=="REQUIRED"
    assert receipt["eligible_for_automatic_promotion"] is False
    assert candidate["CHF"]["date"]=="2026-10-16"
    assert candidate["CHF"]["history2"]["dates"][-1]=="2026-10-16"
    assert candidate["CHF"]["history10"]["dates"][-1]=="2026-10-16"
    assert candidate["CHF"]["quality"]=="FULL_CURRENT_OFFICIAL_STAGING_REVIEW_REQUIRED"
    assert set(k for k in rates if candidate[k]!=rates[k])=={"CHF"}
    assert candidate["CHF"]["tenors"][0]["value"] == 0.32
    assert candidate["CHF"]["tenors"][2]["value"] == 0.64
    print("PASS: CHF official same-day 2Y/10Y staged (NOT promoted)")

    # Stale same-date official source must remain NO_UPDATE, not a new candidate.
    duplicate = {"date":rates["CHF"]["date"],"2Y":rates["CHF"]["2Y"],
                 "10Y":rates["CHF"]["10Y"]}
    unchanged, rr=make_candidate(rates,"CHF",duplicate,
        source_sha256="deadbeef",mode="SYNTHETIC_SNB_FIXTURE_QA",today=today)
    assert unchanged is None and rr["status"]=="NO_NEW_OFFICIAL_PAIR"
    assert rr["source_age_days"]>5
    print("PASS: old but identical official source causes no changes")

    must_reject(lambda:make_candidate(rates,"CHF",{"date":"2026-10-16","2Y":0.32,"10Y":float("nan")},
        source_sha256="fixture",mode="TEST",today=today),"NaN/missing tenor")
    must_reject(lambda:make_candidate(rates,"CHF",{"date":"2026-10-16","2Y":0.32,"10Y":19},
        source_sha256="fixture",mode="TEST",today=today),"implausible value")
    must_reject(lambda:make_candidate(rates,"CHF",{"date":"2026-10-16","2Y":4.99,"10Y":0.64},
        source_sha256="fixture",mode="TEST",today=today),"outlier cross-time jump")
    must_reject(lambda:make_candidate(rates,"CHF",{"date":"2026-10-25","2Y":0.32,"10Y":0.64},
        source_sha256="fixture",mode="TEST",today=today),"future publication")
    must_reject(lambda:make_candidate(rates,"CHF",{"date":"2026-10-06","2Y":0.32,"10Y":0.64},
        source_sha256="fixture",mode="TEST",today=today),"stale new observation")
    must_reject(lambda:make_candidate(rates,"CHF",{"date":"2026-09-30","2Y":0.77,"10Y":0.586},
        source_sha256="fixture",mode="TEST",today=today),"same date conflict")
    must_reject(lambda:make_candidate(rates,"CHF",{"date":"2026-09-29","2Y":0.32,"10Y":0.64},
        source_sha256="fixture",mode="TEST",today=today),"backdated source")

    corrupt=copy.deepcopy(rates)
    corrupt["CHF"]["history2"]["values"][-1]=9.9
    must_reject(lambda:make_candidate(corrupt,"CHF",o,
        source_sha256="fixture",mode="TEST",today=today),"history tail tampering")

    # Build a deterministic synthetic NEXT-session observation from the real
    # certified NZD baseline. The staging gate, not a frozen source vintage,
    # is under test; no production series or actual yields are modified.
    nzd_previous = validate_existing(rates, "NZD")
    nzd_candidate_date = nzd_previous + dt.timedelta(days=1)
    while nzd_candidate_date.weekday() >= 5:
        nzd_candidate_date += dt.timedelta(days=1)
    nzd_test_now = nzd_candidate_date + dt.timedelta(days=1)
    nzd_y2 = round(float(rates["NZD"]["2Y"]) - 0.01, 4)
    nzd_y10 = round(float(rates["NZD"]["10Y"]) + 0.01, 4)
    wb=Workbook()
    ws=wb.active
    ws.title="Daily close"
    ws.append(["Secondary market government bond closing yields (%pa)",None,None])
    ws.append(["Date","2 year","10 year"])
    ws.append([nzd_previous, rates["NZD"]["2Y"], rates["NZD"]["10Y"]])
    ws.append([nzd_candidate_date, nzd_y2, nzd_y10])
    out=io.BytesIO()
    wb.save(out); raw=out.getvalue()
    mapping={"sheet":"Daily close","header_row":2,"group_row":1,
             "date_col":1,"y2_col":2,"y10_col":3,
             "source_url":RBNZ_B2,"source_sha256":hashlib.sha256(raw).hexdigest()}
    parsed=parse_rbnz_b2_xlsx(raw,mapping)
    assert parsed["date"] == nzd_candidate_date.isoformat()
    assert parsed["2Y"] == nzd_y2 and parsed["10Y"] == nzd_y10
    nzdcandidate,nzdreceipt=make_candidate(rates,"NZD",parsed,
        source_sha256=mapping["source_sha256"],
        mode="SYNTHETIC_RBNZ_FIXTURE_QA",today=nzd_test_now)
    assert nzdcandidate["NZD"]["date"] == nzd_candidate_date.isoformat()
    assert set(k for k in rates if nzdcandidate[k]!=rates[k])=={"NZD"}
    assert nzdreceipt["eligible_for_automatic_promotion"] is False
    assert "government benchmark close" in nzdreceipt["official_basis"]
    print("PASS: reviewed-shape B2 government CLOSE Excel fixture staged (NOT promoted)")

    broken=copy.deepcopy(mapping);broken["source_sha256"]="0"*64
    must_reject(lambda:parse_rbnz_b2_xlsx(raw,broken),"document SHA mismatch")
    broken=copy.deepcopy(mapping);broken["y2_col"]=3
    must_reject(lambda:parse_rbnz_b2_xlsx(raw,broken),"duplicate tenor column")
    broken=copy.deepcopy(mapping);broken["group_row"]=2
    must_reject(lambda:parse_rbnz_b2_xlsx(raw,broken),"government basis header group invalid")
    broken=copy.deepcopy(mapping);broken["source_url"]="https://other.example/b2.xlsx"
    must_reject(lambda:parse_rbnz_b2_xlsx(raw,broken),"untrusted source URL")
    # Bank-bill headings MUST NOT be mistaken for government bond close.
    wb2=Workbook();s=wb2.active;s.title="Daily close"
    s.append(["Bank bill yields (%pa)",None,None])
    s.append(["Date","2 year","10 year"])
    s.append([dt.date(2026,10,16),3.5,3.6])
    buffer=io.BytesIO();wb2.save(buffer);other=buffer.getvalue()
    broken=copy.deepcopy(mapping);broken["source_sha256"]=hashlib.sha256(other).hexdigest()
    must_reject(lambda:parse_rbnz_b2_xlsx(other,broken),"bank bills rejected")

    assert json.dumps(rates,sort_keys=True)==before, "QA changed canonical Rates JSON"
    print("CHF_NZD_GATED_OFFICIAL_RATES_STAGING_QA_GREEN")


if __name__=="__main__":
    main()
