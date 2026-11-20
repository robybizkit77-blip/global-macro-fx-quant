from datetime import date, datetime, timedelta
import unittest

from validation.forward import check_frozen_core_macro_directions_v1 as study
from validation.forward import observe_official_ecb_reference_outcomes_v1 as ecb


class FrozenCoreMacroComparisonTest(unittest.TestCase):
    def setUp(self):
        dates = [date(2026, 10, 20) + timedelta(days=n) for n in range(36)]
        days = [day.isoformat() for day in dates if day.weekday() < 5]
        shocks = {"2026-11-02": 1.20, "2026-11-03": 1.31, "2026-11-10": 1.25}
        self.fx = {
            "schema": "GMFQ_ECB_G8_PRICE_HISTORY_V1", "status": "CURRENT_OFFICIAL_HISTORY",
            "source_url": ecb.SOURCE_URL, "base": "EUR", "last_as_of": days[-1],
            "rows": [{"Date": day, "EUR": 1, "USD": shocks.get(day, 1.05 + n / 1000)}
                     for n, day in enumerate(days)],
        }
        self.rates = ecb.source_map(self.fx)
        self.now = datetime.fromisoformat("2026-11-20T20:30:00+01:00")

    def snapshot(self, day, macro="EUR"):
        row = self.rates[date.fromisoformat(day)]
        anchor = {
            "layer": "ECB_DAILY_REFERENCE_NOT_EXECUTABLE_SPOT", "state": "OBSERVED_AT_CAPTURE",
            "rate": row["USD"], "source_date": day, "pair": "EUR/USD", "source_sha256": day,
            "source_id": "live_data/sections/ECB_G8_PRICE_HISTORY.json", "intra_day_traded_price": False,
            "official_publication_instant_independently_verified": False,
        }
        snap = {
            "snapshot_id": day, "pair": "EUR/USD", "source_commit": "c" * 40,
            "capture_class": "FROZEN_CORE_BASELINE_OBSERVATION",
            "schema_version": "GMFQ_CORE_FORWARD_DECISION_LOGGER_V1.1.0",
            "decision_cutoff": day + "T19:30:00Z", "core_baseline_as_of": study.FROZEN_MACRO_ASOF,
            "core_recomputed_at_capture": False, "current_macro_score_certified": False,
            "price_anchor_is_executable": False, "core_signal": "USD", "t0_fx_reference": anchor,
            "inputs": {"ecb_reference": anchor, "core_pair_state": {
                "state": "AVAILABLE", "observed_or_as_of": study.FROZEN_MACRO_ASOF,
                "value": {"layers": {"macro": macro}, "convergence_winner": "USD"},
            }},
            "source_provenance": {"ecb_reference": {
                "source_id": anchor["source_id"], "sha256": day,
            }},
        }
        snap["snapshot_sha256"] = ecb.digest(snap)
        return snap

    def run_study(self, snapshots, refs=None):
        if refs is None:
            refs = ecb.compute(snapshots, self.fx, self.now)["new_rows"]

        def original(_, day):
            return {d: row for d, row in self.rates.items() if d.isoformat() <= day}

        return study.assess(snapshots, refs, self.fx, {"EUR/USD"}, original, self.now)

    def test_macro_core_and_benchmark_share_a_strictly_future_target(self):
        result = self.run_study([self.snapshot("2026-11-02")])
        window, = result["observed_windows"]
        self.assertEqual((window["start_fixing"], window["end_fixing"]), ("2026-11-03", "2026-11-10"))
        # 1.20 at capture, 1.31 at first future fixing, then 1.25 at the target.
        self.assertEqual(window["macro"], {"comparable_pairs": 1, "correct": 0, "momentum_correct": 0})
        self.assertEqual(window["core"], {"comparable_pairs": 1, "correct": 1, "momentum_correct": 0})

    def test_overlap_and_repeated_frozen_directions_are_visible(self):
        result = self.run_study([self.snapshot(day) for day in ("2026-11-02", "2026-11-03", "2026-11-10")])
        self.assertEqual(result["all_complete_windows"]["windows"], 3)
        self.assertEqual(result["nonoverlapping_capture_dates"], ["2026-11-02", "2026-11-10"])
        self.assertEqual(result["unique_frozen_direction_vectors"], 1)

    def test_abstentions_not_credited_and_missing_references_visible(self):
        row = self.snapshot("2026-11-02", macro="MISTO")
        result = self.run_study([row])
        self.assertEqual(result["all_complete_windows"]["macro"]["comparable_pairs"], 0)
        self.assertEqual(result["all_complete_windows"]["core"]["comparable_pairs"], 1)
        missing = self.run_study([row], refs=[])
        self.assertEqual(missing["captured_days"], 1)
        self.assertEqual(missing["all_complete_windows"]["windows"], 0)

    def test_duplicates_and_later_outcome_substitution_fail(self):
        snaps = [self.snapshot("2026-11-02")]
        ref, = (row for row in ecb.compute(snaps, self.fx, self.now)["new_rows"] if row["horizon"] == "1W")
        with self.assertRaisesRegex(ValueError, "Duplicate, orphaned or changed"):
            self.run_study(snaps, [ref, ref])
        altered = {**ref, "observed_reference_date": "2026-11-11"}
        altered.pop("observation_sha256")
        altered["observation_sha256"] = ecb.digest(altered)
        with self.assertRaisesRegex(ValueError, "does not match its dates"):
            self.run_study(snaps, [altered])


if __name__ == "__main__":
    unittest.main()
