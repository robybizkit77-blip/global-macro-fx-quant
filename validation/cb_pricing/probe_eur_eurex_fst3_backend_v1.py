#!/usr/bin/env python3
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PAGE = "https://www.eurex.com/ex-en/markets/int/mon/3m-euro-str-futures/estr/Three-Month-Euro-STR-Futures-3402480"
OUT = Path("validation/cb_pricing/eur_eurex_fst3_backend_probe_receipt_v1.json")
KEYWORDS = ("factsetHostUrl", "connectionToken", "FutureStatistic", "dSettle", "productId", "busDate", "factsetdigitalsolutions", "mdg2")


def get(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 GMFQ-CB-Pricing-Probe/1.0", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def main() -> int:
    page = get(PAGE)
    srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', page, flags=re.I)
    urls = []
    for src in srcs:
        u = urllib.parse.urljoin(PAGE, src)
        if u not in urls:
            urls.append(u)

    matches = []
    errors = []
    for u in urls:
        try:
            text = get(u, timeout=20)
        except Exception as exc:
            errors.append({"url": u, "error_type": type(exc).__name__, "error": str(exc)})
            continue
        lower = text.lower()
        hit_words = [k for k in KEYWORDS if k.lower() in lower]
        if not hit_words:
            continue
        samples = []
        for k in hit_words:
            idx = lower.find(k.lower())
            samples.append({"keyword": k, "sample": re.sub(r"\s+", " ", text[max(0, idx-600):idx+1800])[:2400]})
        matches.append({"url": u, "bytes": len(text.encode('utf-8')), "keywords": hit_words, "samples": samples})

    receipt = {
        "schema": "GMFQ_EUR_EUREX_FST3_BACKEND_PROBE_V1",
        "checked_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "page": PAGE,
        "script_count": len(urls),
        "matching_scripts": matches,
        "fetch_errors": errors,
        "status": "BACKEND_HINTS_FOUND" if matches else "NO_BACKEND_HINTS_FOUND",
        "runtime_mutated": False,
        "publication_performed": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
