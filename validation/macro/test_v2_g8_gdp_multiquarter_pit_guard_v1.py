"""Synthetic release chronology tests: illustrative values are NOT factual GDP."""
import copy
import json
import unittest
from pathlib import Path
from validation.macro.v2_g8_gdp_multiquarter_pit_guard_v1 import validate, snapshot

def event(q, day, value, stage=0, unit="PERCENT_QOQ_SA"):
    return dict(currency="GBP", reference_quarter=q, publisher_release_day=day,
                reported_value=value, reported_unit=unit, stage_order=stage,
                source_url="https://www.ons.gov.uk/illustrative",
                verified_publisher_host="www.ons.gov.uk",
                eligible_for_macro_scoring=False, PIT_training_vintage_certified=False)

class Tests(unittest.TestCase):
    def setUp(self):
        self.rows = [event("2026Q1", "2026-05-15", 0.3),
                     event("2026Q1", "2026-06-30", 0.4, 1),
                     event("2026Q2", "2026-08-13", 0.4),
                     event("2026Q2", "2026-09-30", 0.5, 1)]

    def test_asof_does_not_read_future_revisions_or_quarters(self):
        self.assertEqual(snapshot(self.rows, "2026-05-15T23:59:59Z")["visible_vintages"], {})
        first = snapshot(self.rows, "2026-06-01T00:00:00Z")
        self.assertEqual(first["visible_vintages"]["GBP:2026Q1"]["reported_value"], 0.3)
        self.assertNotIn("GBP:2026Q2", first["visible_vintages"])
        final = snapshot(self.rows, "2026-10-01T00:00:00Z")
        self.assertEqual(final["visible_vintages"]["GBP:2026Q2"]["reported_value"], 0.5)
        self.assertFalse(final["safe_to_use_for_beta"])
        self.assertFalse(final["safe_to_update_live_macro_D"])

    def test_actual_research_fixture_chronology(self):
        path = Path(__file__).parent / "fixtures/v2_g8_gdp_multiquarter_partial_official_research_v1.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = validate(data["records"])
        q1 = {r["currency"] for r in rows if r["reference_quarter"] == "2026Q1" and r["stage_order"] == 0}
        self.assertEqual(q1, {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD"})
        self.assertFalse(data["eligible_for_macro_scoring"])
        snap = snapshot(data["records"], "2026-08-01T00:00:00Z")
        self.assertEqual(snap["visible_vintages"]["USD:2026Q2"]["reported_value"], 1.5)
        self.assertEqual(snap["visible_vintages"]["NZD:2026Q1"]["reported_value"], 0.8)
        self.assertFalse(snap["safe_to_change_28_pairs"])

    def test_reject_unsafe_release_metadata(self):
        for mutation in ({"stage_order": 2}, {"reported_unit": "PERCENT_SAAR_ANNUALIZED"},
                         {"verified_publisher_host": "invalid.example"},
                         {"PIT_training_vintage_certified": True},
                         {"publisher_release_day": "2026-03-01"}):
            rows = copy.deepcopy(self.rows)
            rows[1].update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate(rows)

if __name__ == "__main__":
    unittest.main()
