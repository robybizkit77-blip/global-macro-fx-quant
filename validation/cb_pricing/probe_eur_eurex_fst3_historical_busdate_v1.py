#!/usr/bin/env python3
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PAGE = "https://www.eurex.com/ex-en/markets/int/mon/3m-euro-str-futures/estr/Three-Month-Euro-STR-Futures-3402480"
PRODUCT_ID = "3402482"
DATES = ["20261014", "20261013", "20261007"]
OUT = Path("validation/cb_pricing/eur_eurex_fst3_historical_busdate_probe_receipt_v1.json")


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 GMFQ-CB-Pricing-Probe/1.0", "Accept": "application/json,text/plain,*/*"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def main() -> int:
    page = get(PAGE).decode("utf-8", errors="replace")
    # Extract hostUrl from embedded product JSON/state. Prefer https production host.
    hosts = []
    for pat in [r'"hostUrl"\s*:\s*"([^"]+)"', r'hostUrl\s*:\s*"([^"]+)"']:
        for h in re.findall(pat, page):
            if h not in hosts:
                hosts.append(h)
    # Known production path is also embedded in the prices/statistics widget contract.
    if "https://www.eurex.com/blueprint/servlet" not in hosts:
        hosts.append("https://www.eurex.com/blueprint/servlet")
    if "https://www.eurex.com" not in hosts:
        hosts.append("https://www.eurex.com")

    attempts = []
    successes = []
    for host in hosts:
        base = host.rstrip("/")
        for d in DATES:
            url = f"{base}/api/v1/overallstatistics/{PRODUCT_ID}?busdate={d}&filtertype=overview"
            try:
                raw = get(url)
                text = raw.decode("utf-8", errors="replace")
                try:
                    payload = json.loads(text)
                except Exception:
                    payload = None
                rec = {"host": host, "busdate": d, "url": url, "status": "HTTP_200", "bytes": len(raw), "sample": text[:1200]}
                if payload is not None:
                    rec["json"] = payload
                    successes.append(rec)
                attempts.append(rec)
            except urllib.error.HTTPError as exc:
                attempts.append({"host": host, "busdate": d, "url": url, "status": "HTTP_ERROR", "http_status": exc.code, "error": str(exc)})
            except Exception as exc:
                attempts.append({"host": host, "busdate": d, "url": url, "status": "ERROR", "error_type": type(exc).__name__, "error": str(exc)})

    by_date = {d: [x for x in successes if x["busdate"] == d] for d in DATES}
    all_dates = all(by_date[d] for d in DATES)
    receipt = {
        "schema": "GMFQ_EUR_EUREX_FST3_HISTORICAL_BUSDATE_PROBE_V1",
        "checked_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": "Eurex official prices/statistics REST surface",
        "product_id": PRODUCT_ID,
        "requested_busdates": DATES,
        "hosts": hosts,
        "attempts": attempts,
        "status": "HISTORICAL_BUSDATE_JSON_AVAILABLE" if all_dates else "HISTORICAL_BUSDATE_NOT_PROVEN",
        "runtime_mutated": False,
        "publication_performed": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "hosts": hosts, "successes": len(successes)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
