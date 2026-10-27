#!/usr/bin/env python3
"""ONE-SHOT US BLS original release web recovery; research, never a Core CPI series.

Attempts to preserve Aug-2024...Sep-2026 CPI-U *not seasonally adjusted*
12-month headline as actually reported at each first CPI news release.
It is NOT canonical CPIAUCSL SA-index-derived YoY. October 2025 BLS
headline was not published: do not invent it. All 25 rows are first-web
headlines, not an historical revision complete index.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "validation/macro/fixtures/us_bls_cpi_25_first_web_nsa_headlines_2024_08_2026_09.json"
ARCHIVE = "https://www.bls.gov/bls/news-release/cpi.htm"
MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"]
EXPECTED = [f"{y:04d}-{m:02d}" for y in (2024,2025,2026)
            for m in range(1,13)
            if "2024-08" <= f"{y:04d}-{m:02d}" <= "2026-09" and f"{y:04d}-{m:02d}" != "2025-10"]

def require(c, why):
    if not c: raise ValueError("BLS_CPI_FIRST_WEB_REJECTED: "+why)

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.target=None; self.text=[]; self.found=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            self.target=dict(attrs).get("href"); self.text=[]
    def handle_data(self,data):
        if self.target is not None:self.text.append(data)
    def handle_endtag(self,tag):
        if tag=="a" and self.target is not None:
            self.found.append((self.target," ".join(self.text)))
            self.target=None;self.text=[]

def fetch(url):
    require(urlsplit(url).hostname=="www.bls.gov" and
            url.startswith("https://www.bls.gov/"),"only first-party BLS source")
    req=Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; MacroV2Research/1.0; issuer provenance check)",
                             "Accept":"text/html"})
    with urlopen(req,timeout=45) as r:
        end=r.geturl();require(urlsplit(end).hostname=="www.bls.gov","off-publisher redirect")
        data=r.read(1_500_001); require(500<len(data)<1_500_000,"bad first release bytes")
        return data

def parse_release(raw,reference,url):
    readable=html.unescape(re.sub(r"<[^>]+>"," ",raw.decode("utf-8",errors="replace")))
    readable=re.sub(r"\s+"," ",readable)
    month=MONTHS[int(reference[-2:])-1];year=reference[:4]
    title=f"CONSUMER PRICE INDEX - {month.upper()} {year}"
    require(title in readable.upper(),f"publisher headline wrong observation {reference}")
    start=readable.upper().index(title)
    segment=readable[start:start+2200]
    # Distinguish last-12-month *NSA* headline from an SA monthly movement.
    matches=re.findall(r"(?:Over the last 12 months|for the 12 months ending[ a-zA-Z.0-9]*?)[ ,:]*"
                       r"(?:the )?all[ -]items index "
                       r"(?:increased|rose|advanced|declined|decreased|fell)"
                       r" ([0-9]+(?:\.[0-9]+)?) percent",segment,re.I)
    if not matches:
        # Standard BLS alternative grammar ("The all items index rose 2.9 percent
        # for the 12 months ending ...").
        matches=re.findall(r"(?:The |the )all[ -]items index "
                           r"(?:increased|rose|advanced|declined|decreased|fell) "
                           r"([0-9]+(?:\.[0-9]+)?) percent for the 12 months",segment,re.I)
    require(matches,f"first released NSA YoY headline not identified {reference}")
    y=float(matches[0])
    require(0 <= y <= 30, f"unexpected percent rate: {reference}={y}")
    release_name=url.rsplit("/",1)[-1]
    require(re.fullmatch(r"cpi_\d{8}\.htm",release_name) is not None,
            "original archive release date URL not proven")
    rd=datetime.strptime(release_name[4:12],"%m%d%Y").date()
    require(rd.year in (2024,2025,2026) and rd.isoformat() > reference+"-01",
            "release not after economic reference period")
    return {
        "reference_month":reference,
        "source_value_nsa_all_items_cpi_u_yoy_pct":y,
        "publisher_release_date":rd.isoformat(),
        "source_url":url,
        "original_source_page_sha256_at_recovery":hashlib.sha256(raw).hexdigest(),
        "original_source_web_bytes_capture_time_utc":datetime.now(timezone.utc).isoformat(),
        "release_clock_policy":"NEXT_UTC_DAY_IF_NO_INDEPENDENT_ORIGINAL_HOUR_EVIDENCE",
        "publisher_series":"CPI-U_ALL_ITEMS_NOT_SEASONALLY_ADJUSTED_12_MONTH_RATE",
        "production_CPIAUCSL_equivalent":False,
        "first_web_headline_recovered_not_index_first_vintage":True,
        "safe_to_publish_D":False,
    }

def run():
    index_bytes=fetch(ARCHIVE)
    parser=Links();parser.feed(index_bytes.decode("utf-8",errors="replace"))
    found={}
    for href,label in parser.found:
        m=re.fullmatch(r"("+"|".join(MONTHS)+r")\s+(20\d\d)\s+Consumer Price Index",label.strip(),re.I)
        if m:
            ref=f"{m[2]}-{MONTHS.index(m[1].capitalize())+1:02d}"
            url=urljoin(ARCHIVE,href)
            if ref in EXPECTED:
                require(ref not in found,"duplicate monthly official release")
                found[ref]=url
    require(set(found)==set(EXPECTED),
            "all 25 official 2024–2026 archived release links required; found="+str(sorted(found)))
    reports=[]
    for ref in EXPECTED:
        result=parse_release(fetch(found[ref]),ref,found[ref])
        reports.append(result)
        print("BLS",ref,result["source_value_nsa_all_items_cpi_u_yoy_pct"],result["publisher_release_date"],flush=True)
        time.sleep(0.1)
    require(len(reports)==25 and reports[-1]["reference_month"]=="2026-09",
            "BLS historical release window incomplete")
    result={
        "schema":"GMFQ_MACRO_V2_USD_25_ARCHIVED_BLS_NSA_HEADLINES_RESEARCH_V1",
        "source_publisher":"U.S. Bureau of Labor Statistics",
        "original_issuer_archive_url":ARCHIVE,
        "original_index_retrieval_sha256":hashlib.sha256(index_bytes).hexdigest(),
        "periods_2024_08_to_2026_09_except_oct2025":reports,
        "missing_observation":{
            "reference_month":"2025-10",
            "publisher_release":"NO_OCT_2025_CPI_ALL_ITEMS_ISSUED",
            "official_evidence":"https://www.bls.gov/cpi/additional-resources/2025-federal-government-shutdown-impact-cpi-faq.htm",
            "observation_value":None,
            "may_be_imputed_as_official":False,
        },
        "source_values_not_equivalent_to_production_CPIAUCSL_SA_INDEX_YOY":True,
        "source_issued_web_headlines_captured_now_not_2024_original_HTTP_capture":True,
        "candidate_alternative_only":True,
        "publishable_CPIAUCSL_PIT_training_series":False,
        "safe_to_publish_new_D":False,
        "safe_to_change_28_pairs":False,
        "safe_for_beta":False,"safe_for_forward":False,
        "writes_live_data":False,
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":run()
