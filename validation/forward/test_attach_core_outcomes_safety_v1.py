"""No-future no-fake outcome ingestion: research-only pure unit suite."""
import copy
import datetime as dt
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("attach_core_outcomes_v1", HERE / "attach_core_outcomes_v1.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def sources():
    sid = "a" * 64
    decisions = {
        sid: {"snapshot_id": sid, "decision_cutoff": "2026-10-14T21:01:45Z"}
    }
    item = {
        "snapshot_id": sid, "horizon": "1W", "gross_return": 0.012,
        "cost_bps": 1.5, "source_id": "FIXTURE_PRICE_SOURCE_NOT_LICENSED",
        "available_at": "2026-10-21T21:02:00+00:00",
    }
    return decisions, item


class SafeOutcomes(unittest.TestCase):
    def case(self, item=None, as_of="2026-10-21", old=()):
        decisions, baseline = sources()
        return mod.evaluate(decisions, [item or baseline], set(old),
                            dt.date.fromisoformat(as_of))

    def test_positive_record_does_not_certify_input_or_performance(self):
        x = self.case()[0]
        self.assertEqual(x["horizon"], "1W")
        self.assertAlmostEqual(x["net_return"], 0.01185)
        self.assertEqual(x["price_input_provenance"], "CALLER_SUPPLIED_NOT_INDEPENDENTLY_VERIFIED")
        self.assertFalse(x["performance_certified"])
        self.assertEqual(x["outcome_sha256"], mod.sha({k: v for k, v in x.items() if k != "outcome_sha256"}))

    def test_idempotency_same_record(self):
        decisions, x = sources()
        self.assertEqual(self.case(old={(x["snapshot_id"], "1W")}), [])

    def test_duplicate_inside_new_batch_is_fatal(self):
        decisions, x = sources()
        with self.assertRaisesRegex(ValueError, "duplicate snapshot/horizon"):
            mod.evaluate(decisions, [x, copy.deepcopy(x)], set(), dt.date(2026, 10, 21))

    def test_reject_unlinked_snapshot(self):
        _, x = sources()
        x["snapshot_id"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "unknown snapshot"):
            self.case(x)

    def test_reject_early_outcome_before_full_seven_days(self):
        _, x = sources()
        x["available_at"] = "2026-10-21T20:59:00Z"
        with self.assertRaisesRegex(ValueError, "full target horizon"):
            self.case(x)

    def test_reject_future_observation_after_asof(self):
        _, x = sources()
        x["available_at"] = "2026-10-22T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "not available as of"):
            self.case(x)

    def test_no_premature_horizon_if_asof_early(self):
        _, x = sources()
        x["horizon"] = "3M"
        self.assertEqual(self.case(x, as_of="2026-10-21"), [])

    def test_naive_outcome_timestamp_rejected(self):
        _, x = sources()
        x["available_at"] = "2026-10-21T21:02:00"
        with self.assertRaisesRegex(ValueError, "timezone-naive"):
            self.case(x)

    def test_outcome_equal_to_decision_rejected(self):
        _, x = sources()
        x["available_at"] = "2026-10-14T21:01:45Z"
        with self.assertRaisesRegex(ValueError, "coincides with decision"):
            self.case(x)

    def test_nonfinite_gross_return_rejected(self):
        _, x = sources()
        x["gross_return"] = float("nan")
        with self.assertRaisesRegex(ValueError, "numeric finite gross_return"):
            self.case(x)

    def test_forged_boolean_return_rejected(self):
        _, x = sources()
        x["gross_return"] = True
        with self.assertRaisesRegex(ValueError, "numeric finite gross_return"):
            self.case(x)

    def test_invalid_costs_rejected(self):
        _, x = sources()
        x["cost_bps"] = -1
        with self.assertRaisesRegex(ValueError, "negative cost_bps"):
            self.case(x)

    def test_missing_cost_rejected_instead_of_claiming_net_return(self):
        _, x = sources()
        x["cost_bps"] = None
        with self.assertRaisesRegex(ValueError, "numeric finite cost_bps"):
            self.case(x)

    def test_missing_price_source_rejected(self):
        _, x = sources()
        x["source_id"] = ""
        with self.assertRaisesRegex(ValueError, "missing verifiable source"):
            self.case(x)

    def test_time_offset_normalized_consistently(self):
        _, x = sources()
        x["available_at"] = "2026-10-21T23:02:00+02:00"
        self.assertEqual(self.case(x)[0]["available_at"], "2026-10-21T21:02:00Z")


if __name__ == "__main__":
    unittest.main()
