import copy
import json
import unittest

from validation.macro.v2_abs_trimmed_cross_publication_v1 import (
    SOURCE, ABS_LEDGER, audit, replay,
)


class ABSTrimmedCrossPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(SOURCE.read_text(encoding="utf-8"))
        cls.ledger = json.loads(ABS_LEDGER.read_text(encoding="utf-8"))

    def case(self, receipt, period):
        return next(c for c in receipt["cases"] if c["reference_period"] == period)

    def test_before_original_january_value_not_known(self):
        result = replay("2026-02-25T00:29:59Z", self.fixture, self.ledger)
        jan = self.case(result, "2026-01")
        self.assertIsNone(jan["initial_web_reported_value"])
        self.assertEqual(result["cross_report_changes_visible"], 0)

    def test_january_own_period_first_stays_34_until_feb_report(self):
        original = replay("2026-02-25T00:30:00Z", self.fixture, self.ledger)
        before = replay("2026-03-25T00:29:59Z", self.fixture, self.ledger)
        later = replay("2026-03-25T00:30:00Z", self.fixture, self.ledger)
        self.assertEqual(self.case(original, "2026-01")["initial_web_reported_value"], 3.4)
        self.assertEqual(self.case(before, "2026-01")["latest_accessible_reported_value"], 3.4)
        self.assertEqual(self.case(later, "2026-01")["initial_web_reported_value"], 3.4)
        self.assertEqual(self.case(later, "2026-01")["latest_accessible_reported_value"], 3.3)
        self.assertEqual(self.case(later, "2026-01")["known_cross_report_difference_pp"], -0.1)
        self.assertEqual(self.case(later, "2026-01")["first_different_publication_in_scoped_evidence_utc"],
                         "2026-03-25T00:30:00+00:00")
        self.assertFalse(self.case(later, "2026-01")["exact_statistical_revision_effective_time_verified"])

    def test_may_unchanged_at_june_report_then_lower_by_july_report(self):
        original = replay("2026-06-24T01:30:00Z", self.fixture, self.ledger)
        june = replay("2026-07-29T01:30:00Z", self.fixture, self.ledger)
        before = replay("2026-08-26T01:29:59Z", self.fixture, self.ledger)
        july = replay("2026-08-26T01:30:00Z", self.fixture, self.ledger)
        for receipt in (original, june, before):
            case = self.case(receipt, "2026-05")
            self.assertEqual(case["initial_web_reported_value"], 3.6)
            self.assertEqual(case["latest_accessible_reported_value"], 3.6)
            self.assertFalse(case["later_report_known_at_cutoff"])
        case = self.case(july, "2026-05")
        self.assertEqual(case["initial_web_reported_value"], 3.6)
        self.assertEqual(case["latest_accessible_reported_value"], 3.5)
        self.assertEqual(case["known_cross_report_difference_pp"], -0.1)
        self.assertEqual(case["first_different_publication_in_scoped_evidence_utc"],
                         "2026-08-26T01:30:00+00:00")
        self.assertFalse(case["exact_statistical_revision_effective_time_verified"])

    def test_full_coverage_not_full_revision_history(self):
        final = replay("2026-10-24T00:00:00Z", self.fixture, self.ledger)
        self.assertEqual(final["official_source_web_evidence_count_total"], 5)
        self.assertEqual(final["official_source_web_evidence_visible_at_cutoff"], 5)
        self.assertEqual(final["cross_report_changes_visible"], 2)
        self.assertEqual(final["changes_certified_as_complete_original_vintage_revisions"], 0)
        for field in ("source_release_day_bytes_archived", "historical_revision_chain_complete",
                      "training_observation_count_changed", "eligible_for_backtest",
                      "safe_to_publish_new_D", "safe_to_update_pair_theses", "writes_live_data"):
            self.assertFalse(final[field])
        self.assertTrue(all(c["source_difference_is_proof_of_original_release_day_vintage"] is False
                            for c in final["cases"]))

    def test_fail_closed_changed_pins_and_false_archiving(self):
        mutations = (
            (0, "reported_value", 3.3),
            (1, "reported_value", 3.4),
            (4, "reported_value", 3.6),
            (4, "report_period", "2026-08"),
            (4, "reported_at_local", "2026-08-26T11:30:00+11:00"),
            (4, "source_url", "https://example.com/trimmed"),
            (0, "page_capture_at_first_release_proven", True),
        )
        for i, key, val in mutations:
            with self.subTest(i=i,key=key):
                data = copy.deepcopy(self.fixture)
                data["observations"][i][key] = val
                with self.assertRaises((ValueError, TypeError)):
                    audit(data, self.ledger)
        for k in ("complete_revision_chain_certified", "backtest_allowed", "writes_live_data"):
            changed = copy.deepcopy(self.fixture)
            changed[k] = True
            with self.assertRaises((ValueError, TypeError)):
                audit(changed, self.ledger)

    def test_no_mutation_and_determinism(self):
        f = copy.deepcopy(self.fixture)
        l = copy.deepcopy(self.ledger)
        a = replay("2026-08-26T01:30:00Z", f, l)
        self.assertEqual(a, replay("2026-08-26T01:30:00Z", f, l))
        self.assertEqual(self.fixture, f)
        self.assertEqual(self.ledger, l)


if __name__ == "__main__":
    unittest.main()
