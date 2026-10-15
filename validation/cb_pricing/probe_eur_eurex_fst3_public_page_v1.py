#!/usr/bin/env python3
import html
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URLS = [
    "https://www.eurex.com/ex-en/markets/int/mon/3m-euro-str-futures/estr/Three-Month-Euro-STR-Futures-3402480",
    "https://sim-new.eurex.com/ex-en/markets/int/mon/3m-euro-str-futures/estr/Three-Month-Euro-STR-Futures-3402480",
]
OUT = Path("validation/cb_pricing/eur_eurex_fst3_public_page_probe_receipt_v1.json")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 GMFQ-CB-Pricing-Probe/1.0",
            "Accept": "text/html,application/xhtml+xml,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def main() -> int:
    attempts = []
    for url in URLS:
        try:
            raw = fetch(url)
            text = raw.decode("utf-8", errors="replace")
            upper = text.upper()
            snippets = []
            for pat in ("D. SETTLE", "FST3", "TRADING DATE", "EURO STR"):
                idx = upper.find(pat.upper())
                if idx >= 0:
                    snippets.append({"pattern": pat, "sample": re.sub(r"\s+", " ", text[max(0, idx-250):idx+750])[:1000]})

            product_blocks = []
            for m in re.finditer(r'<script[^>]*type=["\']application/json["\'][^>]*data-product[^>]*>(.*?)</script>', text, flags=re.I | re.S):
                body = html.unescape(m.group(1)).strip()
                block = {"chars": len(body), "sample": re.sub(r"\s+", " ", body)[:5000]}
                try:
                    parsed = json.loads(body)
                    block["json"] = parsed
                except Exception:
                    pass
                product_blocks.append(block)

            candidate_urls = sorted(set(re.findall(r'https?://[^"\'<>\\\s]+', text)))
            interesting_urls = [u for u in candidate_urls if any(k in u.lower() for k in ("stat", "price", "quote", "future", "product", "market", "api"))][:100]

            attempts.append({
                "url": url,
                "status": "HTTP_200",
                "bytes": len(raw),
                "has_fst3": "FST3" in upper,
                "has_d_settle": "D. SETTLE" in upper,
                "has_trading_date": "TRADING DATE" in upper,
                "snippets": snippets,
                "data_product_blocks": product_blocks[:10],
                "interesting_urls": interesting_urls,
            })
        except urllib.error.HTTPError as exc:
            attempts.append({"url": url, "status": "HTTP_ERROR", "http_status": exc.code, "error": str(exc)})
        except Exception as exc:
            attempts.append({"url": url, "status": "ERROR", "error_type": type(exc).__name__, "error": str(exc)})

    reproducible = any(a.get("has_fst3") and a.get("has_d_settle") and a.get("has_trading_date") for a in attempts)
    receipt = {
        "schema": "GMFQ_EUR_EUREX_FST3_PUBLIC_PAGE_PROBE_V1",
        "checked_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": "Eurex official public FST3 product page",
        "status": "MACHINE_REPRODUCIBLE_PRICE_SURFACE_FOUND" if reproducible else "NO_MACHINE_REPRODUCIBLE_SETTLEMENT_SURFACE",
        "attempts": attempts,
        "runtime_mutated": False,
        "publication_performed": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
