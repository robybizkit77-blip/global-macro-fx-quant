#!/usr/bin/env python3
import hashlib
import html
import json
import re
import subprocess
from datetime import datetime, timezone
from urllib.parse import urljoin

BASE = "https://www.bls.gov"
INDEX = "https://www.bls.gov/bls/news-release/empsit.htm"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/154.0 Safari/537.36"
TARGETS = ["2018-02-01", "2023-01-01", "2026-09-01"]
DIRECT_ANCHORS = [
    ("2018-02-02", "https://www.bls.gov/news.release/archives/empsit_02022018.htm"),
    ("2026-08-07", "https://www.bls.gov/news.release/archives/empsit_08072026.htm"),
]


def curl_get(url):
    p = subprocess.run([
        "curl", "--fail", "--silent", "--show-error", "--location", "--http1.1",
        "--compressed", "--retry", "2", "--retry-all-errors",
        "-A", UA, "-H", "Accept-Language: en-US,en;q=0.9",
        "-H", "Accept: text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
        url,
    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.stdout, "curl/browser-like", url


def visible(raw):
    text = raw.decode("utf-8", errors="replace")
    text = re.sub(r"<script\b.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.I | re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text).strip()


def parse_archive_index(raw):
    text = raw.decode("utf-8", errors="replace")
    links = []
    for href in re.findall(r'href=["\']([^"\']*empsit_\d{8}\.(?:htm|pdf))["\']', text, flags=re.I):
        m = re.search(r"empsit_(\d{2})(\d{2})(\d{4})\.(?:htm|pdf)", href, flags=re.I)
        if not m:
            continue
        mm, dd, yyyy = m.groups()
        dt = f"{yyyy}-{mm}-{dd}"
        links.append((dt, urljoin(BASE, href)))
    # Prefer HTML where both HTML and PDF point to the same vintage.
    by_date = {}
    for dt, url in links:
        old = by_date.get(dt)
        if old is None or (old.lower().endswith(".pdf") and url.lower().endswith(".htm")):
            by_date[dt] = url
    return sorted(by_date.items())


def nearest(rows, target):
    t = datetime.strptime(target, "%Y-%m-%d").date()
    return min(rows, key=lambda x: abs((datetime.strptime(x[0], "%Y-%m-%d").date() - t).days))


def validate_release(dt, url):
    raw, transport, final = curl_get(url)
    text = visible(raw)
    required = ["THE EMPLOYMENT SITUATION", "unemployment rate", "U.S. Bureau of Labor Statistics"]
    if not all(x.lower() in text.lower() for x in required):
        raise ValueError(f"release identity failed for {dt}")
    month_match = re.search(r"THE EMPLOYMENT SITUATION\s*[-—]+\s*([A-Z]+)\s+(20\d{2})", text, flags=re.I)
    headline = re.search(
        r"(?:and\s+)?the unemployment rate(?:\s+was|\s+remained|\s+is|\s+increased to|\s+declined to|\s+edged up to|\s+edged down to|\s+rose to|\s+fell to|\s+changed little at|\s+was unchanged at)?\s*([0-9]+(?:\.[0-9]+)?)\s*percent",
        text, flags=re.I,
    )
    if not headline:
        # Tight fallback limited to the introductory paragraph window.
        pos = text.lower().find("the employment situation")
        window = text[pos:pos+2500] if pos >= 0 else text[:2500]
        headline = re.search(r"unemployment rate.{0,120}?([0-9]+(?:\.[0-9]+)?)\s*percent", window, flags=re.I)
    if not headline:
        raise ValueError(f"headline unemployment rate not found for {dt}")
    return {
        "release_date": dt,
        "url": url,
        "final_url": final,
        "transport": transport,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "reference_period_text": (month_match.group(1).title() + " " + month_match.group(2)) if month_match else None,
        "headline_unemployment_rate": float(headline.group(1)),
        "employment_situation_identity": True,
    }


def main():
    direct = [validate_release(dt, url) for dt, url in DIRECT_ANCHORS]
    index_error = None
    rows = []
    final = INDEX
    try:
        raw, _, final = curl_get(INDEX)
        rows = parse_archive_index(raw)
    except Exception as e:
        index_error = repr(e)

    anchors = []
    if rows:
        if len(rows) < 100:
            raise SystemExit(f"archive route too sparse: {len(rows)} links")
        for target in TARGETS:
            dt, url = nearest(rows, target)
            anchors.append(validate_release(dt, url))

    out = {
        "schema": "GMFQ_USD_LABOUR_BLS_ARCHIVE_PROBE_V1",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "authority": "U.S. Bureau of Labor Statistics",
        "route_class": "OFFICIAL_DIRECT_PERIOD_SPECIFIC_ARCHIVE",
        "archive_index": final,
        "archive_index_accessible": bool(rows),
        "archive_index_error": index_error,
        "archive_link_count": len(rows),
        "archive_min_release": rows[0][0] if rows else None,
        "archive_max_release": rows[-1][0] if rows else None,
        "direct_anchors": direct,
        "index_anchors": anchors,
        "status": "PASS_DIRECT_ONLY" if not rows else "PASS",
    }
    print(json.dumps(out, indent=2))
    # Direct period-specific archive access is mandatory; index access is desirable but not required.
    if len(direct) != len(DIRECT_ANCHORS):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
