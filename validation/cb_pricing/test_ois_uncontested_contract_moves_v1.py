#!/usr/bin/env python3
"""Adversarial research-only proof: healthy EUR/CHF contracts survive USD conflicts."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from ois_same_contract_history_v1 import HISTORY, SOURCE, load_history
from reconcile_ois_secondary_conflicts_v1 import (
    CONFLICTS, apply, read_conflicts, validate_conflict_lineage,
)
from ois_uncontested_contract_moves_v1 import evaluate


class UncontestedContractEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive = load_history(HISTORY)
        cls.events = read_conflicts(CONFLICTS)
        cls.source = json.loads(SOURCE.read_text(encoding="utf-8"))

    def case(self, source=None, rows=None, events=None):
        return evaluate(
            copy.deepcopy(self.source if source is None else source),
            copy.deepcopy(self.archive if rows is None else rows),
            copy.deepcopy(self.events if events is None else events),
        )

    def test_current_live_is_not_ois_and_preserves_healthy_contracts(self):
        result = self.case()
        self.assertEqual(result["summary"]["total_horizons"], 9)
        self.assertFalse(result["writes_live_data"])
        self.assertFalse(result["writes_history"])
        self.assertFalse(result["official_ois_curve_constructed"])
        self.assertEqual(result["summary"]["official_ois_promotions"], 0)
        self.assertEqual(result["summary"]["policy_deltas_computed"], 0)
        self.assertEqual(result["summary"]["fx_signals_computed"], 0)
        for row in result["currencies"].values():
            for p in row.values():
                self.assertIs(p["official_ois"], False)
                self.assertIs(p["policy_delta_allowed"], False)
                self.assertIs(p["trade_signal_allowed"], False)
                self.assertEqual(p["forward_v2_effect"], "NONE")
                self.assertIs(p["is_exactly_one_trading_session"], False
                              if p["observed_same_contract_change_bp"] is not None else None)

    def test_exact_oct30_disputed_source_excludes_all_three_usd(self):
        # Fixed historically signed-off Oct 30 captures. A newer feed can
        # advance after the weekend without making this fixture obsolete.
        fixture = self.fixture_oct30()
        result = evaluate(fixture, self.archive, self.events)
        for p in result["currencies"]["USD"].values():
            self.assertEqual(p["status"], "WITHHELD_DISPUTED_CURRENT_BAR")
            self.assertIsNone(p["observed_same_contract_change_bp"])
        eur = result["currencies"]["EUR"]
        self.assertEqual(eur["12m"]["status"], "WITHHELD_DISPUTED_CURRENT_BAR")
        self.assertEqual(eur["6m"]["status"],
                         "VERIFIED_SAME_CONTRACT_OBSERVED_MOVE_RESEARCH_ONLY")
        self.assertEqual(eur["6m"]["matched_previous_quote_day"], "2026-10-29")
        self.assertAlmostEqual(eur["6m"]["observed_same_contract_change_bp"], -0.25)
        chf = result["currencies"]["CHF"]
        self.assertEqual(chf["3m"]["status"], "WITHHELD_DISPUTED_CURRENT_BAR")
        self.assertEqual(chf["6m"]["status"],
                         "VERIFIED_SAME_CONTRACT_OBSERVED_MOVE_RESEARCH_ONLY")
        self.assertAlmostEqual(chf["6m"]["observed_same_contract_change_bp"], -1.0)
        self.assertEqual(result["summary"]["observed_same_contract_moves"], 4)
        self.assertEqual(result["summary"]["disputed_or_unverified_current_contracts"], 5)

    def fixture_oct30(self):
        quote = copy.deepcopy(self.source)
        quote["generated_at_utc"] = "2026-10-31T21:00:27.263906Z"
        ev = {(e["key"][0],e["original_immutable_quote"]["observed_under_horizon"]):
              e for e in self.events if e["key"][2] == "2026-10-30"}
        for c in ("USD", "EUR", "CHF"):
            r = quote["currencies"][c]
            r["source_quality"] = "SECONDARY_PUBLIC_LIVE_PROXY"
            r["status"] = "LIVE_SECONDARY_READY"
            r.pop("source_conflict_status", None)
            r.pop("source_conflict_keys", None)
            keys = []
            for horizon, days in (("3m",90),("6m",180),("12m",365)):
                sample = [row for row in self.archive
                          if row["currency"] == c
                          and row["observed_under_horizon"] == horizon
                          and row["observation_date"] == "2026-10-30"]
                candidates = sorted(sample, key=lambda v:v["contract"])
                # EUR can have two distinct 12M listed contracts on the
                # same day: choose the one with a signed source conflict.
                e = ev.get((c,horizon))
                row = e["conflicting_source_quote"] if e else candidates[0]
                p = r["horizons"][horizon]
                p.update({
                    "contract":row["contract"],"symbol":row["symbol"],
                    "expiration":row["expiration"],
                    "quote_as_of":row["observation_date"],
                    "futures_price":row["futures_price"],"rate":row["implied_rate"],
                    "mapping":f"nearest dated listed contract expiry to today+{days}d; no interpolation",
                    "quote_timestamp_verified":e is None,
                    "quote_timestamp_source":
                        ("QUARANTINED_SAME_CONTRACT_SAME_DAY" if e else
                         "SSR_DAILY_BAR_DATA_UPDATE_TIME"),
                })
                if e:
                    keys.append({"contract":row["contract"],
                                 "observation_date":row["observation_date"],
                                 "horizon":horizon,"event_id":e["event_id"]})
            if keys:
                r["status"] = "LIVE_SECONDARY_CONFLICT_QUARANTINED"
                r["source_conflict_status"] = (
                    "UNRESOLVED_SECONDARY_SOURCE_SAME_DAY_CONFLICT")
                r["source_conflict_keys"] = keys
        return quote

    def test_forged_event_identity_never_licenses_disputed_raw(self):
        fixture = self.fixture_oct30()
        fixture["currencies"]["EUR"]["source_conflict_keys"][0]["event_id"] = "0"*64
        with self.assertRaisesRegex(ValueError, "nonexistent or malformed"):
            self.case(source=fixture)

    def test_modified_quarantined_value_without_event_rejected(self):
        fixture = self.fixture_oct30()
        fixture["currencies"]["CHF"]["horizons"]["3m"]["rate"] += 0.01
        with self.assertRaisesRegex(ValueError, "not identical to signed event"):
            self.case(source=fixture)

    def test_archive_history_mutation_fails_closed(self):
        fixture = self.fixture_oct30()
        altered = copy.deepcopy(self.archive)
        key = self.events[0]["key"]
        row = next(x for x in altered if
                   [x["currency"],x["contract"],x["observation_date"]] == key)
        row["implied_rate"] += 0.01
        row["futures_price"] -= 0.01
        with self.assertRaisesRegex(ValueError, "immutable first quote"):
            self.case(source=fixture, rows=altered)

    def test_clean_other_currency_is_not_blocked_by_unrelated_usd(self):
        fixture = self.fixture_oct30()
        # A genuine source conflict in the USD branch must not mask verified
        # EUR/CHF 6M historical observations and 1-day calendar gap.
        out = self.case(source=fixture)
        for c in ("EUR","CHF"):
            p = out["currencies"][c]["6m"]
            self.assertEqual(p["calendar_gap_days"], 1)
            self.assertEqual(p["quote_day"], "2026-10-30")
            self.assertIsNotNone(p["observed_same_contract_change_bp"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
