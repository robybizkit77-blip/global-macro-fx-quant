"""Adversarial tests: forward-only HY filter is research and never a live signal."""
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from validation.quant import hy_fx_risk_forward_v1 as m


def fx_row(day, aud, jpy=160, nzd=2, chf=.94, usd=1.10):
    return {"Date": day, "AUD": aud, "JPY": jpy, "NZD": nzd,
            "CHF": chf, "USD": usd}


class HyForwardTest(unittest.TestCase):
    def test_frozen_contract(self):
        p, fingerprint = m.check_policy()
        self.assertEqual(p["earliest_eligible_capture_rome"], "2026-11-10")
        self.assertEqual(len(fingerprint), 64)
        self.assertFalse(p["eligible_for_live_engine"])

    def test_actual_clock_and_weekend_gate(self):
        p, _ = m.check_policy()
        self.assertTrue(m.can_capture(datetime(2026, 11, 10, 19, 45, tzinfo=timezone.utc), p))
        self.assertTrue(m.can_capture(datetime(2026, 7, 10, 18, 45, tzinfo=timezone.utc), p) is False)
        self.assertTrue(m.can_capture(datetime(2027, 7, 12, 18, 45, tzinfo=timezone.utc), p))
        self.assertFalse(m.can_capture(datetime(2026, 11, 9, 19, 45, tzinfo=timezone.utc), p))
        self.assertFalse(m.can_capture(datetime(2026, 11, 10, 18, 45, tzinfo=timezone.utc), p))
        self.assertFalse(m.can_capture(datetime(2026, 11, 14, 19, 45, tzinfo=timezone.utc), p))

    def test_hy_csv_date_parsing(self):
        s = "observation_date,BAMLH0A0HYM2\n2026-11-02,3.3\n2026-11-03,.\n2026-11-04,3.4\n"
        self.assertEqual(m.fred_csv(s, "BAMLH0A0HYM2"),
                         [("2026-11-02", 3.3), ("2026-11-04", 3.4)])

    def test_snapshot_no_backfill_and_lagged_hy(self):
        now = datetime(2026, 11, 10, 19, 45, tzinfo=timezone.utc)
        fx = [fx_row("2026-10-%02d" % d, 1.5) for d in range(10, 31)]
        fx[-1] = fx_row("2026-11-10", 1.3)
        hy = [
            ("2026-10-23", 3.0), ("2026-10-26", 3.0),
            ("2026-10-27", 3.0), ("2026-10-28", 3.0),
            ("2026-10-29", 3.0), ("2026-10-30", 3.0),
            ("2026-11-02", 3.10), ("2026-11-03", 3.50),
            ("2026-11-09", 8.0), ("2026-11-10", 100.0),
        ]
        s = m.build_snapshot(now, "p" * 64, fx, hy, [("2026-11-09", 22)])
        self.assertEqual(s["status"], "ELIGIBLE")
        self.assertEqual(s["source"]["hy_observation_date"], "2026-11-03")
        self.assertEqual(s["source"]["hy_delta_5_bp"], 50.0)
        self.assertEqual(s["pairs"]["AUDJPY"]["momentum20_long"], 1)
        self.assertEqual(s["pairs"]["AUDJPY"]["hy_filtered_long"], 0)
        self.assertEqual(s["source"]["vix_observation_date"], "2026-11-09")

    def test_abstain_without_exact_today_fx(self):
        now = datetime(2026, 11, 10, 19, 45, tzinfo=timezone.utc)
        fx = [fx_row("2026-11-09", 1.5)] * 21
        s = m.build_snapshot(now, "s" * 64, fx, [], [])
        self.assertEqual(s["status"], "ABSTAIN")
        self.assertEqual(s["reason"], "NO_SAME_DAY_ECB_FIXING")

    def test_outcomes_only_after_two_future_fixings_and_no_duplication(self):
        with TemporaryDirectory() as td:
            target = Path(td) / "outcomes.jsonl"
            fx = [fx_row("2026-11-10", 1.4), fx_row("2026-11-11", 1.3),
                  fx_row("2026-11-12", 1.2)]
            snap = {"status": "ELIGIBLE", "capture_rome_date": "2026-11-10",
                    "record_sha256": "a" * 64}
            with patch.object(m, "OUTCOMES", target):
                m.mature_outcomes(
                    datetime(2026, 11, 11, 19, 45, tzinfo=timezone.utc),
                    fx, [snap], [])
                self.assertFalse(target.exists())
                now = datetime(2026, 11, 12, 19, 45, tzinfo=timezone.utc)
                m.mature_outcomes(now, fx, [snap], [])
                self.assertEqual(len(m.read_jsonl(target)), 1)
                self.assertEqual(m.read_jsonl(target)[0]["entry_ecb_fixing_date"], "2026-11-11")
                m.mature_outcomes(now, fx, [snap], m.read_jsonl(target))
                self.assertEqual(len(m.read_jsonl(target)), 1)


if __name__ == "__main__":
    unittest.main()
