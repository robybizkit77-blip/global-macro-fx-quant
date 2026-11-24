#!/usr/bin/env python3
"""Exact ECB BLS actual enterprise credit standards, read-only source probe.

ECB BLS API quarter labels denote publication quarter, not survey reference
quarter. Positive means net tightening. Never overwrite native observations
until overlap and date conventions have been reviewed.
"""
import argparse
import csv
import io
import json
import math
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

KEY = "BLS.Q.U2.ALL.O.E.Z.B3.ST.S.WFNET"
API = "https://data-api.ecb.europa.eu/service/data/BLS/" + KEY[4:] + "?format=csvdata&startPeriod=2016-Q1"
REPORT = "https://www.ecb.europa.eu/stats/ecb_surveys/bank_lending_survey/html/ecb.blssurvey2026q3~c6a731e213.en.html"
ROOT = Path(__file__).resolve().parents[2]

def require(ok, message):
    if not ok:
        raise ValueError(message)

def quarter_index(s):
    require(isinstance(s, str) and re.fullmatch(r"\d{4}-Q[1-4]", s), "invalid quarter")
    return int(s[:4])*4 + int(s[-1])-1

def quarter_label(n):
    return f"{n//4}-Q{n%4+1}"

def parse(content, today):
    reader = csv.DictReader(io.StringIO(content))
    cols = set(reader.fieldnames or [])
    require({"TIME_PERIOD","OBS_VALUE"} <= cols, "missing observation columns")
    key_col = "KEY" if "KEY" in cols else "SERIES_KEY"
    require(key_col in cols, "missing identity")
    records = {}
    for row in reader:
        require(row[key_col] == KEY, "wrong BLS variant")
        q = quarter_index(row["TIME_PERIOD"])
        require(q <= today.year*4+(today.month-1)//3, "future publication quarter")
        raw = row["OBS_VALUE"]
        if raw in ("", ".", None):
            continue
        value = float(raw)
        require(math.isfinite(value) and -100 <= value <= 100, "invalid net percent")
        require(q not in records, "duplicate publication quarter")
        records[q] = value
    qs = sorted(records)
    require(len(qs) >= 20, "insufficient history")
    require(list(records) in (qs, list(reversed(qs))), "unordered history")
    require(all(b-a == 1 for a,b in zip(qs,qs[1:])), "quarter gap")
    for period, expected in (("2026-Q3",7),("2026-Q4",9)):
        q = quarter_index(period)
        require(q in records and abs(records[q]-expected)<0.51,
                "ECB October report anchor mismatch: "+period)
    require(qs[-1] >= quarter_index("2026-Q4"), "latest known release missing")
    return records

def compare(records, native):
    ref = dict(zip(native["dates"],native["values"]))
    out = {}
    for shift in (0,-1):
        pairs = [(v,ref[quarter_label(q+shift)]) for q,v in records.items()
                 if quarter_label(q+shift) in ref]
        out[str(shift)] = {"matched":len(pairs),
            "mean_absolute_difference":sum(abs(a-b) for a,b in pairs)/len(pairs) if pairs else None,
            "within_0_51":sum(abs(a-b)<0.51 for a,b in pairs)}
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--receipt",type=Path,required=True)
    args=p.parse_args()
    today=datetime.now(ZoneInfo("Europe/Rome")).date()
    receipt={"series_id":KEY,"source":API,"official_report":REPORT,
             "checked_rome":today.isoformat(),"native_unchanged":True,
             "scheduled_execution_certified":False}
    try:
        req=urllib.request.Request(API,headers={"Accept":"text/csv","User-Agent":"FXQuant-Research-Sources/1.0"})
        with urllib.request.urlopen(req,timeout=30) as response:
            require(response.geturl().startswith("https://data-api.ecb.europa.eu/"),"unexpected host")
            raw=response.read(2_000_001)
        require(len(raw)<2_000_001,"response too large")
        records=parse(raw.decode("utf-8-sig"),today)
        native=json.loads((ROOT/"live_data/sections/NATIVE_LIQ_DATA.json").read_text())["EUR"]["conditions"]
        q=max(records)
        receipt.update(status="EXACT_SOURCE_OBSERVED_RESEARCH_ONLY",
                       latest_publication_quarter=quarter_label(q),
                       latest_reference_quarter=quarter_label(q-1),
                       latest_value=records[q],count=len(records),
                       positive_means="tightening",
                       native_overlap=compare(records,native),
                       observations=[{"publication_quarter":quarter_label(k),
                                      "reference_quarter":quarter_label(k-1),
                                      "value":records[k]} for k in sorted(records)])
    except (OSError,ValueError,UnicodeError) as e:
        receipt.update(status="WITHHELD_SOURCE_UNVERIFIED",reason=str(e)[:320])
    args.receipt.write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps({k:v for k,v in receipt.items() if k!="observations"}))
    if receipt["status"].startswith("WITHHELD"):
        raise SystemExit(2)

if __name__=="__main__":
    main()
