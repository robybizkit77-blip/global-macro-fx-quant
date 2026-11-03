#!/usr/bin/env python3
"""Fail-closed audit of the RBNZ B2 government-bond benchmark transition.

The B2 quoted benchmark is a rolling security, NOT a constant-maturity
instrument or an OIS repricing measurement. Research-only: no live writes.
"""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "validation/research/CHF_NZD_SOURCE_EVIDENCE_2026-11-03.json"


def audit(evidence: dict) -> dict:
    assert evidence["governance"]["updates_live_data"] is False
    assert evidence["governance"]["modifies_28_pair_structural_baseline"] is False
    nzd = evidence["currencies"]["NZD"]
    assert nzd["canonical_rate_update_approved"] is False
    assert nzd["review_status"].endswith("PENDING_INDEPENDENT_XLSX_RECONCILIATION")
    rows = nzd["observations"]
    assert len(rows) >= 3
    dates = [dt.date.fromisoformat(r["date"]) for r in rows]
    assert dates == sorted(set(dates))
    for row in rows:
        assert all(type(row[k]) in (int, float) for k in ("y2_pct", "y10_pct"))
    roll = nzd["benchmark_transition"]
    boundary = dt.date.fromisoformat(roll["date"])
    before = [r for r in rows if dt.date.fromisoformat(r["date"]) < boundary]
    after = [r for r in rows if dt.date.fromisoformat(r["date"]) >= boundary]
    assert before and after
    prior, current = before[-1], after[0]
    assert prior["benchmark_2y"] == roll["old_bond"]
    assert current["benchmark_2y"] == roll["new_bond"]
    jump = round((current["y2_pct"] - prior["y2_pct"]) * 100)
    assert jump == roll["naive_two_year_jump_bp"]
    assert roll["old_bond"] != roll["new_bond"]
    # Even if quoted rates both exist, do not estimate the economic repricing
    # without matched-ISIN prices or a defensible constant-maturity adjustment.
    return {
        "status": "PASS_RESEARCH_ONLY",
        "roll_boundary": roll["date"],
        "quoted_2y_difference_bp": jump,
        "comparable_same_instrument_change_bp": None,
        "eligible_for_rate_change_signal": False,
        "eligible_for_pair_repricing": False,
        "requires_independent_xlsx_reconciliation": True,
        "writes_live_data": False,
    }


if __name__ == "__main__":
    print(json.dumps(audit(json.loads(EVIDENCE.read_text())), indent=2))
