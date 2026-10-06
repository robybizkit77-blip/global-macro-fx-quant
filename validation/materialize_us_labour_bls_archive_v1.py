from __future__ import annotations

import csv
import html
import json
import re
import time
from datetime import datetime, date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

ARCHIVE = "https://www.bls.gov/bls/news-release/empsit.htm"
OUT = Path("history/pit_v1/USD_LABOUR_BLS_EMPLOYMENT_SITUATION_FIRST_RELEASE_2016_2026.csv")
EVID = Path("validation/USD_LABOUR_BLS_ARCHIVE_PIT_MATERIALIZATION_2026-10-06.json")
START = (2016, 1)
END = (2026, 9)
UA = "Mozilla/5.0 GMFQ-PIT-Audit/1.0 (research; contact via repository)"
MONTH_LIST = ["january","february","march","april","may","june","july","august","september","october","november","december"]
MONTHS = {m: i for i, m in enumerate(MONTH_LIST, 1)}

class TextParser(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]
    def handle_data(self, data): self.parts.append(data)
    def text(self): return re.sub(r"\s+", " ", html.unescape(" ".join(self.parts))).strip()

def get(url: str, tries=4) -> str:
    err=None
    for n in range(tries):
        try:
            req=Request(url, headers={"User-Agent":UA, "Accept":"text/html,application/xhtml+xml"})
            with urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            err=e; time.sleep(1.5*(n+1))
    raise RuntimeError(f"GET failed {url}: {err}")

def ym_between(y,m): return START <= (y,m) <= END

def candidate_urls():
    raw=get(ARCHIVE)
    # Layout-independent extraction: every archive release URL contains empsit_MMDDYYYY.pdf/htm.
    hrefs=re.findall(r"href\s*=\s*[\"']([^\"']*empsit_\d{8}\.(?:pdf|htm))[\"']", raw, re.I)
    urls=set()
    for href in hrefs:
        u=urljoin(ARCHIVE, html.unescape(href))
        mm=re.search(r"empsit_(\d{2})(\d{2})(\d{4})", u, re.I)
        if not mm: continue
        rd=date(int(mm.group(3)),int(mm.group(1)),int(mm.group(2)))
        # Jan-2016 reference month was released in Feb-2016. Latest target Sep-2026 was released Oct-02-2026.
        if date(2016,2,1) <= rd <= date(2026,10,6):
            if u.lower().endswith(".pdf"): u=u[:-4]+".htm"
            urls.add(u)
    return sorted(urls)

def extract_reference_period(text: str):
    p=re.search(r"THE EMPLOYMENT SITUATION\s*--+\s*([A-Za-z]+)\s+(\d{4})", text, re.I)
    if not p:
        p=re.search(r"EMPLOYMENT SITUATION[^A-Za-z0-9]+([A-Za-z]+)\s+(\d{4})", text, re.I)
    if not p: raise ValueError("reference-month title not found")
    m=MONTHS.get(p.group(1).lower()); y=int(p.group(2))
    if not m: raise ValueError(f"unknown month in title: {p.group(1)}")
    return y,m,p.start()

def parse_release(text: str, url: str):
    ref_y,ref_m,title_pos=extract_reference_period(text)
    ts=re.search(r"8:30\s*a\.m\.\s*\((?:ET|EST|EDT)\)\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday),?\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})", text, re.I)
    if not ts:
        ts=re.search(r"8:30\s*a\.m\.\s*(?:\((?:ET|EST|EDT)\))?\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday),?\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})", text, re.I)
    if not ts: raise ValueError("release timestamp not found")
    release_date=datetime.strptime(ts.group(1), "%B %d, %Y").date().isoformat()
    body=text[title_pos:title_pos+5000]

    nfp=None
    p=re.search(r"Total nonfarm payroll employment.{0,260}?\(([+-]\s*[\d,]+)\)", body, re.I)
    if p: nfp=int(p.group(1).replace(" ","").replace(",",""))
    if nfp is None:
        p=re.search(r"Total nonfarm payroll employment.{0,180}?\b(rose|increased|edged up|grew|declined|decreased|fell|dropped)\b.{0,80}?\bby\s+([\d,]+)", body, re.I)
        if p:
            val=int(p.group(2).replace(",","")); verb=p.group(1).lower()
            nfp=-val if verb in {"declined","decreased","fell","dropped"} else val
    if nfp is None:
        p=re.search(r"Total nonfarm payroll employment.{0,300}?([+-]\s*[\d,]+)", body, re.I)
        if p: nfp=int(p.group(1).replace(" ","").replace(",",""))
    if nfp is None: raise ValueError("first-published NFP not found")

    ur=None
    for pat in [
        r"unemployment rate.{0,80}?\bat\s+(\d+(?:\.\d+)?)\s+percent",
        r"unemployment rate.{0,80}?\b(?:rose|increased|edged up|declined|decreased|fell|dropped)\s+to\s+(\d+(?:\.\d+)?)\s+percent",
        r"unemployment rate.{0,80}?\bwas\s+(\d+(?:\.\d+)?)\s+percent",
    ]:
        p=re.search(pat, body, re.I)
        if p: ur=float(p.group(1)); break
    if ur is None: raise ValueError("first-published unemployment rate not found")

    return {"release_date":release_date,"release_time_et":"08:30","reference_month":f"{ref_y:04d}-{ref_m:02d}","nfp_change_thousands":nfp,"unemployment_rate_pct":ur,"source_url":url}

def expected_months():
    out=[]; y,m=START
    while (y,m)<=END:
        out.append(f"{y:04d}-{m:02d}"); m+=1
        if m==13: y+=1; m=1
    return out

def main():
    expected=expected_months(); urls=candidate_urls()
    if len(urls) < len(expected):
        raise SystemExit(f"too few candidate archive URLs: {len(urls)} for expected {len(expected)} months")
    rows=[]; errors=[]
    for url in urls:
        try:
            hp=TextParser(); hp.feed(get(url)); text=hp.text()
            r=parse_release(text,url)
            y,m=map(int,r["reference_month"].split("-"))
            if ym_between(y,m): rows.append(r)
        except Exception as e:
            errors.append({"url":url,"error":str(e)})
        time.sleep(0.12)
    # Deduplicate only exact reference months; multiple releases for one reference month is a hard error.
    by_month={}
    dup=[]
    for r in rows:
        if r["reference_month"] in by_month: dup.append(r["reference_month"])
        by_month[r["reference_month"]]=r
    missing=sorted(set(expected)-set(by_month))
    extra=sorted(set(by_month)-set(expected))
    if errors or dup or missing or extra:
        EVID.parent.mkdir(parents=True,exist_ok=True)
        EVID.write_text(json.dumps({"status":"FAIL","candidate_urls":len(urls),"rows_parsed":len(rows),"missing":missing,"duplicates":sorted(set(dup)),"extra":extra,"errors":errors},indent=2),encoding="utf-8")
        raise SystemExit(f"strict PIT gate failed: errors={len(errors)} missing={len(missing)} dup={len(set(dup))} extra={len(extra)}")
    rows=[by_month[m] for m in expected]
    for r in rows:
        if not (-25000 <= r["nfp_change_thousands"] <= 10000): raise SystemExit(f"implausible NFP parse {r}")
        if not (2.0 <= r["unemployment_rate_pct"] <= 20.0): raise SystemExit(f"implausible unemployment parse {r}")

    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    evidence={"schema":"GMFQ_USD_LABOUR_BLS_ARCHIVE_PIT_V1","status":"PASS","source":"Official BLS Employment Situation archived news releases","archive_index":ARCHIVE,"coverage":{"start":expected[0],"end":expected[-1],"months":len(rows)},"candidate_archive_urls":len(urls),"fields":["NFP first-published monthly change","unemployment rate first-published","release date","08:30 ET release time"],"method":"Extract reference month and opening-summary values from each archived Employment Situation release; no current database/revised-history substitution.","strict_zero_parse_errors":True,"output":str(OUT),"notes":["Archived BLS releases are treated as the information set available at their publication checkpoint.","No consensus-surprise series is introduced here.","This certifies Labour PIT inputs only; engine rules and live data remain untouched."]}
    EVID.write_text(json.dumps(evidence,indent=2),encoding="utf-8")
    print(json.dumps(evidence,indent=2))

if __name__=="__main__": main()
