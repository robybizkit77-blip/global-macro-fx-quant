#!/usr/bin/env python3
import csv
import io
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URLS = [
    "https://www.cmegroup.com/ftp/grs/ctr/rt/rates/2026/10-Oct/IR.20261002.csv",
    "https://www.cmegroup.com/ftp/pub/pub/grs/ctr/rt/rates/2026/10-Oct/IR.20261002.csv",
]
OUT = Path("validation/cb_pricing/usd_cme_zq_archive_probe_receipt_v1.json")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 GMFQ-CB-Pricing-Probe/1.0",
            "Accept": "text/csv,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        status = getattr(response, "status", None)
        if status not in (None, 200):
            raise RuntimeError(f"unexpected HTTP status: {status}")
        return response.read()


def write_receipt(receipt: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


def main() -> int:
    checked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    attempts = []
    raw = None
    selected_url = None

    for url in URLS:
        try:
            raw = fetch(url)
            selected_url = url
            attempts.append({"url": url, "status": "HTTP_200", "bytes": len(raw)})
            break
        except urllib.error.HTTPError as exc:
            attempts.append({"url": url, "status": "HTTP_ERROR", "http_status": exc.code, "error": str(exc)})
        except urllib.error.URLError as exc:
            attempts.append({"url": url, "status": "URL_ERROR", "error": str(exc.reason)})
        except Exception as exc:
            attempts.append({"url": url, "status": "ERROR", "error_type": type(exc).__name__, "error": str(exc)})

    base = {
        "schema": "GMFQ_USD_CME_ZQ_ARCHIVE_PROBE_V1",
        "checked_at_utc": checked_at,
        "source": "CME Group official FTP/HTTP archive",
        "attempts": attempts,
        "runtime_mutated": False,
        "publication_performed": False,
    }

    if raw is None:
        write_receipt({**base, "status": "NO_ACCESSIBLE_OFFICIAL_ARCHIVE_PATH"})
        return 0

    text = raw.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        write_receipt({**base, "status": "EMPTY_CSV", "selected_url": selected_url, "bytes": len(raw), "row_count": 0})
        return 0

    header = rows[0]
    zq_rows = []
    for row in rows[1:]:
        joined = "|".join(row).upper()
        if "ZQ" in joined or "FED FUND" in joined or "FEDERAL FUND" in joined:
            zq_rows.append(row)

    write_receipt({
        **base,
        "status": "PASS" if zq_rows else "NO_ZQ_ROWS_FOUND",
        "selected_url": selected_url,
        "bytes": len(raw),
        "row_count": len(rows),
        "header": header,
        "zq_like_row_count": len(zq_rows),
        "zq_like_sample": zq_rows[:12],
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
