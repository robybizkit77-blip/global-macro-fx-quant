"""End-to-end research-only history, including 2026Q2 legacy release evidence."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from validation.macro.v2_g8_gdp_multiquarter_pit_guard_v1 import validate, snapshot
from validation.macro.v2_g8_gdp_unified_web_research_v1 import (
    FIX, QUARTER_FILES, Q2_2026_LEDGER, read_rows, research_receipt,
    unified_research_rows,
)

class GDPUnifiedResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=unified_research_rows()
        cls.receipt=research_receipt()

    def test_seventeen_quarters_136_distinct_first_recorded_release_keys(self):
        s=self.receipt
        self.assertEqual(s["quarters_documented"], 17)
        self.assertEqual(s["first_publisher_statements_documented"], 136)
        self.assertEqual(s["first_statement_quarters_per_currency"],
                         {c:17 for c in "USD EUR GBP JPY CHF CAD AUD NZD".split()})
        self.assertEqual(len(self.rows),
                         len({(r["currency"],r["reference_quarter"],r["stage_order"])
                              for r in self.rows}))
        self.assertGreater(s["research_events_documented"],136)

    def test_us_duplicate_2026_q2_release_not_counted_twice(self):
        usd=[r for r in self.rows if r["currency"]=="USD"
             and r["reference_quarter"]=="2026Q2"]
        self.assertEqual(len(usd),3)
        self.assertEqual([r["reported_value"] for r in
                          sorted(usd,key=lambda r:r["stage_order"])],[1.5,1.5,2.2])
        self.assertEqual(sum(r["reference_quarter"]=="2026Q2"
                             and r["stage_order"]==0 for r in self.rows),8)

    def test_q2_2026_revision_asof_does_not_look_ahead(self):
        first=snapshot(self.rows,"2026-08-01T00:00:00Z")["visible_vintages"]
        self.assertEqual(first["USD:2026Q2"]["reported_value"],1.5)
        self.assertEqual(first["EUR:2026Q2"]["reported_value"],0.4)
        self.assertNotIn("NZD:2026Q2",first)
        september=snapshot(self.rows,"2026-09-18T00:00:00Z")["visible_vintages"]
        self.assertEqual(september["EUR:2026Q2"]["reported_value"],0.6)
        self.assertEqual(september["GBP:2026Q2"]["reported_value"],0.4)
        self.assertEqual(september["NZD:2026Q2"]["reported_value"],0.2)
        october=snapshot(self.rows,"2026-10-01T00:00:00Z")["visible_vintages"]
        self.assertEqual(october["GBP:2026Q2"]["reported_value"],0.5)
        self.assertEqual(october["USD:2026Q2"]["reported_value"],2.2)

    def test_2024_q1_first_and_later_stage_publication_visibility(self):
        first=snapshot(self.rows,"2024-05-17T00:00:00Z")["visible_vintages"]
        self.assertEqual(first["USD:2024Q1"]["reported_value"],1.6)
        self.assertEqual(first["EUR:2024Q1"]["reported_value"],0.3)
        self.assertEqual(first["GBP:2024Q1"]["reported_value"],0.6)
        self.assertEqual(first["JPY:2024Q1"]["reported_value"],-0.5)
        self.assertEqual(first["CHF:2024Q1"]["reported_value"],0.2)
        self.assertNotIn("NZD:2024Q1",first)
        later=snapshot(self.rows,"2024-07-01T00:00:00Z")["visible_vintages"]
        self.assertEqual(later["USD:2024Q1"]["reported_value"],1.4)
        self.assertEqual(later["GBP:2024Q1"]["reported_value"],0.7)
        self.assertEqual(later["AUD:2024Q1"]["reported_value"],0.1)
        self.assertEqual(later["CAD:2024Q1"]["reported_value"],0.4)
        self.assertEqual(later["NZD:2024Q1"]["reported_value"],0.2)
        self.assertEqual(
            snapshot(self.rows,"2024-09-20T00:00:00Z")["visible_vintages"]
            ["NZD:2024Q1"]["reported_value"],0.1)

    def test_swiss_flash_not_falsely_treated_as_sports_adjusted_same_metric(self):
        before=snapshot(self.rows,"2024-05-17T00:00:00Z")["visible_vintages"]["CHF:2024Q1"]
        later=snapshot(self.rows,"2024-05-31T00:00:00Z")["visible_vintages"]["CHF:2024Q1"]
        self.assertNotEqual(before["reported_unit"],later["reported_unit"])
        self.assertTrue(later["unit_definition_break_acknowledged"])
        self.assertFalse(later["eligible_for_macro_scoring"])
        bad=copy.deepcopy(self.rows)
        for row in bad:
            if row["currency"]=="CHF" and row["reference_quarter"]=="2024Q1" and row["stage_order"]==1:
                row["unit_definition_break_acknowledged"]=False
        with self.assertRaises(ValueError):
            validate(bad)

    def test_corrupted_duplicate_us_in_legacy_file_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in (*QUARTER_FILES,Q2_2026_LEDGER):
                shutil.copy2(FIX/name,root/name)
            path=root/Q2_2026_LEDGER
            old=json.loads(path.read_text(encoding="utf-8"))
            for r in old["records"]:
                if r["currency"]=="USD" and r["stage_order"]==0:
                    r["reported_value"]=99.0
            path.write_text(json.dumps(old),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"overlapping GDP vintage disagrees"):
                unified_research_rows(root)

    def test_not_certified_for_any_live_or_backtest_promotion(self):
        s=self.receipt
        for flag in ("release_day_bytes_historical_archive_certified",
                     "intraday_PIT_certified","cross_country_metric_definition_harmonized",
                     "historical_training_approved","safe_to_update_live_macro_D",
                     "safe_to_use_for_beta","safe_to_use_for_forward","safe_to_change_28_pairs"):
            self.assertIs(s[flag],False)
        self.assertIs(s["source_statement_record_only"],True)
        self.assertEqual(len(read_rows()),len(self.rows)-9)

if __name__=="__main__":
    unittest.main()
