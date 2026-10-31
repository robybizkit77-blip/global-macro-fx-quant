#!/usr/bin/env python3
"""Reconcile *independently fetched* RBNZ B2 XLSX government benchmark close.

Read-only. The public HTML table is one source and the XLSX is a second
publication representation of the SAME provider, not an independent institution.
Don't confuse the '2-10s' swap spread with 10Y-2Y government yield; require
the government-bond header group, unique date, 2Y, 10Y columns and matching
2018+ workbook values. No unreviewed Excel guessed index enters production.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from datetime import datetime, date, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parents[2]
HTML=ROOT / "live_data/sections/NZD_B2_GOVT_LATEST_WEB_RESEARCH.json"
RATES=ROOT / "live_data/sections/NATIVE_RATES_DATA.json"
URL="https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily-close.xlsx"
ALTERNATE="https://rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily-close.xlsx"
SCHEMA="GMFQ_NZD_RBNZ_B2_HTML_VS_INDEPENDENT_XLSX_RECONCILIATION_V1"


def require(ok, msg):
    if not ok:
        raise ValueError("RBNZ_B2_XLSX_RECONCILIATION_WITHHELD: "+msg)


def clean(s):
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def asdate(s):
    if isinstance(s,datetime):
        return s.date().isoformat()
    if isinstance(s,date):
        return s.isoformat()
    if isinstance(s,str):
        try:
            return date.fromisoformat(s).isoformat()
        except ValueError:
            return None
    return None


def locate_government_pair(wb):
    """Find a single unambiguous government-bond 2Y+10Y column pair.

    Inspects workbook group headings and exact tenors, never infers 2Y from
    position in the swap/bank bill columns. An ambiguous/moved format is a
    manual review event, not an invitation to choose the closest cell.
    """
    candidates=[]
    for ws in wb:
        cap=min(ws.max_column,100)
        headings=list(ws.iter_rows(min_row=1,max_row=min(ws.max_row,40),
                                   max_col=cap,values_only=True))
        for i,row in enumerate(headings):
            labels=[clean(v) for v in row]
            date_cols=[j for j,v in enumerate(labels) if v in ("date","date of observation")]
            if len(date_cols)!=1:
                continue
            y2=[j for j,v in enumerate(labels) if v in ("2 year","2 years","2-year")]
            y10=[j for j,v in enumerate(labels) if v in ("10 year","10 years","10-year")]
            # Within a merged heading group the government yield group label
            # begins in a column on an earlier heading row. Its *next*
            # nonempty group heading is the right-hand limit.
            for j in range(max(0,i-7),i):
                heading=[clean(v) for v in headings[j]]
                groups=[k for k,v in enumerate(heading) if
                        "secondary market government bond" in v and
                        ("closing" in v or "close" in v)]
                for start in groups:
                    limit=next((k for k in range(start+1,len(heading))
                                if heading[k] and not heading[k].isdigit()
                                and len(heading[k])>=4),len(heading))
                    c2=[v for v in y2 if start<=v<limit]
                    c10=[v for v in y10 if start<=v<limit]
                    if len(c2)==1 and len(c10)==1 and len({date_cols[0],c2[0],c10[0]})==3:
                        candidates.append((ws.title,i+1,date_cols[0]+1,c2[0]+1,c10[0]+1))
    candidates=list(dict.fromkeys(candidates))
    require(len(candidates)==1, "no unique government 2Y/10Y close header map "+repr(candidates[:8]))
    return candidates[0]


def reconcile(raw: bytes, web: dict, rates: dict, *, url: str=URL) -> dict:
    require(url in (URL,ALTERNATE) and raw.startswith(b"PK\x03\x04")
            and len(raw)>=1000 and len(raw)<10_000_000,
            "unexpected source URL, size or XLSX signature")
    require(web.get("schema")=="GMFQ_NZD_B2_LATEST_GOVT_HTML_RESEARCH_V1"
            and web.get("status")==
               "SINGLE_OFFICIAL_RBNZ_HTML_TEXT_CAPTURE__INDEPENDENT_XLSX_REVIEW_PENDING"
            and web.get("source_release_date")=="2026-10-30"
            and web.get("latest_observation_date")=="2026-10-29"
            and web.get("governance",{}).get("eligible_for_official_canonical_promotion") is False,
            "HTML page summary is not the independently reviewed source")
    base=web.get("historical_approved_anchor",{})
    require(rates["NZD"]["date"]==base.get("date")=="2026-10-16"
            and rates["NZD"]["2Y"]==base.get("2Y")==3.89
            and rates["NZD"]["10Y"]==base.get("10Y")==5.,
            "approved canonical B2 anchor drift")
    wb=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
    try:
        sheet,head,dc,c2,c10=locate_government_pair(wb)
        ws=wb[sheet]
        data={}
        for row in ws.iter_rows(min_row=head+1,max_col=max(dc,c2,c10),values_only=True):
            iso=asdate(row[dc-1])
            if iso is None:
                continue
            values=(row[c2-1],row[c10-1])
            if any(type(v) not in (int,float) or not 0<=v<=20 for v in values):
                continue
            candidate=(round(float(values[0]),5),round(float(values[1]),5))
            require(iso not in data or data[iso]==candidate,
                    "conflicting same-day government bond yield in official XLSX")
            data[iso]=candidate
        pairs=web.get("website_rows")
        require(isinstance(pairs,list) and len(pairs)==10,
                "official HTML comparison history not pinned")
        compared=[]
        for p in pairs:
            d=p["date"]
            require(d in data,"missing HTML-publication date in independent XLSX "+d)
            observed=data[d]
            require(abs(observed[0]-p["2Y"])<.00001
                    and abs(observed[1]-p["10Y"])<.00001,
                    "RBNZ independent XLSX mismatches published government 2Y/10Y "+d)
            compared.append(d)
        return {
          "schema":SCHEMA,"status":"OFFICIAL_HTML_XLSX_AGREE_REVIEWABLE_NOT_PUBLISHED",
          "source_url":url,"xlsx_sha256":hashlib.sha256(raw).hexdigest(),
          "xlsx_bytes":len(raw),"worksheet":sheet,"header_row":head,
          "columns_1_based":{"date":dc,"2Y_government_close":c2,"10Y_government_close":c10},
          "latest_web_release":"2026-10-30",
          "latest_pair_date":compared[-1],"latest_2Y":data[compared[-1]][0],
          "latest_10Y":data[compared[-1]][1],
          "paired_dates_compared":compared,"matched_count":len(compared),
          "same_source_two_formats_not_independent_institution":True,
          "independent_human_review_completed":False,
          "eligible_for_automatic_promotion":False,
          "writes_operational_rates":False,
          "writes_macro_or_fx":False,
        }
    finally:
        wb.close()


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--xlsx",type=Path,default=None)
    p.add_argument("--output",type=Path,
                   default=Path("/tmp/rbnz-b2-xlsx-independent-reconciliation.json"))
    args=p.parse_args()
    require(args.output.resolve().is_relative_to(Path("/tmp")),
            "research-only receipt must stay in /tmp")
    used=URL
    if args.xlsx:
        raw=args.xlsx.read_bytes()
    else:
        # Both hosts are listed in the official RBNZ statistical file index.
        # Do not use third-party mirrors, proxy credentials, or unknown hosts.
        # Explicitly retain both HTTP failures rather than claiming an XLSX.
        errors=[]
        raw=None
        for host in (URL,ALTERNATE):
            try:
                req=Request(host,headers={
                    "User-Agent":"GlobalMacroFXQuant/1.0 (read-only official source XLSX cross-check)",
                    "Accept":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"})
                with urlopen(req,timeout=20) as response:
                    require(response.status==200,"RBNZ XLSX endpoint returned non-200")
                    candidate=response.read(10_000_001)
                    require(candidate.startswith(b"PK\x03\x04") and
                            len(candidate)<10_000_001,
                            "official XLSX missing ZIP signature or too large")
                    raw=candidate;used=host;break
            except (OSError,ValueError) as exc:
                errors.append({"official_host":host,
                               "error_type":type(exc).__name__,
                               "reason":str(exc)[:110]})
        require(raw is not None, "all official XLSX hosts inaccessible: "+
                json.dumps(errors))
    result=reconcile(raw,json.loads(HTML.read_text()),
                     json.loads(RATES.read_text()),url=used)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],
                      "xlsx_sha256":result["xlsx_sha256"],
                      "latest":result["latest_pair_date"],
                      "paired_source_rows":result["matched_count"],
                      "official_promotion":False}))


if __name__=="__main__":
    main()
