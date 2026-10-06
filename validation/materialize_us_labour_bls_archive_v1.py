from __future__ import annotations

import csv
import html
import json
import re
import time
from datetime import datetime
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
    def __init__(self):
        super().__init__(); self.parts=[]
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

def ym_between(y,m):
    return START <= (y,m) <= END

def archive_links():
    raw=get(ARCHIVE)
    # BLS markup is typically: "September 2026 Employment Situation (<a ...>PDF</a>)".
    # The reference-month label is outside the anchor, so parse the surrounding markup directly.
    pat=re.compile(
        r"([A-Za-z]+)\s+(\d{4})\s+Employment\s+Situation\s*\(\s*<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>\s*PDF\s*</a>",
        re.I|re.S,
    )
    out=[]
    for month_name, year_s, href in pat.findall(raw):
        month=MONTHS.get(month_name.lower()); year=int(year_s)
        if not month or not ym_between(year,month): continue
        url=urljoin(ARCHIVE, href)
        if url.lower().endswith(".pdf"): url=url[:-4]+".htm"
        out.append(((year,month),url,f"{month_name} {year} Employment Situation"))
    uniq={k:(u,l) for k,u,l in out}
    return [(k[0],k[1],uniq[k][0],uniq[k][1]) for k in sorted(uniq)]

def parse_release(text: str, ref_y: int, ref_m: int, url: str):
    ts=re.search(r"8:30\s*a\.m\.\s*\((?:ET|EST|EDT)\)\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday),?\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})", text, re.I)
    if not ts:
        ts=re.search(r"8:30\s*a\.m\.\s*(?:\((?:ET|EST|EDT)\))?\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday),?\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})", text, re.I)
    if not ts: raise ValueError("release timestamp not found")
    release_date=datetime.strptime(ts.group(1), "%B %d, %Y").date().isoformat()

    month_name=MONTH_LIST[ref_m-1]
    title_pat=rf"THE EMPLOYMENT SITUATION\s*--\s*{month_name}\s+{ref_y}"
    mt=re.search(title_pat, text, re.I)
    if not mt:
        mt=re.search(rf"EMPLOYMENT SITUATION[^A-Za-z0-9]+{month_name}\s+{ref_y}", text, re.I)
    if not mt: raise ValueError("reference-month title not found")
    body=text[mt.start():mt.start()+5000]

    nfp=None
    p=re.search(r"Total nonfarm payroll employment.{0,260}?\(([+-]\s*[\d,]+)\)", body, re.I)
    if p:
        nfp=int(p.group(1).replace(" ","").replace(",",""))
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
    patterns=[
        r"unemployment rate.{0,80}?\bat\s+(\d+(?:\.\d+)?)\s+percent",
        r"unemployment rate.{0,80}?\b(?:rose|increased|edged up|declined|decreased|fell|dropped)\s+to\s+(\d+(?:\.\d+)?)\s+percent",
        r"unemployment rate.{0,80}?\bwas\s+(\d+(?:\.\d+)?)\s+percent",
    ]
    for pat in patterns:
        p=re.search(pat, body, re.I)
        if p: ur=float(p.group(1)); break
    if ur is None: raise ValueError("first-published unemployment rate not found")

    return {
        "release_date":release_date,
        "release_time_et":"08:30",
        "reference_month":f"{ref_y:04d}-{ref_m:02d}",
        "nfp_change_thousands":nfp,
        "unemployment_rate_pct":ur,
        "source_url":url,
    }

def main():
    links=archive_links()
    expected=[]
    y,m=START
    while (y,m)<=END:
        expected.append(f"{y:04d}-{m:02d}")
        m+=1
        if m==13: y+=1; m=1
    if len(links)!=len(expected):
        got={f"{y:04d}-{m:02d}" for y,m,_,_ in links}
        missing=sorted(set(expected)-got)
        raise SystemExit(f"archive link coverage incomplete: {len(links)}/{len(expected)}; missing={missing}")

    rows=[]; errors=[]
    for y,m,url,label in links:
        try:
            hp=TextParser(); hp.feed(get(url)); text=hp.text()
            rows.append(parse_release(text,y,m,url))
        except Exception as e:
            errors.append({"reference_month":f"{y:04d}-{m:02d}","url":url,"error":str(e)})
        time.sleep(0.15)
    if errors:
        EVID.parent.mkdir(parents=True, exist_ok=True)
        EVID.write_text(json.dumps({"status":"FAIL","rows_parsed":len(rows),"errors":errors},indent=2),encoding="utf-8")
        raise SystemExit(f"strict parse failed for {len(errors)} releases; see {EVID}")

    rows.sort(key=lambda x:x["reference_month"])
    if [r["reference_month"] for r in rows] != expected:
        raise SystemExit("reference-month sequence mismatch")
    if len({r["source_url"] for r in rows}) != len(rows):
        raise SystemExit("duplicate source URLs")
    for r in rows:
        if not (-25000 <= r["nfp_change_thousands"] <= 10000): raise SystemExit(f"implausible NFP parse {r}")
        if not (2.0 <= r["unemployment_rate_pct"] <= 20.0): raise SystemExit(f"implausible unemployment parse {r}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    evidence={
        "schema":"GMFQ_USD_LABOUR_BLS_ARCHIVE_PIT_V1",
        "status":"PASS",
        "source":"Official BLS Employment Situation archived news releases",
        "archive_index":ARCHIVE,
        "coverage":{"start":expected[0],"end":expected[-1],"months":len(rows)},
        "fields":["NFP first-published monthly change","unemployment rate first-published","release date","08:30 ET release time"],
        "method":"Extract only opening-summary values from each archived release; no current database/revised-history substitution.",
        "strict_zero_parse_errors":True,
        "output":str(OUT),
        "notes":[
            "Archived BLS releases may themselves have later errata; the release document is treated as the information set available at its publication checkpoint.",
            "No consensus-surprise series is introduced here.",
            "This materialization certifies the Labour PIT input only; it does not change engine rules or live data."
        ]
    }
    EVID.write_text(json.dumps(evidence,indent=2),encoding="utf-8")
    print(json.dumps(evidence,indent=2))

if __name__=="__main__": main()
