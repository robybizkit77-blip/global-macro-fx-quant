#!/usr/bin/env python3
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin
from urllib.request import Request, urlopen

BASE = "https://www.bls.gov"
INDEX = "https://www.bls.gov/bls/news-release/empsit.htm"
UA = "GMFQ-Strict-PIT-validation/1.0 (+https://github.com/robybizkit77-blip/global-macro-fx-quant)"
TARGETS = ["2018-02-01", "2023-01-01", "2026-09-01"]


def get(url):
    req = Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    with urlopen(req, timeout=40) as r:
        return r.read(), r.headers.get("Content-Type", ""), r.geturl()


def visible(raw):
    text = raw.decode("utf-8", errors="replace")
    text = re.sub(r"<script\b.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.I | re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text).strip()


def parse_archive_index(raw):
    text = raw.decode("utf-8", errors="replace")
    links = []
    for href in re.findall(r'href=["\']([^"\']*?/news\.release/archives/empsit_\d{8}\.htm)["\']', text, flags=re.I):
        m = re.search(r"empsit_(\d{2})(\d{2})(\d{4})\.htm", href, flags=re.I)
        if not m:
            continue
        mm, dd, yyyy = m.groups()
        dt = f"{yyyy}-{mm}-{dd}"
        links.append((dt, urljoin(BASE, href)))
    # Some archive pages use absolute or root-relative URLs without a preceding slash pattern.
    for href in re.findall(r'href=["\']([^"\']*empsit_\d{8}\.htm)["\']', text, flags=re.I):
        m = re.search(r"empsit_(\d{2})(\d{2})(\d{4})\.htm", href, flags=re.I)
        if not m:
            continue
        mm, dd, yyyy = m.groups()
        dt = f"{yyyy}-{mm}-{dd}"
        links.append((dt, urljoin(BASE, href)))
    uniq = {}
    for dt, url in links:
        uniq[(dt, url)] = True
    return sorted(uniq)


def nearest(rows, target):
    t = datetime.strptime(target, "%Y-%m-%d").date()
    return min(rows, key=lambda x: abs((datetime.strptime(x[0], "%Y-%m-%d").date() - t).days))


def validate_release(dt, url):
    raw, ct, final = get(url)
    text = visible(raw)
    required = ["THE EMPLOYMENT SITUATION", "unemployment rate", "U.S. Bureau of Labor Statistics"]
    if not all(x.lower() in text.lower() for x in required):
        raise ValueError(f"release identity failed for {dt}")
    rate_hits = re.findall(r"unemployment rate.{0,120}?([0-9]+(?:\.[0-9]+)?)\s*percent", text, flags=re.I)
    return {
        "release_date": dt,
        "url": url,
        "final_url": final,
        "content_type": ct,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "headline_rate_candidates": rate_hits[:10],
        "employment_situation_identity": True,
    }


def main():
    raw, _, final = get(INDEX)
    rows = parse_archive_index(raw)
    if len(rows) < 100:
        raise SystemExit(f"archive route too sparse: {len(rows)} links")
    anchors = []
    for target in TARGETS:
        dt, url = nearest(rows, target)
        anchors.append(validate_release(dt, url))
    out = {
        "schema": "GMFQ_USD_LABOUR_BLS_ARCHIVE_PROBE_V1",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "authority": "U.S. Bureau of Labor Statistics",
        "route_class": "OFFICIAL_DIRECT_PERIOD_SPECIFIC_ARCHIVE",
        "archive_index": final,
        "archive_link_count": len(rows),
        "archive_min_release": rows[0][0],
        "archive_max_release": rows[-1][0],
        "anchors": anchors,
        "status": "PASS",
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
