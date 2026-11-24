#!/usr/bin/env python3
"""Read-only exact dated ASX bank-bill contract reference, never official OIS."""
import argparse
import json
import hashlib
from datetime import date
from pathlib import Path
from collect_nzd_asx_directional_proxy_v1 import (
    _fetch, _parse_bb_rows, _report_url, _business_days_before,
)
from nzd_asx_scenario_sensitivity_v2 import check_asx

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"live_data/sections/NZD_CB_PRICING_DIRECTIONAL_PROXY.json"

def probe(feed, fetch=_fetch):
    end=date.fromisoformat(feed["as_of"])
    check_asx(feed,end)
    target=_business_days_before(end,20)
    url=_report_url(target)
    result={"schema":"GMFQ_NZD_ASX_EXACT_20_WEEKDAY_REFERENCE_V1",
            "as_of":end.isoformat(),"reference_date":target.isoformat(),
            "reference_url":url,"current_source_url":feed["source_url"],
            "status":"REFERENCE_UNAVAILABLE","horizons":{},
            "official_ois_created":False,"fx_engine_effect":"NONE"}
    try:
        raw=fetch(url)
        rows=_parse_bb_rows(raw)
    except (OSError,RuntimeError,ValueError) as exc:
        result["reason"]=type(exc).__name__
        return result
    result["decoded_source_sha256"]=hashlib.sha256(raw.encode("utf-8")).hexdigest()
    for h,current in feed["horizons"].items():
        matches=[r for r in rows if r["expiry_label"]==current["expiry_label"]
                 and r["expiration"].isoformat()==current["expiration"]]
        if len(matches)!=1:
            continue
        ref=matches[0]
        result["horizons"][h]={"contract":current["expiry_label"],
            "expiration":current["expiration"],
            "reference_price":ref["settlement_price"],
            "reference_implied_pct":ref["implied_bank_bill_rate"],
            "current_price":current["settlement_price"],
            "current_implied_pct":current["implied_bank_bill_rate"],
            "change_bp":round((current["implied_bank_bill_rate"]-ref["implied_bank_bill_rate"])*100,2),
            "basis":"EXACT_LISTED_ASX_BANK_BILL_CONTRACT_NOT_OIS"}
    result["status"]="REFERENCE_PARSED" if result["horizons"] else "NO_MATCHED_LISTED_CONTRACT"
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,default=SOURCE)
    p.add_argument("--output",type=Path,default=Path("/tmp/nzd-asx-20d-reference.json"))
    a=p.parse_args()
    if not a.output.resolve().is_relative_to(Path("/tmp")):
        raise ValueError("Probe output must remain temporary")
    result=probe(json.loads(a.source.read_text()))
    a.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,sort_keys=True))

if __name__=="__main__":main()
