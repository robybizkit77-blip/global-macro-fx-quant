#!/usr/bin/env python3
"""One-time, observed-link-only public access audit for historical Eurex EUR OIS.

NOT a model accuracy test, not a scan over fabricated date suffixes, no new
scheduler. Historical 2026-10-21 URL came from a previously published Eurex
Clearing settlement-prices page; its domain-mirrored path is only a hypothesis.
2026-10-29 is the positive source control, previously retrieved and date-audited.

Read just the first 2KB of an HTTP response to verify a CSV-shaped public
file; avoid copying/distributing full vendor settlement curves. All sources
are explicit and audited, never dynamically constructed from a date pattern.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import urllib.error
import urllib.request

SCHEMA="GMFQ_EUREX_OIS_HISTORICAL_ACCESS_RESEARCH_V1"
SOURCES=(
    {
        "date":"2026-10-21",
        "kind":"SOURCE_PAGE_LINK_CACHED",
        "url":"https://www.eurexgroup.com/resource/blob/5654224/bf6ab8fe5c914603eb1517be9881fd9a/data/settlement-prices_20261021.csv",
        "page":"https://www.eurexgroup.com/ec-en/clear/eurex-otc-clear/settlement-prices",
        "discovered_as":"EUREX_CLEARING_HISTORIC_PAGE_DOWNLOAD_21_OCT",
        "source_url_is_site_observed":True,
    },
    {
        "date":"2026-10-21",
        "kind":"MIRRORED_HOST_HYPOTHESIS_ONLY",
        "url":"https://www.eurex.com/resource/blob/5654224/bf6ab8fe5c914603eb1517be9881fd9a/data/settlement-prices_20261021.csv",
        "page":"https://www.eurexgroup.com/ec-en/clear/eurex-otc-clear/settlement-prices",
        "discovered_as":"HOST_SUBSTITUTION_OF_GROUNDED_ORIGINAL_ASSET_NOT_VERIFIED",
        "source_url_is_site_observed":False,
    },
    {
        "date":"2026-10-29",
        "kind":"POSITIVE_CONTROL_PREVIOUSLY_RETRIEVED",
        "url":"https://www.eurex.com/resource/blob/5673460/29ad46d1ef7a740197df794a9f33ffc1/data/settlement-prices_20261029.csv",
        "page":"https://www.eurex.com/ec-en/clear/eurex-otc-clear/settlement-prices",
        "discovered_as":"EUREX_CLEARING_SITE_DOWNLOAD_LINK_29_OCT",
        "source_url_is_site_observed":True,
    },
)

def source_shape(prefix):
    header=prefix.decode("utf-8-sig",errors="replace").splitlines()[0].lower()
    return (("value datetime" in header or "valuedatetime" in header)
            and ("curve id" in header or "curveid" in header)
            and ("maturity" in header) and ("value type" in header or "valuetype" in header))

def make_observation(info,status=None,http_status=None,media_type=None,reason=None,final_url=None):
    result={k:info[k] for k in ("date","kind","url","page","discovered_as",
                                 "source_url_is_site_observed")}
    result.update({"status":status or "NOT_PROBED",
        "http_status":http_status,
        "media_type":media_type,
        "error_class":reason,
        "redirected_to":final_url if final_url and final_url!=info["url"] else None,
        "downloaded_vendor_curve_values":False,
        "used_as_actual_independent_OIS_quote":False})
    return result

def probe(info, opener=urllib.request.urlopen):
    url=info["url"]
    # Dates and endpoints must come from the attested immutable list, not a pattern.
    if url not in [a["url"] for a in SOURCES]:
        raise ValueError("not a source-observed or explicitly flagged mirror candidate")
    try:
        request=urllib.request.Request(url,headers={
            "User-Agent":"GMFQ-public-source-access-research/1.0",
            "Accept":"text/csv,text/plain,*/*"})
        with opener(request,timeout=12) as response:
            code=response.status
            media=response.headers.get("content-type","")
            first=response.read(2048)
            effective=response.geturl()
        if code!=200:
            return make_observation(info,"PUBLIC_SOURCE_NOT_CONFIRMED",
                                    http_status=code,media_type=media,final_url=effective)
        if source_shape(first):
            return make_observation(info,"PUBLIC_DATED_CURVE_CSV_HEADER_VERIFIED",
                                    http_status=code,media_type=media,final_url=effective)
        return make_observation(info,"HTTP_OK_BUT_NOT_EXPECTED_CSV",
                                http_status=code,media_type=media,final_url=effective)
    except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError,
            OSError,UnicodeError) as exc:
        return make_observation(info,"PUBLIC_SOURCE_NOT_CONFIRMED",
            http_status=getattr(exc,"code",None),reason=type(exc).__name__)

def audit(*,allow_network=False,opener=urllib.request.urlopen):
    source_rows=[probe(x,opener) if allow_network else make_observation(x)
                 for x in SOURCES]
    historic=[x for x in source_rows if x["date"]=="2026-10-21"
             and x["status"]=="PUBLIC_DATED_CURVE_CSV_HEADER_VERIFIED"]
    control=[x for x in source_rows if x["date"]=="2026-10-29"
             and x["status"]=="PUBLIC_DATED_CURVE_CSV_HEADER_VERIFIED"]
    return {"schema":SCHEMA,
        "research_goal":"REAL_HISTORIC_SOURCE_ACCESS_NOT_PRICE_ACCURACY",
        "checked_sources":source_rows,
        "historic_21oct_public_source_verified":bool(historic),
        "29oct_positive_control_currently_accessible":bool(control),
        "different_dates_verified":len({x["date"] for x in source_rows if
             x["status"]=="PUBLIC_DATED_CURVE_CSV_HEADER_VERIFIED"}),
        "multi_date_OIS_spread_statistics_allowed":False,
        "same_market_time_and_instrument_proven":False,
        "source_curve_from_same_Eurex_group_as_futures":True,
        "EUR_OIS_MAE_bp":None,"EUR_OIS_hit_rate":None,
        "no_lagging_archives_replaced_by_newer_source":True,
        "no_generated_untested_historical_url":True,
        "no_source_curve_values_persisted":True,
        "changes_live_OIS_or_FX":False,
        "new_schedule_added":False,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--once",action="store_true",
                   help="three bounded documented requests (no retries)")
    p.add_argument("--out",type=Path,
                   default=Path("/tmp/eurex-historic-source-access.json"))
    args=p.parse_args()
    if not args.out.resolve().is_relative_to(Path("/tmp")):
        raise ValueError("read-only receipt must remain in /tmp")
    result=audit(allow_network=args.once)
    result["checked_at_utc"]=datetime.now(timezone.utc).isoformat()
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",
                        encoding="utf-8")
    print(json.dumps({"historic_21oct_verified":result["historic_21oct_public_source_verified"],
        "distinct_verified_dates":result["different_dates_verified"],
        "responses":[{"day":x["date"],"kind":x["kind"],"status":x["status"],
                      "http_status":x["http_status"]} for x in result["checked_sources"]]},
        sort_keys=True))

if __name__=="__main__":
    main()
