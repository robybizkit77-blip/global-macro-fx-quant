from datetime import date, datetime
from copy import deepcopy
import unittest

from validation.forward import check_next_estimate_core_comparison_v1 as m
from validation.forward.test_macro_challenger_v1 import fixture, fx


class NextEstimateComparisonTests(unittest.TestCase):
    def setUp(self):
        f = fixture()
        self.core = f["core"]
        self.original = m.source_map(f["prices"])
        self.snap = {
            "fixing": "2026-11-19", "macroAsOf": "2026-11-20",
            "capturedAt": "2026-11-20T11:00:00Z", "commit": "a"*40,
            "method": "b"*64, "sourceHashes": {"prices": "c"*64},
            "pairs": {p["pair"].replace("/", ""): {"favored": p["pair"].split("/")[0]}
                      for p in self.core["pairs"]},
        }
        self.origin = lambda commit, sha: (self.original, self.core, "2026-11-20T10:00:00Z")
        self.archive = {"schema": "GMFQ_NEXT_ESTIMATED_FX_THESIS_HISTORY_V1", "snapshots": [self.snap]}

    def evaluate(self, entries, when):
        now = datetime.fromisoformat(when)
        return m.evaluate(entries, fx(now.date()), self.origin, now)

    def test_archive_recovers_rolled_off_and_rejects_mutation(self):
        empty = {**self.archive, "snapshots": []}
        first = "2026-11-23T08:00:00Z"
        self.assertEqual(m.recover([(self.archive, first), (empty, "2026-11-24T08:00:00Z")]),
                         [(self.snap, first)])
        changed = deepcopy(self.archive)
        changed["snapshots"][0]["pairs"]["AUDEUR"]["favored"] = None
        with self.assertRaisesRegex(ValueError, "changed"):
            m.recover([(self.archive, first), (changed, "2026-11-24T08:00:00Z")])

    def test_late_archive_waits_and_uses_next_fixing(self):
        entries = [(self.snap, "2026-11-23T08:00:00Z")]
        early = self.evaluate(entries, "2026-11-30T22:00:00+01:00")
        self.assertEqual(early["windows"][0]["status"], "WAITING_FOR_WEEKLY_ECB_OUTCOME")
        late = self.evaluate(entries, "2026-12-01T22:00:00+01:00")
        window, = late["windows"]
        self.assertEqual((window["start_fixing"], window["end_fixing"]), ("2026-11-24", "2026-12-01"))
        self.assertEqual(window["comparable_pairs"], 28)
        self.assertEqual(window["estimate_correct"], window["core_correct"])
        self.assertFalse(late["eligible_to_replace_core"])

    def test_neutral_excluded_and_overlapping_windows_not_double_counted(self):
        self.snap["pairs"]["AUDEUR"]["favored"] = None
        later = deepcopy(self.snap)
        later["capturedAt"] = "2026-11-24T08:00:00Z"
        report = self.evaluate([(self.snap, "2026-11-23T08:00:00Z"),
                                (later, "2026-11-24T08:01:00Z")], "2026-12-03T22:00:00+01:00")
        self.assertEqual(len(report["windows"]), 2)
        self.assertEqual(report["windows"][0]["comparable_pairs"], 27)
        self.assertEqual(report["nonoverlapping_by_method"]["b"*64]["windows"], 1)

    def test_coverage_keeps_abstentions_and_disagreements_separate(self):
        votes = {"A": (1,-1,1), "B": (0,1,-1), "C": (-1,1,0), "D": (1,1,1)}
        counts = m.coverage(votes, {"A":1, "B":-1, "C":1, "D":0})
        self.assertEqual(counts["nonflat_outcomes"],3)
        self.assertEqual(counts["flat_outcomes"],1)
        self.assertEqual(counts["estimate_directional"],2)
        self.assertEqual(counts["estimate_abstained"],1)
        self.assertEqual(counts["estimate_correct_all_directional"],1)
        self.assertEqual(counts["core_directional"],3)
        self.assertEqual(counts["estimate_core_disagree"],2)
        self.assertEqual(counts["estimate_wins_disagreement"],1)
        self.assertEqual(counts["core_wins_disagreement"],1)

    def test_coverage_aggregation_excludes_overlapping_windows(self):
        self.snap["pairs"]["AUDEUR"]["favored"] = None
        later = deepcopy(self.snap)
        later["capturedAt"] = "2026-11-24T08:00:00Z"
        report = self.evaluate([(self.snap, "2026-11-23T08:00:00Z"),
                                (later, "2026-11-24T08:01:00Z")], "2026-12-03T22:00:00+01:00")
        selected = [w for w in report["windows"] if w.get("selected_nonoverlapping")]
        self.assertEqual(len(selected),1)
        self.assertEqual(report["coverage_on_selected_nonoverlapping_windows"]["b"*64],selected[0]["coverage"])
        self.assertEqual(selected[0]["coverage"]["estimate_abstained"],1)
        self.assertFalse(report["eligible_to_replace_core"])

    def test_rejects_future_and_invalid_pair(self):
        with self.assertRaisesRegex(ValueError, "Future"):
            self.evaluate([(self.snap, "2026-12-03T08:00:00Z")], "2026-12-01T22:00:00+01:00")
        self.snap["pairs"]["AUDEUR"]["favored"] = "USD"
        with self.assertRaisesRegex(ValueError, "orientation"):
            self.evaluate([(self.snap, "2026-11-23T08:00:00Z")], "2026-12-01T22:00:00+01:00")


if __name__ == "__main__":
    unittest.main()
