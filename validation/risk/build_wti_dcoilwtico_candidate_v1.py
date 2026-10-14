#!/usr/bin/env python3
from __future__ import annotations
import csv, io, json, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "live_data/sections/D.json"
OUT = ROOT / "validation/risk/WTI_DCOILWTICO_CANDIDATE_V1.json"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILWTICO&cosd=2016-01-01"


def fetch_wti():
    req = urllib.request.Request(FRED_URL, headers={"User-Agent": "Mozilla/5.0 GMFQ-WTI/1.0"})
    raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8-sig")
    rdr = csv.DictReader(io.StringIO(raw))
    rows = []
    for rr in rdr:
        ds = (rr.get("observation_date") or rr.get("DATE") or "").strip()
        vs = (rr.get("DCOILWTICO") or "").strip()
        if not ds or vs in ("", ".", "NA", "N/A"):
            continue
        try:
            rows.append((ds, float(vs)))
        except ValueError:
            continue
    rows.sort(key=lambda x: x[0])
    if len(rows) < 500:
        raise SystemExit(f"WTI source history too short: {len(rows)}")
    if rows[0][0] > "2016-01-31":
        raise SystemExit(f"WTI source start too late: {rows[0][0]}")
    if rows[-1][0] < "2026-10-01":
        raise SystemExit(f"WTI source unexpectedly stale: {rows[-1][0]}")
    return rows


def locate_wti(root):
    # Canonical current shape is D.risk.WTI. Fail closed if it drifts.
    if not isinstance(root, dict) or not isinstance(root.get("risk"), dict):
        raise SystemExit("D.risk missing or not an object")
    risk = root["risk"]
    if "WTI" not in risk or not isinstance(risk["WTI"], dict):
        raise SystemExit("D.risk.WTI missing or not an object")
    return risk


def main():
    current = json.loads(SOURCE.read_text(encoding="utf-8"))
    risk = locate_wti(current)
    old = risk["WTI"]
    rows = fetch_wti()
    replacement = {
        "dates": [d for d, _ in rows],
        "values": [v for _, v in rows],
        "source": "U.S. EIA via FRED",
        "series_id": "DCOILWTICO",
        "frequency": "Daily",
        "last_date": rows[-1][0],
        "last_value": rows[-1][1],
    }
    risk["WTI"] = replacement
    OUT.write_text(json.dumps(current, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
    receipt = {
        "schema": "GMFQ_WTI_DCOILWTICO_CANDIDATE_RECEIPT_V1",
        "status": "PASS",
        "source": "U.S. EIA via FRED",
        "series_id": "DCOILWTICO",
        "history_rows": len(rows),
        "first_date": rows[0][0],
        "last_date": rows[-1][0],
        "last_value": rows[-1][1],
        "old_keys": sorted(old.keys()),
        "candidate_path": str(OUT.relative_to(ROOT)),
        "publication_performed": False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
