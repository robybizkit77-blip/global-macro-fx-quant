#!/usr/bin/env python3
"""Fetch exactly two dated official ONS first-release bulletins, fail-closed.

No current revised MGSX API values accepted as PIT input. This program
connects June-August and May-July 2026 official bulletins to END-MONTH
canonical storage, and emits content hashes and individual source identities.
It does NOT write canonical Macro, D.json, or FX pair files.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

from validation.materialize_gbp_labour_strict_pit_v1 import (
    one, digest, SEMANTIC,
)
from validation.macro.gbp_ons_temporal_guard_v1 import ROOT, CONTRACT

EXPECTED = {
    "2026-07": ("2026-09-15", 4.9, "May 2026 to July 2026"),
    "2026-08": ("2026-10-20", 4.7, "June 2026 to August 2026"),
}


def require(ok, detail):
    if not ok:
        raise ValueError("GBP_ONS_FIRST_RELEASE_PROOF_FAILED: "+detail)


def verify_materialization(items, source_contract):
    require(len(items)==2, "need two official release documents exactly")
    byperiod={}
    for row in items:
        key=row.get("reference_month")
        require(key in EXPECTED and key not in byperiod,
                "duplicate/unexpected end-of-rolling-period month")
        expected_date, expected_value, _ = EXPECTED[key]
        require(row.get("release_date")==expected_date and
                row.get("headline_unemployment_rate_pct")==expected_value,
                f"{key}: first-release value/date mismatch")
        require(row.get("pit_status")=="STRICT_FIRST_RELEASE" and
                row.get("source_route") in (
                    "ONS_UK_LABOUR_MARKET_BULLETIN",
                    "ONS_EMPLOYMENT_IN_UK_COMPANION_BULLETIN"
                ), f"{key}: non-first-release/unsupported retrieval")
        url=row.get("source_url")
        require(type(url) is str and
                url.startswith("https://www.ons.gov.uk/"),
                f"{key}: release must be hosted by ONS")
        sha=row.get("page_sha256")
        require(type(sha) is str and len(sha)==64 and
                all(x in "0123456789abcdef" for x in sha),
                f"{key}: source page missing SHA256")
        byperiod[key]=row
    require(set(byperiod)==set(EXPECTED),"missing source release")
    require(byperiod["2026-07"]["page_sha256"]!=byperiod["2026-08"]["page_sha256"],
            "source page reused across vintages")
    anchors=source_contract.get("official_periods")
    require(isinstance(anchors,list) and len(anchors)==3,
            "canonical UK end-month map missing")
    for period in ("2026-07","2026-08"):
        row=byperiod[period]
        refs=[x for x in anchors if x.get("canonical_end_month")==period]
        require(len(refs)==1 and
                refs[0]["release_date"]==row["release_date"] and
                refs[0]["unemployment_pct"]==row["headline_unemployment_rate_pct"],
                "source registry official value/period mismatch")
        require(row["rolling_period"] == refs[0]["source_label"].replace(
            "May to July", "May 2026 to July").replace(
            "June to August", "June 2026 to August") or
            # Source label may use the abbreviated single-year prose.
            (period=="2026-07" and "May" in row["rolling_period"] and "July" in row["rolling_period"]) or
            (period=="2026-08" and "June" in row["rolling_period"] and "August" in row["rolling_period"]),
            "source rolling-window identity drift")
    return {
        "schema":"GMFQ_GBP_ONS_TWO_RELEASE_FIRST_VINTAGE_EVIDENCE_V1",
        "status":"TWO_FIRST_RELEASE_PAGES_VERIFIED",
        "as_of":date.today().isoformat(),
        "first_release_rows": [byperiod[k] for k in ("2026-07","2026-08")],
        "semantic_rowset_sha256":digest(
            [byperiod[k] for k in ("2026-07","2026-08")], SEMANTIC),
        "official_pages_independently_hashed":2,
        "all_history_vintage_certified":False,
        "scope":"ONLY_JULY_AUGUST_2026_UK_MGSX",
        "live_runtime_modified":False,
        "macro_score_rebase_authorized":False,
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    contract=json.loads((ROOT/CONTRACT).read_text(encoding="utf-8"))
    # Existing first-vintage materializer uses end-of-window months, not the
    # centered ONS MGSX API representation. July and August -> Sep/Oct bulletins.
    rows=[one(2026,7),one(2026,8)]
    receipt=verify_materialization(rows, contract)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":receipt["status"],
        "months":[x["reference_month"] for x in rows],
        "values":[x["headline_unemployment_rate_pct"] for x in rows],
        "source_sha256s":[x["page_sha256"] for x in rows],
        "all_history_vintage_certified":False},ensure_ascii=False))


if __name__=="__main__":
    main()
