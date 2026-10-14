#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D_PATH = ROOT / "live_data" / "sections" / "D.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--replacement-out", required=True)
    args = ap.parse_args()

    candidate = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
    if candidate.get("schema") != "GMFQ_RISK_WTI_CANDIDATE_V1" or candidate.get("status") != "GREEN_OFFICIAL_SOURCE_CANDIDATE":
        raise SystemExit("candidate schema/status mismatch")
    src = candidate.get("source") or {}
    if src.get("publisher") != "U.S. Energy Information Administration" or src.get("series_id") != "RWTC":
        raise SystemExit("candidate source identity mismatch")
    if src.get("legacy_api_series_id") != "PET.RWTC.D" or src.get("fred_mirror_series_id") != "DCOILWTICO":
        raise SystemExit("candidate source equivalence metadata mismatch")
    observations = candidate.get("observations")
    if not isinstance(observations, list) or not observations:
        raise SystemExit("candidate observations missing")

    d = json.loads(D_PATH.read_text(encoding="utf-8"))
    risk = d.get("risk")
    if not isinstance(risk, dict) or not isinstance(risk.get("WTI"), dict):
        raise SystemExit("D.risk.WTI missing")
    wti = risk["WTI"]
    dates = wti.get("dates")
    values = wti.get("values")
    if not isinstance(dates, list) or not isinstance(values, list) or len(dates) != len(values) or not dates:
        raise SystemExit("invalid runtime WTI dates/values arrays")
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise SystemExit("runtime WTI dates are not strictly unique/monotonic")

    source = {x["date"]: float(x["value"]) for x in observations}
    if len(source) != len(observations):
        raise SystemExit("candidate has duplicate dates")

    # The current truncated runtime must overlap the official EIA source exactly.
    overlap = [day for day in dates if day in source]
    if not overlap:
        raise SystemExit("runtime WTI has no overlap with canonical source")
    anchor = overlap[-1]
    idx = dates.index(anchor)
    if not math.isclose(float(values[idx]), source[anchor], rel_tol=0, abs_tol=1e-9):
        raise SystemExit(f"WTI overlap anchor mismatch on {anchor}: runtime={values[idx]} source={source[anchor]}")

    source_dates = sorted(source)
    new_dates = source_dates
    new_values = [source[x] for x in source_dates]
    if len(new_dates) < 500 or new_dates[0] > "2016-01-31":
        raise SystemExit("canonical WTI replacement history invalid")

    before_other_risk = {k: v for k, v in risk.items() if k != "WTI"}
    risk["WTI"] = {
        "dates": new_dates,
        "values": new_values,
        "source": "U.S. Energy Information Administration",
        "source_url": "https://www.eia.gov/dnav/pet/hist/RWTCD.htm",
        "series_id": "RWTC",
        "legacy_api_series_id": "PET.RWTC.D",
        "fred_mirror_series_id": "DCOILWTICO",
        "frequency": "Daily",
        "last_date": new_dates[-1],
        "last_value": new_values[-1],
    }
    if {k: v for k, v in risk.items() if k != "WTI"} != before_other_risk:
        raise SystemExit("non-WTI risk data changed unexpectedly")

    out = Path(args.replacement_out)
    out.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    receipt = {
        "schema": "GMFQ_RISK_WTI_CONTROLLED_APPLY_RECEIPT_V1",
        "candidate_as_of": candidate["as_of"],
        "overlap_anchor_date": anchor,
        "old_observation_count": len(dates),
        "result_observation_count": len(new_dates),
        "result_first_date": new_dates[0],
        "result_last_date": new_dates[-1],
        "result_last_value": new_values[-1],
        "source": "U.S. EIA / RWTC / PET.RWTC.D",
        "fred_mirror_reference": "DCOILWTICO",
        "other_risk_keys_preserved": True,
        "publication_performed": False,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
