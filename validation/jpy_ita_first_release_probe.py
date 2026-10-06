#!/usr/bin/env python3
import argparse
import io
import json
import re
import urllib.request
from datetime import date

from pypdf import PdfReader

ANCHORS = {
    "2019-01": {
        "url": "https://www.meti.go.jp/statistics/tyo/sanzi/result/pdf/ITA_press_201901j.pdf",
        "release_date": "2019-03-13",
        "tertiary_sa_index": 106.5,
    },
    "2020-01": {
        "url": "https://www.meti.go.jp/statistics/tyo/sanzi/result/pdf/ITA_press_202001j.pdf",
        "release_date": "2020-03-13",
        "tertiary_sa_index": 105.9,
    },
    "2023-01": {
        "url": "https://www.meti.go.jp/statistics/tyo/sanzi/result/pdf/ITA_press_202301j.pdf",
        "release_date": "2023-03-17",
        "tertiary_sa_index": 100.5,
    },
}


def fetch_pdf(url):
    headers={
        "User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36",
        "Accept":"application/pdf,*/*;q=0.8",
        "Accept-Language":"ja,en-US;q=0.9,en;q=0.8",
        "Referer":"https://www.meti.go.jp/statistics/tyo/sanzi/",
    }
    req=urllib.request.Request(url,headers=headers)
    with urllib.request.urlopen(req,timeout=30) as r:
        raw=r.read(); status=getattr(r,"status",200)
    reader=PdfReader(io.BytesIO(raw))
    text="\n".join((p.extract_text() or "") for p in reader.pages[:4])
    return status,raw,text


def parse_japanese_date(text):
    # Gregorian publication dates appear in the archived press PDFs as ２０１９年３月１３日 etc.
    trans=str.maketrans("０１２３４５６７８９","0123456789")
    z=text.translate(trans)
    m=re.search(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",z)
    if not m:return None
    return date(int(m.group(1)),int(m.group(2)),int(m.group(3))).isoformat()


def parse_index(text):
    trans=str.maketrans("０１２３４５６７８９．","0123456789.")
    z=text.translate(trans)
    patterns=[
        r"第３次産業活動指数[^\n]{0,80}?([0-9]{2,3}(?:\.[0-9]+)?)",
        r"Indices of Tertiary Industry Activity[^\n]{0,120}?([0-9]{2,3}(?:\.[0-9]+)?)",
    ]
    for p in patterns:
        m=re.search(p,z,re.I)
        if m:return float(m.group(1))
    return None


def probe(month,exp):
    status,raw,text=fetch_pdf(exp["url"])
    row={
        "reference_month":month,
        "source_url":exp["url"],
        "http_status":status,
        "pdf_bytes":len(raw),
        "release_date":parse_japanese_date(text),
        "tertiary_sa_index":parse_index(text),
        "expected_anchor":{k:v for k,v in exp.items() if k!="url"},
    }
    row["anchor_match"]=(row["release_date"]==exp["release_date"] and row["tertiary_sa_index"]==exp["tertiary_sa_index"])
    return row


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--output",required=True); args=ap.parse_args()
    rows=[probe(m,e) for m,e in ANCHORS.items()]
    passed=all(r["http_status"]==200 and r["anchor_match"] for r in rows)
    out={
        "schema":"GMFQ_JPY_ITA_FIRST_RELEASE_FEASIBILITY_V1",
        "status":"PASS" if passed else "FAIL",
        "source":"METI archived Indices of Tertiary Industry Activity press PDFs",
        "series":"seasonally adjusted Tertiary Industry Activity index",
        "rows":rows,
        "publication_date_in_source":True,
        "revised_history_fallback_used":False,
        "growth_series_count":1,
        "pit_activation":False
    }
    with open(args.output,"w",encoding="utf-8") as f:
        json.dump(out,f,indent=2,ensure_ascii=False); f.write("\n")
    print(json.dumps(out,indent=2,ensure_ascii=False))
    if not passed: raise SystemExit(1)

if __name__=="__main__": main()
