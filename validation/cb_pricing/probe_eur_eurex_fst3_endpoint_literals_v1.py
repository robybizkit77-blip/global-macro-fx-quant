#!/usr/bin/env python3
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

JS = "https://www.eurex.com/resource/themes/eurex-facelift/js/prices-statistics-3466696-65.js"
OUT = Path("validation/cb_pricing/eur_eurex_fst3_endpoint_literals_probe_receipt_v1.json")


def get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 GMFQ-CB-Pricing-Probe/1.0", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def main() -> int:
    text = get(JS)
    literals = []
    for m in re.finditer(r'(["\'])(.{1,240}?)\1', text):
        s = m.group(2)
        sl = s.lower()
        if any(k in sl for k in ("futurestat", "statistic", "servlet", "price", "quote", "contract", "factset", "mdg", "busdate")):
            if s not in literals:
                literals.append(s)
    contexts = []
    for key in ("FutureStatistic", "busDate", "dSettle", "hostUrl", "fetch(", "XMLHttpRequest", "servlet"):
        start = 0
        count = 0
        while count < 8:
            idx = text.find(key, start)
            if idx < 0:
                break
            contexts.append({"key": key, "sample": re.sub(r"\s+", " ", text[max(0, idx-900):idx+2400])[:3300]})
            start = idx + len(key)
            count += 1
    receipt = {
        "schema": "GMFQ_EUR_EUREX_FST3_ENDPOINT_LITERALS_PROBE_V1",
        "checked_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "js": JS,
        "bytes": len(text.encode("utf-8")),
        "candidate_literals": literals[:500],
        "contexts": contexts[:80],
        "status": "PASS",
        "runtime_mutated": False,
        "publication_performed": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "candidate_literal_count": len(literals), "context_count": len(contexts)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
