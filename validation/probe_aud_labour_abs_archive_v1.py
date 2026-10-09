#!/usr/bin/env python3
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from urllib.request import Request, urlopen

UA = "Mozilla/5.0 (compatible; global-macro-fx-quant/1.0)"
ANCHORS = [
    {"reference_month":"2018-01","era":"AUSSTATS_LEGACY","url":"https://www.abs.gov.au/ausstats/abs%40.nsf/lookup/6202.0Media%20Release1Jan%202018","expected_rate":5.5},
    {"reference_month":"2019-01","era":"AUSSTATS_LEGACY","url":"https://www.abs.gov.au/ausstats/abs%40.nsf/Lookup/6202.0Main%20Features3Jan%202019","expected_rate":5.0},
    {"reference_month":"2021-01","era":"MODERN_RELEASE","url":"https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia/jan-2021","expected_rate":6.4},
    {"reference_month":"2023-01","era":"MODERN_RELEASE","url":"https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia/jan-2023","expected_rate":3.7},
    {"reference_month":"2026-08","era":"MODERN_RELEASE","url":"https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-australia/aug-2026","expected_rate":4.6},
]
MONTHS={"jan":1,"january":1,"feb":2,"february":2,"mar":3,"march":3,"apr":4,"april":4,"may":5,"jun":6,"june":6,"jul":7,"july":7,"aug":8,"august":8,"sep":9,"september":9,"oct":10,"october":10,"nov":11,"november":11,"dec":12,"december":12}

def get(url):
    req=Request(url,headers={"User-Agent":UA,"Accept-Language":"en-AU,en;q=0.9"})
    with urlopen(req,timeout=45) as r:return r.read(),r.headers.get("Content-Type",""),r.geturl()

def textify(raw):
    s=raw.decode("utf-8",errors="replace");s=re.sub(r"<script\b.*?</script>"," ",s,flags=re.I|re.S);s=re.sub(r"<style\b.*?</style>"," ",s,flags=re.I|re.S);s=html.unescape(re.sub(r"<[^>]+>"," ",s));return re.sub(r"\s+"," ",s).strip()

def parse_reference_month(text,expected):
    ey,em=map(int,expected.split("-")); names=[k for k,v in MONTHS.items() if v==em]
    if not any(re.search(rf"\b{re.escape(n)}\s+{ey}\b",text,flags=re.I) for n in names): raise ValueError(f"reference month identity not established for {expected}")

def parse_release_timestamp(text,expected_ref):
    m=re.search(r"Release date and time\s+(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d{2}\s*(?:am|pm))\s*([A-Z]{3,5})",text,flags=re.I)
    if m:return {"release_date":m.group(1),"release_time":re.sub(r"\s+","",m.group(2)).lower(),"timezone":m.group(3).upper(),"source":"page_explicit"}
    m=re.search(r"Released at\s+(\d{1,2}:\d{2})\s*(AM|PM)\s*\(CANBERRA TIME\)\s*(\d{1,2}/\d{1,2}/\d{4})",text,flags=re.I)
    if m:return {"release_date":m.group(3),"release_time":m.group(1)+m.group(2).lower(),"timezone":"CANBERRA_TIME","source":"page_explicit"}
    m=re.search(r"(\d{1,2}\s+[A-Z][a-z]+\s+\d{4}).{0,160}?Embargo:\s*(\d{1,2}:\d{2})\s*(am|pm)\s*\(Canberra Time\)",text,flags=re.I|re.S)
    if m:return {"release_date":m.group(1),"release_time":m.group(2)+m.group(3).lower(),"timezone":"CANBERRA_TIME","source":"page_explicit"}
    raise ValueError(f"explicit release timestamp not found for {expected_ref}")

def seasonally_adjusted_rate(text,expected_ref):
    ey,em=map(int,expected_ref.split("-")); full=[k.title() for k,v in MONTHS.items() if v==em and len(k)>3][0]
    # 1) Explicit phrases that name the seasonally adjusted unemployment rate.
    m=re.search(r"seasonally adjusted unemployment rate.{0,220}?\b(?:to|at|was)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:%|per cent)",text,flags=re.I|re.S)
    if m:return float(m.group(1))
    # 2) Period-specific seasonally adjusted sections. These must run before any generic
    # unemployment-rate fallback because ABS pages often present TREND first.
    markers=[
        f"In seasonally adjusted terms, in {full} {ey}",
        f"Seasonally adjusted estimates for {full} {ey}",
        "SEASONALLY ADJUSTED ESTIMATES",
        "Key statistics - Seasonally adjusted",
        "Seasonally Adjusted",
    ]
    for marker in markers:
        pos=text.lower().find(marker.lower())
        if pos>=0:
            win=text[pos:pos+2600]
            for p in [
                r"unemployment rate.{0,180}?\b(?:remained steady at|remained at|was steady at|was unchanged at|increased to|decreased to|rose to|fell to|to|at)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:%|per cent)",
                r"Unemployment rate\s*\(%\).{0,180}?([0-9]+(?:\.[0-9]+)?)\s+([0-9]+(?:\.[0-9]+)?)",
                r"Unemployment rate.{0,120}?([0-9]+(?:\.[0-9]+)?)\s*%",
            ]:
                m=re.search(p,win,flags=re.I|re.S)
                if m:
                    # In table form group 2 is the current/reference-period value.
                    return float(m.group(2) if m.lastindex and m.lastindex>=2 else m.group(1))
    # 3) Narrow period-specific prose fallback.
    for p in [
        rf"In {full} {ey}, the unemployment rate[^0-9]{{0,120}}(?:to|at)?\s*([0-9]+(?:\.[0-9]+)?)% in seasonally adjusted terms",
        rf"seasonally adjusted estimates for {full} {ey}:.{{0,900}}?Unemployment rate[^0-9]{{0,120}}(?:to|at)?\s*([0-9]+(?:\.[0-9]+)?)%",
    ]:
        m=re.search(p,text,flags=re.I|re.S)
        if m:return float(m.group(1))
    raise ValueError(f"seasonally adjusted unemployment rate not found for {expected_ref}")

def probe(a):
    raw,ct,final=get(a["url"]);text=textify(raw)
    if "Australian Bureau of Statistics" not in text and "ABS" not in text:raise ValueError("ABS identity not established")
    if "Labour Force" not in text:raise ValueError("Labour Force identity not established")
    parse_reference_month(text,a["reference_month"]);rate=seasonally_adjusted_rate(text,a["reference_month"])
    if abs(rate-float(a["expected_rate"]))>1e-9:raise ValueError(f"rate mismatch {a['reference_month']}: {rate} != {a['expected_rate']}")
    stamp=parse_release_timestamp(text,a["reference_month"])
    return {"reference_month":a["reference_month"],"era":a["era"],"url":a["url"],"final_url":final,"content_type":ct,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"seasonally_adjusted_unemployment_rate":rate,**stamp}

def main():
    out={"schema":"GMFQ_AUD_LABOUR_ABS_ARCHIVE_ROUTE_PROBE_V1","checked_at_utc":datetime.now(timezone.utc).isoformat(),"authority":"Australian Bureau of Statistics","route_class":"OFFICIAL_DIRECT_PERIOD_SPECIFIC_ARCHIVE","contract":{"series_id":"AU_UNEMP_RATE","frequency":"M","transformation":"level","seasonal_adjustment":"seasonally adjusted"},"anchors":[],"status":"PASS"}
    for a in ANCHORS:
        try:out["anchors"].append(probe(a))
        except Exception as e:out["anchors"].append({"reference_month":a["reference_month"],"era":a["era"],"url":a["url"],"error":repr(e)});out["status"]="FAIL"
    print(json.dumps(out,indent=2));
    if out["status"]!="PASS":raise SystemExit(1)
if __name__=="__main__":main()
