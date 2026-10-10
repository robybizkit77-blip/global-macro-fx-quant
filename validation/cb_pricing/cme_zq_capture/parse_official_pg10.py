#!/usr/bin/env python3
"""Parse CME PG10 ZQ PDF bytes into an immutable, source-linked strip snapshot."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

source = "https://www.cmegroup.com/daily_bulletin/current/Section10_Interest_Rate_Futures_Continued.pdf"
pdf = Path(sys.argv[1])
raw = pdf.read_bytes()
if not raw.startswith(b"%PDF") or len(raw) < 5000:
    sys.exit("WITHHELD: missing or invalid CME PDF")
sha = hashlib.sha256(raw).hexdigest()
text = subprocess.check_output(["pdftotext", "-f", "1", "-l", "1", "-layout", str(pdf), "-"], text=True)
date_match = re.search(r"(?:Mon|Tue|Wed|Thu|Fri),\s+([A-Z][a-z]{2})\s+(\d{1,2}),\s+(\d{4})", text)
bulletin = re.search(r"BULLETIN\s*#\s*(\d+)", text)
if not date_match or not bulletin:
    sys.exit("WITHHELD: CME header incomplete")
trade_date = dt.datetime.strptime(" ".join(date_match.groups()), "%b %d %Y").date()
ct = dt.datetime.now(ZoneInfo("America/Chicago"))
if trade_date > ct.date() or (ct.date() - trade_date).days > 5:
    sys.exit("WITHHELD: stale or future CME bulletin")
head = text[:2200].upper()
statuses = [s for s in ("PRELIMINARY", "FINAL") if re.search(r"\b" + s + r"\b", head)]
if len(statuses) != 1:
    sys.exit("WITHHELD: CME publication status ambiguous")
lines = text.splitlines()
starts = [i for i, x in enumerate(lines) if re.fullmatch(r"\s*30D FED FD FUT\s*", x)]
if len(starts) != 1:
    sys.exit("WITHHELD: ZQ section missing or duplicated")
start = starts[0]
ends = [i for i in range(start + 1, min(len(lines), start + 80)) if "TOTAL 30D FED FD FUT" in lines[i]]
if len(ends) != 1:
    sys.exit("WITHHELD: ZQ section terminator missing")
end = ends[0]
pattern = re.compile(r"\b(\d{2}\.\d{3,4})\s*\(\s*\d+(?:\.\d+)?\s*\)\s*(UNCH|[+-]\s*\d+(?:\.\d+)?)\b")
rows = []
for line in lines[start + 1:end]:
    m = re.match(r"^\s*((?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\d{2})\s+", line)
    if not m:
        continue
    p = pattern.search(line)
    if not p:
        sys.exit("WITHHELD: unparseable ZQ settlement row")
    price = float(p.group(1))
    if not 80 < price < 100:
        sys.exit("WITHHELD: invalid ZQ settlement")
    rows.append({"contract": m.group(1), "settlement_price": price,
                 "implied_average_effr_pct": round(100-price, 4),
                 "official_price_change": 0 if p.group(2) == "UNCH" else float(p.group(2).replace(" ", "")),
                 "official_row": line.strip()})
by_contract = {r["contract"]: r for r in rows}
if len(rows) < 12 or len(by_contract) != len(rows):
    sys.exit("WITHHELD: incomplete or duplicate ZQ strip")
reference = {"3m_reference": "DEC26", "6m_reference": "MAR27", "12m_reference": "SEP27"}
if any(x not in by_contract for x in reference.values()):
    sys.exit("WITHHELD: required quarterly reference contract missing")
block = "\n".join(lines[start:end+1]) + "\n"
output = {
    "schema_version": "GMFQ_CME_ZQ_FULL_STRIP_V1", "currency": "USD",
    "instrument": "CBOT 30-Day Federal Funds Futures (ZQ)",
    "source": "CME Group official Daily Information Bulletin PG10", "source_url": source,
    "source_pdf_sha256": sha, "source_pdf_bytes": len(raw),
    "source_block_sha256": hashlib.sha256(block.encode()).hexdigest(),
    "trade_date": str(trade_date), "bulletin_number": int(bulletin.group(1)),
    "publication_status": statuses[0], "captured_ct": ct.isoformat(),
    "quotation": "100 minus monthly average effective federal funds rate",
    "contracts": rows, "reference_quarterly_buckets_not_exact_ois_tenors": reference,
    "validation": {"official_pdf": True, "full_monthly_strip": True, "no_proxy": True,
                   "no_secondary_prices": True, "ois_tenors_validated": False},
    "promotion": {"usd_ois": "WITHHELD", "main_mutated": False, "gh_pages_mutated": False}
}
outdir = Path(__file__).resolve().parent / "daily"
outdir.mkdir(exist_ok=True)
stem = f"ZQ_STRIP_{trade_date}_{statuses[0]}_{sha[:12]}"
(outdir / (stem + ".pdf")).write_bytes(raw)
json_path = outdir / (stem + ".json")
if not json_path.exists():
    json_path.write_text(json.dumps(output, indent=2) + "\n")
print(json.dumps({"trade_date": str(trade_date), "status": statuses[0],
                  "contracts": len(rows), "sha256": sha, "snapshot": str(json_path),
                  "usd_ois": "WITHHELD"}, indent=2))
