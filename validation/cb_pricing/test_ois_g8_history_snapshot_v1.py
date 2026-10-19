#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ois_g8_history_snapshot_v1 import append_snapshots, CCYS


def row(c: str, official: bool, as_of: str, bump: float = 0.0) -> dict:
    base = 2.0 + (CCYS.index(c) * 0.1) + bump
    return {
        "operational_status": "GREEN_OFFICIAL" if official else "GREEN_ESTIMATED",
        "quality": "OFFICIAL_CERTIFIED" if official else "ESTIMATED_INFORMATIONAL",
        "confidence": "A" if official else "B",
        "official_status": "ACTIVE" if official else "WITHHELD",
        "input_mode": None if official else "LIVE_SECONDARY_OVERLAY",
        "method_id": None if official else "TEST_ESTIMATED_METHOD_V1",
        "as_of": as_of,
        "source": f"TEST SOURCE {c}",
        "policy_rate": base,
        "direction_vs_policy": "UP",
        "backtest_eligible_as_official": official,
        "horizons": {
            "3m": {"rate": base + 0.05, "policy_delta_bp": 5.0},
            "6m": {"rate": base + 0.10, "policy_delta_bp": 10.0},
            "12m": {"rate": base + 0.20, "policy_delta_bp": 20.0},
        },
    }


def view(as_of: str = "2026-10-17") -> dict:
    official = {"AUD", "CAD", "GBP", "JPY"}
    return {
        "status": "GREEN_8_OF_8",
        "currencies": {c: row(c, c in official, as_of) for c in CCYS},
    }


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "g8.jsonl"
        v = view()
        r1 = append_snapshots(v, "2026-10-17T08:15:00Z", p)
        assert r1["appended"] == 8, r1
        assert r1["currencies"] == list(CCYS), r1
        lines = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
        assert len(lines) == 8
        assert {x["currency"] for x in lines} == set(CCYS)
        assert all(x["method_id"] for x in lines)
        assert all(x["source_as_of"] == "2026-10-17" for x in lines)

        r2 = append_snapshots(v, "2026-10-17T09:00:00Z", p)
        assert r2["appended"] == 0, r2

        v2 = view()
        v2["currencies"]["EUR"] = row("EUR", False, "2026-10-18", 0.01)
        r3 = append_snapshots(v2, "2026-10-18T08:15:00Z", p)
        assert r3["appended"] == 1 and r3["currencies"] == ["EUR"], r3

        v3 = view()
        v3["currencies"]["EUR"] = row("EUR", False, "2026-10-18", 0.01)
        v3["currencies"]["EUR"]["method_id"] = "TEST_ESTIMATED_METHOD_V2"
        r4 = append_snapshots(v3, "2026-10-18T09:15:00Z", p)
        assert r4["appended"] == 1 and r4["currencies"] == ["EUR"], r4

        # A genuine 5/8 session must never discard good official/estimated
        # history or leave yesterday's green curve as the latest USD/CHF/NZD.
        partial = view("2026-10-19")
        for c in ("USD", "CHF", "NZD"):
            last = partial["currencies"][c]
            last["operational_status"] = "WITHHELD"
            last["official_status"] = "WITHHELD"
            last["backtest_eligible_as_official"] = False
            last["withheld_reason"] = "STALE_OR_INCOMPLETE_PRICING"
            last["horizons"] = {h: {"rate": None, "policy_delta_bp": None}
                                for h in ("3m", "6m", "12m")}
        r5 = append_snapshots(partial, "2026-10-19T08:15:00Z", p)
        assert r5["appended"] == 8, r5
        history = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
        latest = {x["currency"]: x for x in history}
        assert set(latest) == set(CCYS)
        assert sum(x["operational_status"] == "WITHHELD" for x in latest.values()) == 3
        for c in ("USD", "CHF", "NZD"):
            x = latest[c]
            assert x["source_as_of"] is None
            assert x["last_input_as_of"] == "2026-10-19"
            assert x["quality"] == "UNAVAILABLE"
            assert x["backtest_eligible_as_official"] is False
            assert x["policy_rate"] is None
            assert all(v["rate"] is None and v["policy_delta_bp"] is None for v in x["horizons"].values())
        assert latest["EUR"]["operational_status"] == "GREEN_ESTIMATED"

        # A replay of the same WITHHELD state is a no-op: append on semantic change.
        r6 = append_snapshots(partial, "2026-10-19T10:00:00Z", p)
        assert r6["appended"] == 0, r6
        # Bad incoming WITHHELD record containing a non-null quote must FAIL CLOSED.
        bad = json.loads(json.dumps(partial))
        bad["currencies"]["CHF"]["horizons"]["3m"]["rate"] = 0.05
        try:
            append_snapshots(bad, "2026-10-19T12:00:00Z", p)
            assert False, "WITHHELD rate leak accepted"
        except SystemExit as exc:
            assert "null pricing" in str(exc), exc

        # When a currency re-enters GREEN, record restoration as a new regime.
        restored = json.loads(json.dumps(partial))
        restored["currencies"]["CHF"] = row("CHF", False, "2026-10-20", 0.02)
        r7 = append_snapshots(restored, "2026-10-20T08:15:00Z", p)
        assert r7["currencies"] == ["CHF"], r7

        print("OIS_G8_HISTORY_SNAPSHOT_V1_PASS")


if __name__ == "__main__":
    main()
