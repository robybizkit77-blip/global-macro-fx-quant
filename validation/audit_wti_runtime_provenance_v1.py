#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import csv
import gzip
import io
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D_PATH = ROOT / "live_data" / "sections" / "D.json"


def decode_snapshot(path: Path) -> list[dict]:
    raw = base64.b64decode(path.read_text(encoding="utf-8").strip())
    text = gzip.decompress(raw).decode("utf-8-sig")
    rows = []
    for rr in csv.DictReader(io.StringIO(text)):
        ds = (rr.get("observation_date") or rr.get("DATE") or "").strip()
        vs = (rr.get("DCOILWTICO") or "").strip()
        if not ds or vs in ("", ".", "NA", "N/A"):
            continue
        try:
            rows.append({"date": ds, "value": float(vs)})
        except ValueError:
            continue
    rows.sort(key=lambda x: x["date"])
    return rows


def as_map(rows: list[dict]) -> dict[str, float]:
    return {str(x["date"]): float(x["value"]) for x in rows}


def compare(a: dict[str, float], b: dict[str, float]) -> dict:
    shared = sorted(set(a) & set(b))
    exact = []
    mismatches = []
    for d in shared:
        if math.isclose(a[d], b[d], rel_tol=0, abs_tol=1e-9):
            exact.append(d)
        else:
            mismatches.append({"date": d, "a": a[d], "b": b[d], "delta": round(a[d]-b[d], 10)})
    return {
        "shared_count": len(shared),
        "exact_count": len(exact),
        "mismatch_count": len(mismatches),
        "exact_ratio": (len(exact) / len(shared)) if shared else None,
        "first_mismatch": mismatches[0] if mismatches else None,
        "last_mismatch": mismatches[-1] if mismatches else None,
        "last_10_mismatches": mismatches[-10:],
    }


def dates_for_value(m: dict[str, float], target: float, tol: float = 1e-9) -> list[str]:
    return [d for d, v in sorted(m.items()) if math.isclose(v, target, rel_tol=0, abs_tol=tol)]


def summary(m: dict[str, float]) -> dict:
    ds = sorted(m)
    return {
        "count": len(ds),
        "first_date": ds[0] if ds else None,
        "last_date": ds[-1] if ds else None,
        "last_value": m[ds[-1]] if ds else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--eia-candidate", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    d = json.loads(D_PATH.read_text(encoding="utf-8"))
    wti = d.get("risk", {}).get("WTI")
    if not isinstance(wti, dict):
        raise SystemExit("D.risk.WTI missing")
    dates = wti.get("dates") or []
    values = wti.get("values") or []
    if len(dates) != len(values) or not dates:
        raise SystemExit("runtime WTI dates/values invalid")

    runtime_rows = [{"date": str(ds), "value": float(v)} for ds, v in zip(dates, values)]
    snapshot_rows = decode_snapshot(Path(args.snapshot))
    eia = json.loads(Path(args.eia_candidate).read_text(encoding="utf-8"))
    eia_rows = eia.get("observations") or []

    runtime = as_map(runtime_rows)
    snapshot = as_map(snapshot_rows)
    official = as_map(eia_rows)

    target = 92.41
    receipt = {
        "schema": "GMFQ_WTI_RUNTIME_PROVENANCE_FORENSIC_V1",
        "status": "FORENSIC_READ_ONLY",
        "runtime_metadata": {k: wti.get(k) for k in ("source", "series_id", "frequency", "last_date", "last_value") if k in wti},
        "runtime": summary(runtime),
        "historical_snapshot_commit": "d2c701abfc21935979a7b30e3e1fb9555e2e8d08",
        "historical_snapshot_declared_series": "DCOILWTICO",
        "snapshot": summary(snapshot),
        "official_eia": summary(official),
        "runtime_vs_snapshot": compare(runtime, snapshot),
        "runtime_vs_official_eia": compare(runtime, official),
        "snapshot_vs_official_eia": compare(snapshot, official),
        "target_value_92_41": {
            "runtime_dates": dates_for_value(runtime, target),
            "snapshot_dates": dates_for_value(snapshot, target),
            "official_eia_dates": dates_for_value(official, target),
        },
        "focus_dates": {},
        "mutation_performed": False,
        "publication_performed": False,
    }
    for ds in ("2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25"):
        receipt["focus_dates"][ds] = {
            "runtime": runtime.get(ds),
            "snapshot": snapshot.get(ds),
            "official_eia": official.get(ds),
        }

    # Classification is intentionally conservative: it explains provenance, never authorizes migration.
    rvs = receipt["runtime_vs_snapshot"]
    sve = receipt["snapshot_vs_official_eia"]
    if rvs["shared_count"] and rvs["mismatch_count"] == 0:
        if sve["shared_count"] and sve["mismatch_count"] == 0:
            classification = "RUNTIME_MATCHES_SNAPSHOT_AND_SNAPSHOT_MATCHES_EIA"
        else:
            classification = "RUNTIME_MATCHES_HISTORICAL_SNAPSHOT_BUT_SNAPSHOT_DIVERGES_FROM_CURRENT_OFFICIAL_EIA"
    elif receipt["runtime_vs_official_eia"]["shared_count"] and receipt["runtime_vs_official_eia"]["mismatch_count"] == 0:
        classification = "RUNTIME_MATCHES_OFFICIAL_EIA_NOT_HISTORICAL_SNAPSHOT"
    else:
        classification = "RUNTIME_PROVENANCE_NOT_RECONCILED"
    receipt["classification"] = classification

    Path(args.out).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
