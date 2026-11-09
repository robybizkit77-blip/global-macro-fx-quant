#!/usr/bin/env python3
"""Daily firms/households source intake -- RESEARCH STAGING, not live Macro.

Run within the existing Macro Persistent Daily job. It collects two BEA-based
FRED monthly series (PCEC96, DSPIC96) as revised-volume level candidates,
and separately checks the BEA issuer release clock plus the latest known
Stats NZ electronic-card publication. It NEVER writes MACRO_SERIES, the 28-pair
Core, operational dashboards, or point-in-time archives.

Missing HTTP / changed HTML produce explicit WITHHELD receipts, not fabricated
observations or a successful live-data-published claim.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
from hashlib import sha256
from io import StringIO
import json
import math
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[2]
OUT=Path("/tmp/macro-persistent/household-firm-publisher-intake-v1.json")
LIVE=ROOT/"live_data/sections/MACRO_SERIES.json"
SCHEMA="GMFQ_HOUSEHOLD_FIRMS_ISSUER_INTAKE_RESEARCH_V1"
BEA_CURRENT="https://www.bea.gov/news/current-releases"
NZ_ECT="https://www.stats.govt.nz/information-releases/electronic-card-transactions-september-2026/"
FRED_IDS={
    "PCEC96":"US_PCEC96_history_value",
    "DSPIC96":"US_DSPIC96_history_DSPIC96",
}
MAX_BYTES=1_500_000


def fetch(url):
    req=Request(url,headers={"User-Agent":"GMFQ-Research-Snapshot/1.0 (public economic research)",
                             "Accept":"text/html,text/csv;q=0.9"})
    with urlopen(req,timeout=14) as res:
        final=res.geturl()
        # Allow www canonicalization, but no third-party host nor HTTP downgrade.
        host=final.split("/")[2].lower()
        expected=url.split("/")[2].lower()
        if not final.startswith("https://") or host.removeprefix("www.")!=expected.removeprefix("www."):
            raise ValueError("source left its permitted HTTPS publisher host")
        buf=res.read(MAX_BYTES+1)
    if not buf or len(buf)>MAX_BYTES:
        raise ValueError("empty or oversized issuer document")
    return buf,final


def fred_monthly_csv(raw, ident, now):
    """Parse a revised monthly LEVEL, never convert it into rate or PIT."""
    text=raw.decode("utf-8-sig")
    reader=csv.DictReader(StringIO(text))
    if reader.fieldnames not in ([ "observation_date",ident],["DATE",ident]):
        raise ValueError("FRED CSV header or series identity changed")
    ds, values=[],[]
    for r in reader:
        key=reader.fieldnames[0]
        stamp=r[key]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",stamp) or stamp[-2:]!="01":
            raise ValueError("FRED observation not a first-of-month ISO date")
        val=r[ident]
        if val in ("","."):
            continue
        n=float(val)
        if not math.isfinite(n) or n<=0:
            raise ValueError("FRED value cannot be negative/zero/non-finite")
        dt=date.fromisoformat(stamp)
        if dt>now:
            raise ValueError("FRED source contains future observation")
        ds.append(stamp);values.append(n)
    if len(ds)<24 or ds!=sorted(set(ds)):
        raise ValueError("FRED series too short, duplicate or unordered")
    for a,b in zip(ds[-13:-1],ds[-12:]):
        a,b=date.fromisoformat(a),date.fromisoformat(b)
        if 12*(b.year-a.year)+(b.month-a.month)!=1:
            raise ValueError("last year FRED months are not contiguous")
    return {"series_id":ident,"last_date":ds[-1],"last_value":values[-1],
            "previous_date":ds[-2],"previous_value":values[-2],
            "observations":len(ds),"source_lineage":"FRED_FEDERAL_RESERVE_MIRROR_OF_BEA_REVISED_NOT_ISSUER_PIT",
            "metric_kind":"MONTHLY_SA_CHAINED_DOLLAR_REAL_LEVEL_NOT_MOM_PCT"}


def compare_to_existing(candidate, row):
    if row["id"]!=FRED_IDS[candidate["series_id"]] or len(row["values"])!=len(row["dates"]):
        raise ValueError("canonical source identity/pairing changed")
    if "Chained" not in str(row.get("unit","")) and candidate["series_id"]=="PCEC96":
        raise ValueError("PCEC96 canonical real-price unit mismatch")
    current=str(row["last_date"])[:7]
    new=candidate["last_date"][:7]
    if new<current:
        status="SOURCE_BEHIND_CANONICAL"
    elif new>current:
        status="NEWER_REVISED_SOURCE_CANDIDATE_NOT_APPLIED"
    elif math.isclose(candidate["last_value"],float(row["last_value"]),
                      rel_tol=0,abs_tol=1e-8):
        status="SAME_PERIOD_MATCH"
    else:
        status="SAME_PERIOD_REVISION_CANDIDATE_NOT_APPLIED"
    return {**candidate,"canonical_last_period":current,
            "canonical_last_value":row["last_value"],"status":status,
            "written_to_live_series":False,"eligible_for_PIT_backtest":False}


def official_bea_release(raw, url):
    soup=BeautifulSoup(raw,"html.parser")
    matches=[]
    for a in soup.find_all("a",href=True):
        label=" ".join(a.get_text(" ",strip=True).split())
        m=re.search(r"Personal Income and Outlays,\s*(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})",label,re.I)
        if not m:continue
        href=a["href"]
        if not re.search(r"/news/20\d\d/personal-income-and-outlays-[a-z]+-20\d\d",href):
            continue
        from urllib.parse import urljoin, urlparse
        dest=urljoin(url,href)
        u=urlparse(dest)
        if u.scheme!="https" or u.hostname not in ("www.bea.gov","bea.gov"):
            raise ValueError("BEA release URL not on BEA HTTPS")
        matches.append({"month":m.group(1).lower(),"year":int(m.group(2)),"url":dest})
    if not matches:
        raise ValueError("current BEA Personal Income and Outlays release not identified")
    months=["january","february","march","april","may","june","july","august","september","october","november","december"]
    best=max(matches,key=lambda x:(x["year"],months.index(x["month"])))
    return {"status":"ISSUER_RELEASE_DISCOVERED_NOT_ACTUAL_PARSED",
            "release_reference_period":f"{best['year']}-{months.index(best['month'])+1:02}",
            "release_url":best["url"],"publisher":"BEA",
            "actual_values_validated_here":False}


def statsnz_known_release(raw, url):
    soup=BeautifulSoup(raw,"html.parser")
    t=" ".join(soup.get_text(" ",strip=True).split())
    if not re.search(r"Electronic card transactions:\s*September 2026",t,re.I):
        raise ValueError("Stats NZ issuer release identity changed")
    # On the Stats NZ production HTML the publication date can be rendered
    # outside the readable body. The title is checked live; date comes from
    # the earlier independently verified manual publisher snapshot unless
    # this run can also see it. Never label that as a new release-day PIT.
    date_seen=bool(re.search(r"16\\s+October\\s+2026|2026-10-16",t,re.I))
    if not re.search(r"Values.*not adjusted for price changes",t,re.I):
        raise ValueError("Stats NZ nominal nature not verified")
    # Do not equate this with retail *volume* or a new retail survey quarter.
    return {"status":("KNOWN_STATIC_RELEASE_DATE_AND_TITLE_CONFIRMED" if date_seen
                      else "KNOWN_STATIC_RELEASE_TITLE_ONLY_DATE_FROM_PRIOR_RESEARCH"),
            "issuer_url":url,"reference_period":"2026-09",
            "release_date":"2026-10-16",
            "release_date_verified_in_current_html":date_seen,
            "release_date_otherwise_from":"G8_US_NZ_PUBLISHED_RELEASE_CONTEXT_2026-11-09",
            "metric_type":"NOMINAL_ELECTRONIC_CARD_TRANSACTION_VALUE",
            "not_real_retail_volumes":True,"latest_release_certified":False}


def capture(*,now=None,fetcher=fetch,series=None):
    at=now or datetime.now(timezone.utc)
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("capture clock must be timezone-aware")
    today=at.date()
    if series is None:
        series=json.loads(LIVE.read_text(encoding="utf-8"))
    output={"schema":SCHEMA,"observed_at_utc":at.astimezone(timezone.utc).isoformat(),
            "research_only":True,"source_series_modified":False,
            "website_modified":False,"fx_signal_generated":False,
            "new_scheduler_created":False,"actual_publisher_release_PIT":False,
            "sources":{}}
    def attempt(name,url,parser):
        try:
            raw,final=fetcher(url)
            # Defense-in-depth even for an injected retrieval implementation.
            from urllib.parse import urlparse
            supplied,returned=urlparse(url),urlparse(final)
            if (returned.scheme!="https" or
                returned.hostname.removeprefix("www.")!=supplied.hostname.removeprefix("www.")):
                raise ValueError("publisher host changed under fetch")
            value=parser(raw,final)
            output["sources"][name]={"status":"VERIFIED_RESEARCH_ONLY",
                "issuer_url":final,"sha256":sha256(raw).hexdigest(),
                "value":value}
        except (HTTPError,URLError,OSError,TimeoutError,UnicodeError,
                ValueError,KeyError,TypeError) as e:
            output["sources"][name]={"status":"WITHHELD_FETCH_OR_PARSER_UNAVAILABLE",
                                     "attempted_url":url,
                                     "reason_type":type(e).__name__,
                                     "reason_detail":str(e)[:180]}
    for ident,target in FRED_IDS.items():
        url="https://fred.stlouisfed.org/graph/fredgraph.csv?id="+ident
        hits=[r for r in series["USD"] if r.get("id")==target]
        if len(hits)!=1:
            raise ValueError("canonical US series identity not unique: "+target)
        def parse(raw,final,ident=ident,row=hits[0]):
            return compare_to_existing(fred_monthly_csv(raw,ident,today),row)
        attempt("FRED_BEAMIRROR_"+ident,url,parse)
    attempt("BEA_CURRENT_RELEASE_DISCOVERY",BEA_CURRENT,official_bea_release)
    attempt("STATS_NZ_ECT_KNOWN_SOURCE",NZ_ECT,statsnz_known_release)
    output["usable_new_revised_monthly_candidates"]=[
        k for k,v in output["sources"].items()
        if v["status"]=="VERIFIED_RESEARCH_ONLY" and
        v["value"].get("status")=="NEWER_REVISED_SOURCE_CANDIDATE_NOT_APPLIED"
    ]
    output["source_count_verified"]=sum(
        x["status"]=="VERIFIED_RESEARCH_ONLY" for x in output["sources"].values())
    output["no_claim_of_current_nzd_retail_volume"]=True
    return output


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,default=OUT)
    args=p.parse_args()
    if not args.out.resolve().is_relative_to(Path("/tmp")):
        raise SystemExit("research-only output outside /tmp rejected")
    result=capture()
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":"RESEARCH_INTAKE_RECEIPT_ONLY",
        "sources_verified":result["source_count_verified"],
        "sources_total":len(result["sources"]),
        "candidates":result["usable_new_revised_monthly_candidates"],
        "source_series_modified":False,"fx_signal_generated":False},sort_keys=True))


if __name__=="__main__":
    main()
