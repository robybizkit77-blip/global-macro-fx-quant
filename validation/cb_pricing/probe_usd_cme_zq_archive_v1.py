#!/usr/bin/env python3
import csv
import io
import json
import sys
import urllib.request
from datetime import datetime

URL = "https://www.cmegroup.com/ftp/pub/pub/grs/ctr/rt/rates/2026/10-Oct/IR.20261002.csv"


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


def main() -> int:
    raw = fetch(URL)
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise SystemExit("CME archive returned an empty CSV")

    header = rows[0]
    zq_rows = []
    for row in rows[1:]:
        joined = "|".join(row).upper()
        if "ZQ" in joined or "FED FUND" in joined or "FEDERAL FUND" in joined:
            zq_rows.append(row)

    receipt = {
        "schema": "GMFQ_USD_CME_ZQ_ARCHIVE_PROBE_V1",
        "checked_at_utc": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "source": "CME Group official FTP/HTTP archive",
        "url": URL,
        "bytes": len(raw),
        "row_count": len(rows),
        "header": header,
        "zq_like_row_count": len(zq_rows),
        "zq_like_sample": zq_rows[:12],
        "status": "PASS" if zq_rows else "NO_ZQ_ROWS_FOUND",
        "runtime_mutated": False,
        "publication_performed": False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))

    if not zq_rows:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
