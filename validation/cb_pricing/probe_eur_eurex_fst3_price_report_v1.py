#!/usr/bin/env python3
import io
import json
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

URL = "https://www.eurex.com/resource/blob/5425422/8c6da155ce7181eb4468ec491fd7e358/data/90rptcb002publi20260810.zip"
OUT = Path("validation/cb_pricing/eur_eurex_fst3_price_report_probe_receipt_v1.json")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 GMFQ-CB-Pricing-Probe/1.0",
            "Accept": "application/zip,application/octet-stream,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def emit(receipt: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


def main() -> int:
    base = {
        "schema": "GMFQ_EUR_EUREX_FST3_PRICE_REPORT_PROBE_V1",
        "checked_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": "Eurex official Product and Price Report",
        "url": URL,
        "runtime_mutated": False,
        "publication_performed": False,
    }
    try:
        raw = fetch(URL)
        zf = zipfile.ZipFile(io.BytesIO(raw))
        names = zf.namelist()
        hits = []
        samples = []
        for name in names:
            data = zf.read(name)
            text = data.decode("utf-8", errors="replace")
            upper = text.upper()
            if "FST3" in upper or "EURO STR" in upper or "€STR" in text:
                hits.append(name)
                lines = [line for line in text.splitlines() if "FST3" in line.upper() or "EURO STR" in line.upper()]
                samples.extend({"file": name, "line": line[:500]} for line in lines[:20])
        emit({
            **base,
            "status": "PASS" if hits else "NO_FST3_FOUND",
            "zip_bytes": len(raw),
            "members": names,
            "fst3_members": hits,
            "fst3_samples": samples[:40],
        })
    except urllib.error.HTTPError as exc:
        emit({**base, "status": "HTTP_ERROR", "http_status": exc.code, "error": str(exc)})
    except Exception as exc:
        emit({**base, "status": "ERROR", "error_type": type(exc).__name__, "error": str(exc)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
