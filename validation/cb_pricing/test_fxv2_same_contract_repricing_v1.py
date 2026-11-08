#!/usr/bin/env python3
"""Adversarial validation of research-only same-listed-futures 1D/1W moves."""
from __future__ import annotations

import copy
import json
import unittest
from datetime import date
from pathlib import Path

from build_fxv2_same_contract_repricing_v1 import TARGET, build, SCHEMA
from ois_same_contract_history_v1 import HISTORY, SOURCE, load_history
from reconcile_ois_secondary_conflicts_v1 import CONFLICTS, read_conflicts


class SameContractResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.feed = json.loads(SOURCE.read_text(encoding="utf-8"))
        cls.archive = load_history(HISTORY)
        cls.conflicts = read_conflicts(CONFLICTS)
        cls.result = build(cls.feed, cls.archive, cls.conflicts)

    def test_strict_source_and_live_asset_parity(self):
        a = self.result
        self.assertEqual(a["schema"], SCHEMA)
        self.assertEqual(set(a["currencies"]), {"USD", "EUR", "CHF"})
        self.assertEqual(a["summary"]["horizons"], 9)
        self.assertEqual(a["summary"]["generated_ois_signals"], 0)
        self.assertEqual(a["summary"]["generated_fx_signals"], 0)
        self.assertFalse(a["eligible_for_fx_engine"])
        self.assertFalse(a["eligible_for_policy_repricing_signals"])
        self.assertTrue(a["unknown_is_null_not_zero"])
        self.assertEqual(json.loads(TARGET.read_text(encoding="utf-8")), a)

    def test_no_fake_source_update_from_rechecking_same_market_bars(self):
        refreshed = copy.deepcopy(self.feed)
        # A later collector run with the exact same dated bars must NOT
        # manufacture a newer observation or republish a timestamp-only file.
        from datetime import datetime, timedelta, timezone
        previous = datetime.fromisoformat(
            self.feed["generated_at_utc"].replace("Z", "+00:00"))
        refreshed["generated_at_utc"] = (
            previous + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        result = build(refreshed, self.archive, self.conflicts)
        self.assertEqual(result, self.result)
        self.assertNotEqual(result["source_capture_at_utc"],
                            refreshed["generated_at_utc"])

    def test_exact_previous_weekday_and_seven_day_identity(self):
        for ccy, tenors in self.result["currencies"].items():
            for tenor, row in tenors.items():
                for key in ("one_day", "one_week"):
                    p = row[key]
                    if not p:
                        self.assertIsNone(row["change_1d_bp" if key == "one_day" else "change_1w_bp"])
                        continue
                    self.assertTrue(p["same_contract"])
                    self.assertTrue(p["same_expiration"])
                    self.assertTrue(p["not_policy_rate"])
                    diff = (date.fromisoformat(p["to_date"]) -
                            date.fromisoformat(p["from_date"])).days
                    if key == "one_week":
                        self.assertEqual(diff, 7, (ccy, tenor, p))
                    else:
                        self.assertIn(diff, (1, 3), (ccy, tenor, p))
                    self.assertAlmostEqual(p["change_bp"],
                        (p["current_rate_pct"] - p["reference_rate_pct"]) * 100, places=3)

    def test_live_research_move_not_ois_and_not_cross_contract_roll(self):
        # These values are read dynamically from signed daily bars; never
        # fix a *future* daily market print as a permanent test expectation.
        for code, tenor in (("USD", "12m"), ("EUR", "12m"), ("CHF", "6m")):
            row = self.result["currencies"][code][tenor]
            self.assertIs(row["official_ois"], False)
            self.assertIs(row["policy_repricing_signal"], False)
            self.assertIsNone(row["fx_signal"])
            if row["one_day"]:
                self.assertNotEqual(row["one_day"]["from_date"], row["one_day"]["to_date"])

    def clean_signed_contract(self, require_one_day=False):
        # The latest USD 12M can legitimately be quarantined. Select an
        # *actually verified* current contract rather than invent a move.
        # Every negative test still exercises the real signed archive.
        choices = [
            (ccy, tenor, row)
            for ccy, horizons in self.result["currencies"].items()
            for tenor, row in horizons.items()
            if row["status"] in (
                "VERIFIED_CONTRACT_NO_MATCHED_REFERENCE",
                "VERIFIED_SAME_CONTRACT_PRICE_CHANGE",
            ) and (not require_one_day or row["one_day"] is not None)
        ]
        self.assertTrue(choices, "no uncontested signed contract available for adversarial check")
        return choices[0]

    def test_missing_previous_session_is_null_not_older_rate(self):
        ccy, tenor, source = self.clean_signed_contract(require_one_day=True)
        data = copy.deepcopy(self.archive)
        reference = source["one_day"]["from_date"]
        data = [r for r in data if not (r["currency"] == ccy and
                r["contract"] == source["contract"] and
                r["observation_date"] == reference)]
        result = build(self.feed, data, self.conflicts)
        row = result["currencies"][ccy][tenor]
        self.assertIsNone(row["one_day"])
        self.assertIsNone(row["change_1d_bp"])

    def test_missing_current_archive_never_becomes_verified(self):
        ccy, tenor, source = self.clean_signed_contract()
        data = copy.deepcopy(self.archive)
        data = [r for r in data if not (r["currency"] == ccy and
                r["contract"] == source["contract"] and
                r["observation_date"] == source["as_of"])]
        result = build(self.feed, data, self.conflicts)
        row = result["currencies"][ccy][tenor]
        self.assertEqual(row["status"], "CURRENT_NOT_YET_ARCHIVED")
        self.assertIsNone(row["one_day"])
        self.assertIsNone(row["one_week"])

    def test_current_source_mutation_is_rejected(self):
        ccy, tenor, _ = self.clean_signed_contract()
        fed = copy.deepcopy(self.feed)
        q = fed["currencies"][ccy]["horizons"][tenor]
        q["rate"] += 0.01
        q["futures_price"] -= 0.01
        with self.assertRaisesRegex(ValueError, "immutable current quote changed"):
            build(fed, self.archive, self.conflicts)

    def test_disputed_previous_day_never_used_as_reference(self):
        # The signed EUR FST3U2027 30 Oct 2026 quote is disputed. Build a
        # synthetic current-feed recheck of its clean 2 Nov bar, for which
        # 30 Oct would otherwise be the previous calendar weekday.
        fed = copy.deepcopy(self.feed)
        r = next(x for x in self.archive if x["currency"] == "EUR"
                 and x["contract"] == "FST3U2027"
                 and x["observation_date"] == "2026-11-02")
        q = fed["currencies"]["EUR"]["horizons"]["12m"]
        q.update({"contract": r["contract"], "symbol": r["symbol"],
                  "expiration": r["expiration"],
                  "quote_as_of": r["observation_date"],
                  "futures_price": r["futures_price"], "rate": r["implied_rate"],
                  "quote_timestamp_source": "SSR_DAILY_BAR_DATA_UPDATE_TIME",
                  "quote_timestamp_verified": True})
        # The published source capture timestamp is deliberately unchanged:
        # this is a synthetic replay of a recorded historical quote.
        result = build(fed, self.archive, self.conflicts)
        row = result["currencies"]["EUR"]["12m"]
        self.assertEqual(row["as_of"], "2026-11-02")
        self.assertIsNone(row["change_1d_bp"])
        self.assertIsNone(row["one_day"])
        self.assertIsNone(row["change_1w_bp"])

    def test_quarantine_is_a_hard_guard_against_original_revision(self):
        # Removing a conflict event should FAIL its chain check when the
        # current feed's quarantine metadata still points to that event.
        e = copy.deepcopy(self.conflicts)
        bad = copy.deepcopy(e[0])
        bad["event_id"] = "0" * 64
        e[0] = bad
        with self.assertRaises(ValueError):
            build(self.feed, self.archive, e)


if __name__ == "__main__":
    unittest.main(verbosity=2)
