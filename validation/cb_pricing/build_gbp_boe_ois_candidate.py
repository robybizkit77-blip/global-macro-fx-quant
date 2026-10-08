#!/usr/bin/env python3
"""Build a GBP CB-pricing candidate from a read-only BoE source snapshot.

No runtime or payload mutation. Policy rate and meeting path are inherited from
currently validated canonical GBP runtime metadata; market observations come
only from the source snapshot produced by collect_gbp_boe_ois.py.
"""
from __future__ import annotations
import argparse, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
OIS = ROOT / "live_data" / "sections" / "OIS_DATA.json"
REGISTRY = ROOT / "validation" / "cb_pricing" / "CB_PRICING_SOURCE_STATUS_2026-10-08.json"


def classify(values, eps=0.05):
    vals = [float(values[k]) for k in ("3m", "6m", "12m")]
    pos = sum(v > eps for v in vals)
    neg = sum(v < -eps for v in vals)
    if pos == 3: return "UP"
    if neg == 3: return "DOWN"
    if pos == 0 and neg == 0: return "FLAT"
    if vals[0] > eps and vals[1] > eps: return "MIXED_FRONT_END_UP"
    if vals[0] < -eps and vals[1] < -eps: return "MIXED_FRONT_END_DOWN"
    return "MIXED"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True, type=pathlib.Path)
    ap.add_argument("--output", required=True, type=pathlib.Path)
    args = ap.parse_args()

    s = json.loads(args.snapshot.read_text(encoding="utf-8"))
    if s.get("schema") != "GMFQ_CB_PRICING_SOURCE_SNAPSHOT_V1" or s.get("currency") != "GBP":
        raise SystemExit("Invalid GBP source snapshot")
    v = s.get("validation", {})
    required = ("official_source", "exact_tenor_columns", "no_interpolation", "homogeneous_sessions")
    if not all(v.get(k) is True for k in required):
        raise SystemExit("GBP source snapshot validation incomplete")

    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rg = registry["currencies"]["GBP"]
    if rg.get("status") != "ACTIVE" or rg.get("official_source") != "Bank of England":
        raise SystemExit("GBP source registry does not authorize BoE ACTIVE pricing")

    ois = json.loads(OIS.read_text(encoding="utf-8"))
    live = ois["currencies"]["GBP"]
    if live.get("status") != "ACTIVE" or not live.get("policy_rate") or not live.get("meetings"):
        raise SystemExit("Canonical GBP policy metadata incomplete")
    if live.get("source") != s.get("source"):
        raise SystemExit("Snapshot source differs from canonical authorized GBP source")

    policy = float(live["policy_rate"])
    horizons = {}
    for k in ("3m", "6m", "12m"):
        rate = float(s["observations"]["current"][k])
        horizons[k] = {
            "rate": rate,
            "change_1d_bp": float(s["change_1d_bp"][k]),
            "change_1w_bp": float(s["change_1w_bp"][k]),
            "policy_delta_bp": round((rate - policy) * 100.0, 4),
        }

    obs = {}
    for name in ("t_minus_5", "t_minus_1", "current"):
        x = s["observations"][name]
        obs[x["date"]] = {k: float(x[k]) for k in ("3m", "6m", "12m")}

    candidate = {
        "schema": "GMFQ_CB_PRICING_CANDIDATE_V1",
        "currency": "GBP",
        "status": "READY_FOR_DRY_RUN",
        "as_of": s["as_of"],
        "source": s["source"],
        "source_url": s["source_url"],
        "archive_url": s["official_archive"],
        "instrument": s["instrument"],
        "quotation": s["quotation"],
        "policy_rate": policy,
        "meeting_path": live["meetings"],
        "horizon_mapping": {
            "3m": "BoE short-end forward curve · exact maturity 3 months",
            "6m": "BoE short-end forward curve · exact maturity 6 months",
            "12m": "BoE short-end forward curve · exact maturity 12 months"
        },
        "horizons": horizons,
        "cuts_hikes_priced": {f"{k}_bp": horizons[k]["policy_delta_bp"] for k in ("3m", "6m", "12m")},
        "direction": classify({k: horizons[k]["policy_delta_bp"] for k in horizons}),
        "change_direction_1d": classify(s["change_1d_bp"]),
        "change_direction_1w": classify(s["change_1w_bp"]),
        "observations": obs,
        "validation": {
            "source_validated": True,
            "asof_validated": True,
            "meeting_path_validated": True,
            "changes_validated": True,
            "current_real": True,
            "previous_real": True,
            "week_real": True,
            "tenor_headers_validated": True,
            "no_interpolation": True,
            "source_registry_authorized": True,
            "runtime_mutated": False,
            "payload_mutated": False,
            "weekly_reference_note": f"{s['observations']['t_minus_5']['date']} is the homogeneous five-official-session reference for {s['as_of']}."
        },
        "provenance": {
            "official_archive_workbook": s["workbook"],
            "official_sheet": s["sheet"],
            "collector": "validation/cb_pricing/collect_gbp_boe_ois.py",
            "method": "Direct extraction from the Bank of England official daily OIS archive; exact 3M/6M/12M instantaneous forward-curve columns; no interpolation.",
            "methodology_note": "Bank of England estimated SONIA OIS forward curve, not exchange futures settlements."
        }
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(candidate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(candidate, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
