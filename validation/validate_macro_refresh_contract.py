#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LIVE_SERIES = ROOT / "live_data" / "sections" / "MACRO_SERIES.json"
LIVE_HEAT = ROOT / "live_data" / "sections" / "MACRO_THERMOMETER_DATA.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def changed_currency_series(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for ccy in sorted(set(before) | set(after)):
        if before.get(ccy) != after.get(ccy):
            out.append(ccy)
    return out


def changed_heatmap_dimensions(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    out: list[str] = []
    bcur = before.get("currencies", {})
    acur = after.get("currencies", {})
    for ccy in sorted(set(bcur) | set(acur)):
        brow = bcur.get(ccy, {})
        arow = acur.get(ccy, {})
        for dim in ("inflation", "labour"):
            if brow.get(dim) != arow.get(dim):
                out.append(f"{ccy}.{dim}")
        if brow.get("as_of_detail") != arow.get("as_of_detail"):
            out.append(f"{ccy}.as_of_detail")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate a read-only macro refresh candidate against live data")
    ap.add_argument("--candidate-dir", required=True)
    ap.add_argument("--expected-currency", required=True)
    ap.add_argument("--expected-dimension", choices=("inflation", "labour"), required=True)
    args = ap.parse_args()

    cdir = Path(args.candidate_dir)
    cand_series_path = cdir / "MACRO_SERIES.json"
    cand_heat_path = cdir / "MACRO_THERMOMETER_DATA.json"
    summary_path = cdir / "summary.json"
    for p in (cand_series_path, cand_heat_path, summary_path):
        if not p.exists():
            raise SystemExit(f"missing candidate artifact: {p}")

    before_series = load(LIVE_SERIES)
    before_heat = load(LIVE_HEAT)
    cand_series = load(cand_series_path)
    cand_heat = load(cand_heat_path)
    summary = load(summary_path)

    expected_ccy = args.expected_currency
    expected_dim = args.expected_dimension
    series_changes = changed_currency_series(before_series, cand_series)
    heat_changes = changed_heatmap_dimensions(before_heat, cand_heat)

    if summary.get("status") != "PASS" or summary.get("mode") != "CANDIDATE_ONLY":
        raise SystemExit("candidate summary contract mismatch")
    if summary.get("live_data_modified") is not False:
        raise SystemExit("candidate claims live data modification")
    if summary.get("currency") != expected_ccy or summary.get("dimension") != expected_dim:
        raise SystemExit("candidate summary target mismatch")
    if series_changes != [expected_ccy]:
        raise SystemExit(f"unexpected MACRO_SERIES scope: {series_changes}")

    allowed_heat = {f"{expected_ccy}.{expected_dim}", f"{expected_ccy}.as_of_detail"}
    if not heat_changes or any(x not in allowed_heat for x in heat_changes):
        raise SystemExit(f"unexpected heatmap scope: {heat_changes}")
    if f"{expected_ccy}.{expected_dim}" not in heat_changes:
        raise SystemExit("expected heatmap dimension did not change")

    result = {
        "status": "PASS",
        "contract": "CANONICAL_MACRO_REFRESH_V1",
        "target": {"currency": expected_ccy, "dimension": expected_dim},
        "series_changes": series_changes,
        "heatmap_changes": heat_changes,
        "live_hashes": {
            "MACRO_SERIES": sha256(LIVE_SERIES),
            "MACRO_THERMOMETER_DATA": sha256(LIVE_HEAT),
        },
        "candidate_hashes": {
            "MACRO_SERIES": sha256(cand_series_path),
            "MACRO_THERMOMETER_DATA": sha256(cand_heat_path),
        },
        "promotion_allowed": True,
        "promotion_performed": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
