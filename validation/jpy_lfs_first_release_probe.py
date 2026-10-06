#!/usr/bin/env python3
import argparse
import io
import json
import re
import urllib.request
from datetime import date

from pypdf import PdfReader

URL_TEMPLATE = "https://www.stat.go.jp/data/roudou/rireki/tsuki/pdf/{yyyymm}.pdf"

EXPECTED_ANCHORS = {
    "2018-01": {"unemployment_rate_sa_pct": 2.4, "employed_sa_10k": 6595},
    "2019-01": {"unemployment_rate_sa_pct": 2.5, "employed_sa_10k": 6665},
    "2023-01": {"unemployment_rate_sa_pct": 2.4, "employed_sa_10k": 6744},
}


def era_to_iso(era: str, year_text: str, month: str, day: str) -> str:
    y = 1 if year_text == "元" else int(year_text)
    if era == "平成":
        year = 1988 + y
    elif era == "令和":
        year = 2018 + y
    else:
        raise ValueError(era)
    return date(year, int(month), int(day)).isoformat()


def extract_release_date(text: str):
    m = re.search(r"(平成|令和)\s*(元|\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日", text)
    if not m:
        return None
    return era_to_iso(m.group(1), m.group(2), m.group(3), m.group(4))


def sa_section(text: str) -> str:
    for marker in ("季節調整値でみた結果の概要", "季節調整値でみた結果"):
        i = text.find(marker)
        if i >= 0:
            return text[i:]
    return text


def extract_unemployment_rate(text: str):
    section = sa_section(text)
    patterns = [
        r"完全失業率(?:（季節調整値）)?\s*(?:は|：|:)\s*([0-9]+(?:\.[0-9]+)?)\s*[％%]",
        r"完全失業率[^\n]{0,80}?([0-9]+(?:\.[0-9]+)?)\s*[％%]",
    ]
    for p in patterns:
        m = re.search(p, section)
        if m:
            return float(m.group(1))
    return None


def extract_employed_sa_10k(text: str):
    section = sa_section(text)
    patterns = [
        r"就業者数\s*(?:は|：|:)\s*([0-9]{4})\s*万人",
        r"就業者\s+([0-9]{4})\s+(?:[-−+]?\d+)",
    ]
    for p in patterns:
        m = re.search(p, section)
        if m:
            return int(m.group(1))
    return None


def fetch_month(month: str):
    yyyymm = month.replace("-", "")
    url = URL_TEMPLATE.format(yyyymm=yyyymm)
    req = urllib.request.Request(url, headers={"User-Agent": "GMFQ-PIT-validation/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        status = getattr(r, "status", 200)
    reader = PdfReader(io.BytesIO(raw))
    text = "\n".join((p.extract_text() or "") for p in reader.pages[:8])
    return {
        "reference_month": month,
        "source_url": url,
        "http_status": status,
        "pdf_bytes": len(raw),
        "release_date": extract_release_date(text),
        "unemployment_rate_sa_pct": extract_unemployment_rate(text),
        "employed_sa_10k": extract_employed_sa_10k(text),
        "text_chars_examined": len(text),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", nargs="+", default=list(EXPECTED_ANCHORS))
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    rows = []
    for month in args.months:
        row = fetch_month(month)
        exp = EXPECTED_ANCHORS.get(month)
        row["expected_anchor"] = exp
        row["anchor_match"] = (
            exp is None
            or (
                row["unemployment_rate_sa_pct"] == exp["unemployment_rate_sa_pct"]
                and row["employed_sa_10k"] == exp["employed_sa_10k"]
            )
        )
        rows.append(row)

    passed = all(
        r["http_status"] == 200
        and r["release_date"] is not None
        and r["unemployment_rate_sa_pct"] is not None
        and r["employed_sa_10k"] is not None
        and r["anchor_match"]
        for r in rows
    )
    out = {
        "schema": "GMFQ_JPY_LFS_FIRST_RELEASE_FEASIBILITY_V2",
        "status": "PASS" if passed else "FAIL",
        "source": "Statistics Bureau of Japan archived Labour Force Survey monthly preliminary PDFs",
        "url_template": URL_TEMPLATE,
        "series": [
            "seasonally adjusted unemployment rate",
            "seasonally adjusted employed persons"
        ],
        "purpose": "Prove that two publication-time JPY Labour inputs plus release dates can be reconstructed from archived official PDFs without revised-history fallback.",
        "release_time_policy": {
            "status": "SEPARATE_YEAR_SCHEDULE_CONFIRMATION_REQUIRED",
            "note": "Do not infer intraday time from the PDF itself; pair each release date with the official annual release schedule before PIT activation."
        },
        "rows": rows,
        "labour_block_series_count": 2,
        "revised_history_fallback_used": False,
        "pit_activation": False,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
