import unittest
from datetime import date, datetime, timedelta

from validation.pair_thesis.check_next_forward_ecb_v1 import (
    SOURCE_URL, assess, verify_first_archive_commits,
)


def fixture():
    days = [date(2026, 11, 10) + timedelta(days=i) for i in range(20)]
    rows = [{"Date": d.isoformat(), "EUR": 1, "USD": 1 + n / 100}
            for n, d in enumerate(d for d in days if d.weekday() < 5)]
    return {"schema": "GMFQ_ECB_G8_PRICE_HISTORY_V1", "status": "CURRENT_OFFICIAL_HISTORY",
            "source_url": SOURCE_URL, "base": "EUR", "last_as_of": rows[-1]["Date"], "rows": rows}


def capture(day="2026-11-18", instant="17:30:00Z", favored="EUR"):
    return {"capturedAt": f"{day}T{instant}", "fixing": day, "macroAsOf": day, "method": "a" * 64,
            "pairs": {"EURUSD": {"favored": favored, "thesis": "PARZIALE"}}}


def run(captures, now, commits=None):
    fx = fixture()
    if commits is None:
        commits = {s["capturedAt"]: ("main-archive-commit", s["capturedAt"]) for s in captures}

    def original(s):
        return {date.fromisoformat(r["Date"]): r for r in fx["rows"] if r["Date"] <= s["fixing"]}

    return assess(captures, {"EURUSD"}, commits, fx, original, datetime.fromisoformat(now))["captures"]


class NextForwardEcbTest(unittest.TestCase):
    def test_interval_strictly_after_capture_and_archived_price_benchmark(self):
        row, = run([capture()], "2026-11-20T19:10:00+01:00")
        self.assertEqual(row["cohort"], "PILOT")
        self.assertEqual((row["start_fixing"], row["end_fixing"]), ("2026-11-19", "2026-11-20"))
        self.assertEqual((row["comparable_pairs"], row["next_correct"], row["momentum_correct"]), (1, 1, 1))

    def test_waits_for_today_cutoff_and_for_delayed_archival(self):
        sample = capture()
        self.assertEqual(run([sample], "2026-11-20T18:59:00+01:00")[0]["status"],
                         "WAITING_FOR_TWO_LATER_ECB_FIXINGS")
        late = {sample["capturedAt"]: ("delayed-commit", "2026-11-19T10:00:00Z")}
        result, = run([sample], "2026-11-23T19:10:00+01:00", commits=late)
        self.assertEqual((result["start_fixing"], result["end_fixing"]), ("2026-11-20", "2026-11-23"))

    def test_one_capture_per_day_and_unavailable_provenance(self):
        records = run([capture(), capture(instant="18:00:00Z", favored="USD")],
                      "2026-11-20T19:10:00+01:00")
        self.assertEqual([r["status"] for r in records],
                         ["OBSERVED_ECB_INTERVAL", "LATER_CAPTURE_SAME_DAY"])
        self.assertEqual(run([capture()], "2026-11-20T19:10:00+01:00", commits={})[0]["status"],
                         "ARCHIVE_PROVENANCE_PENDING")

    def test_no_direction_is_kept_in_coverage_and_never_wins(self):
        r, = run([capture(favored=None)], "2026-11-20T19:10:00+01:00")
        self.assertEqual((r["canonical_pairs"], r["directions_issued"], r["comparable_pairs"]), (1, 0, 0))
        self.assertEqual((r["next_correct"], r["momentum_correct"]), (0, 0))

    def test_first_persistence_rejects_rewrites(self):
        item = capture()
        born = ("first", "2026-11-18T18:01:00Z", [item])
        later = ("later", "2026-11-20T18:01:00Z", [item])
        captures, first = verify_first_archive_commits([], [born, later])
        self.assertEqual(captures, [item])
        self.assertEqual(first[item["capturedAt"]], born[:2])
        with self.assertRaisesRegex(ValueError, "rewritten"):
            verify_first_archive_commits([item], [born, (*later[:2], [capture(favored="USD")])])

    def test_prospectively_frozen_cohort_starts_after_rule(self):
        r, = run([capture(day="2026-11-23")], "2026-11-25T19:10:00+01:00")
        self.assertEqual(r["cohort"], "POST_PROTOCOL")
        self.assertEqual((r["start_fixing"], r["end_fixing"]), ("2026-11-24", "2026-11-25"))


if __name__ == "__main__":
    unittest.main()
