#!/usr/bin/env python3
"""Single-run public download availability probe. Not OIS data ingestion.

CME's own site links the historical CSV. This read makes at most ONE official
URL request (no mirrors, cookies, spoofing, retries, automation schedules or
redistribution of rate values). Receipt contains headers/shape and source URL,
NEVER the downloaded historical content or a fabricated same-window comparison.
"""
import argparse
import csv
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
import urllib.error
import urllib.request

URL="https://www.cmegroup.com/reports/cme-term-estr-historical-data.csv"

def inspect(*,allow_network=False):
    result={"schema":"GMFQ_CME_TERM_ESTR_PUBLIC_CSV_AVAILABILITY_V1",
        "url":URL,"downloaded_data_stored":False,
        "independent_OIS_same_forward_period_benchmark":False,
        "as_observed_CME_term_estr_is_spot_start_not_Eurex_FST3_future_start":True,
        "potentially_usable_for_future_bootstrapped_spot_curve_comparison":True,
        "eligible_to_persist_original_rate_values":False,
        "eligible_to_modify_live_OIS_or_FX":False,
        "status":"NOT_PROBED"}
    if not allow_network:return result
    try:
        request=urllib.request.Request(URL,headers={
            "User-Agent":"GMFQ-research-availability-audit/1.0"})
        with urllib.request.urlopen(request,timeout=12) as response:
            media=response.headers.get("content-type","")
            contents=response.read(1800000)
            status=response.status
        # Do not publish rates, only CSV shape and column labels.
        text=contents.decode("utf-8-sig")
        head=list(csv.reader(StringIO(text)))
        if status==200 and "html" not in media.lower() and len(head)>1:
            result.update({"status":"PUBLIC_CSV_READABLE_NOT_BENCHMARK_MATCHED",
                "http_status":status,"declared_mime":media,
                "row_count_bounded":len(head),"header_fields":head[0][:20],
                "body_parse_limited":len(contents)>=1800000})
        else:
            result.update({"status":"PUBLIC_CSV_NOT_VALIDATED_AS_CSV",
                "http_status":status,"declared_mime":media})
    except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,
            OSError,UnicodeError,csv.Error) as e:
        result.update({"status":"PUBLIC_CSV_ACCESS_NOT_CONFIRMED",
          "error_class":type(e).__name__,
          "http_status":e.code if isinstance(e,urllib.error.HTTPError) else None})
    return result

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--once",action="store_true",help="single public official URL request")
    ap.add_argument("--out",type=Path,default=Path("/tmp/cme-term-estr-source-access.json"))
    a=ap.parse_args()
    if not a.out.resolve().is_relative_to(Path("/tmp")):
        raise ValueError("only research receipt in /tmp")
    result=inspect(allow_network=a.once)
    result["checked_at_utc"]=datetime.now(timezone.utc).isoformat()
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({"status":result["status"],"http_status":result.get("http_status"),
        "readable_rows":result.get("row_count_bounded"),
        "not_same_future_period":result["as_observed_CME_term_estr_is_spot_start_not_Eurex_FST3_future_start"]},
        sort_keys=True))
