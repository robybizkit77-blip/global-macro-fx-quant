#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, urllib.error, urllib.request

PROBES = [
    ("2018-03", "2018-04-11"),
    ("2020-01", "2020-02-13"),
    ("2024-01", "2024-02-13"),
]
BASE = "https://www.bls.gov/news.release/archives/cpi_{date}.{ext}"
UA = "Mozilla/5.0 (compatible; GLOBAL-MACRO-FX-QUANT/1.0; research validation)"


def archive_stamp(iso_date: str) -> str:
    year, month, day = iso_date.split("-")
    return f"{month}{day}{year}"


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1",
        "Connection": "close",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            status = getattr(r, "status", 200)
            ctype = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return {"url": url, "ok": False, "http_status": e.code, "error": repr(e)}
    except Exception as e:
        return {"url": url, "ok": False, "error": repr(e)}

    text = raw.decode("utf-8", errors="replace")
    norm = re.sub(r"\s+", " ", text).upper()
    markers = {
        "consumer_price_index": "CONSUMER PRICE INDEX" in norm,
        "all_items": "ALL ITEMS" in norm,
        "seasonally_adjusted": "SEASONALLY ADJUSTED" in norm,
        "unadjusted_indexes": "UNADJUSTED INDEX" in norm,
        "revision_of_sa_indexes": "REVISION OF SEASONALLY ADJUSTED INDEXES" in norm,
    }
    return {
        "url": url,
        "ok": status == 200 and markers["consumer_price_index"],
        "http_status": status,
        "content_type": ctype,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "markers": markers,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True, type=pathlib.Path)
    args = ap.parse_args()

    rows = []
    for reference_month, release_date in PROBES:
        stamp = archive_stamp(release_date)
        variants = []
        for ext in ("htm", "txt"):
            variants.append(fetch(BASE.format(date=stamp, ext=ext)))
        rows.append({
            "reference_month": reference_month,
            "release_date": release_date,
            "archive_stamp": stamp,
            "variants": variants,
            "any_official_archive_readable": any(v.get("ok") for v in variants),
        })

    transport_ok = all(r["any_official_archive_readable"] for r in rows)
    out = {
        "schema": "GMFQ_USD_CPI_RELEASE_ARCHIVE_TRANSPORT_V1",
        "status": "DISCOVERY_PASS" if transport_ok else "DISCOVERY_WITHHELD",
        "authority": "U.S. Bureau of Labor Statistics",
        "purpose": "Test deterministic transport to release-specific archived CPI news releases whose filenames encode the official release date.",
        "rows": rows,
        "transport_ok": transport_ok,
        "invariants": {
            "official_bls_only": True,
            "release_specific_url": True,
            "release_date_encoded_in_filename": True,
            "no_current_revised_history_substitution": True,
            "no_production_write": True,
            "certification_implied": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if transport_ok else 2

if __name__ == "__main__":
    raise SystemExit(main())
