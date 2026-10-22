#!/usr/bin/env python3
"""Independent fail-closed tests for Macro source / release / score joint audit."""
from __future__ import annotations
import copy
import json
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from validation.macro.rebase_joint_gate_v1 import combine, run
from validation.macro.rebase_readiness_v1 import ROOT, PATHS, g8_coverage
from validation.macro.latest_release_pit_ledger_v1 import build_ledger

ASOF = datetime.now(ZoneInfo("Europe/Rome")).date()


class JointMacroGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        feeds = {k: json.loads((ROOT / p).read_text(encoding="utf-8"))
                 for k, p in PATHS.items()}
        cls.source = g8_coverage(*(feeds[k] for k in PATHS), ASOF)
        cls.ledger = build_ledger(ROOT, ASOF)

    def analyze(self, source=None, ledger=None):
        return combine(copy.deepcopy(source or self.source),
                       copy.deepcopy(ledger or self.ledger))

    def test_real_evidence_and_explicit_block(self):
        out = self.analyze()
        self.assertEqual(out["status"], "AUDITED_NOT_AUTHORIZED_FOR_MACRO_REBASE")
        self.assertEqual(out["macro_baseline_as_of"], "2026-09-25")
        self.assertEqual(out["source_rows_compared"], 16)
        self.assertEqual(out["currency_count"], 8)
        self.assertEqual(out["pair_count"], 28)
        self.assertEqual(sum(out["release_grades"].values()), 16)
        self.assertFalse(out["safe_to_publish_new_D"])
        self.assertFalse(out["safe_to_update_pair_thesis"])
        self.assertFalse(out["writes_live_data"])
        self.assertEqual(len(out["mandatory_open_gates"]), 4)
        self.assertTrue(all(not lane["source_ready"]["inflation"]["archival_vintage_certified"]
                            and not lane["source_ready"]["labour"]["score_transform_certified"]
                            for lane in out["currency_gates"].values()))

    def test_each_source_value_and_period_must_match_across_audits(self):
        ledger = copy.deepcopy(self.ledger)
        ledger["observations"]["USD.inflation"]["latest_transformed_observation"] += 0.1
        with self.assertRaisesRegex(ValueError, "value mismatch"):
            self.analyze(ledger=ledger)
        ledger = copy.deepcopy(self.ledger)
        ledger["observations"]["EUR.labour"]["current_observation_period"] = "2026-01"
        with self.assertRaisesRegex(ValueError, "period or id mismatch"):
            self.analyze(ledger=ledger)

    def test_unlicensed_intraday_promotion_is_rejected(self):
        ledger = copy.deepcopy(self.ledger)
        dates = [x for x in ledger["observations"].values()
                 if x["release"]["status"] == "DATE_ONLY"]
        self.assertGreater(len(dates), 0)
        dates[0]["release"]["date_only_not_eligible_for_intraday_PIT"] = False
        with self.assertRaisesRegex(ValueError, "date-only intraday promotion"):
            self.analyze(ledger=ledger)

    def test_falsely_published_canonical_macro_is_rejected(self):
        source = copy.deepcopy(self.source)
        source["safe_to_publish_D"] = True
        with self.assertRaisesRegex(ValueError, "unsafe source-to-engine"):
            self.analyze(source=source)
        ledger = copy.deepcopy(self.ledger)
        ledger["historical_vintage_series_available"] = True
        with self.assertRaisesRegex(ValueError, "falsely promoted"):
            self.analyze(ledger=ledger)

    def test_missing_or_modified_currency_pit_lineage_is_rejected(self):
        source = copy.deepcopy(self.source)
        source["currencies"]["CAD"]["labour"]["series_id"] = "WRONG"
        with self.assertRaisesRegex(ValueError, "period or id mismatch"):
            self.analyze(source=source)
        ledger = copy.deepcopy(self.ledger)
        ledger["observations"].pop("GBP.labour")
        with self.assertRaisesRegex(ValueError, "source identities"):
            self.analyze(ledger=ledger)

    def test_release_counts_must_not_be_claimed_green(self):
        ledger = copy.deepcopy(self.ledger)
        ledger["counts"]["FULL_RELEASE_INSTANT"] += 1
        ledger["counts"]["DATE_ONLY"] -= 1
        with self.assertRaisesRegex(ValueError, "release evidence counts"):
            self.analyze(ledger=ledger)

    def test_real_repository_is_never_changed(self):
        # run() writes no files and cannot publish canonical Macro scores.
        receipt = run(root=ROOT, today=ASOF)
        self.assertFalse(receipt["safe_to_publish_new_D"])
        self.assertFalse(receipt["writes_live_data"])


if __name__ == "__main__":
    unittest.main()
