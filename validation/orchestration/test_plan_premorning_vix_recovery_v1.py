#!/usr/bin/env python3
"""07:45 CET/CEST official VIX selective retry: network-free contract tests."""
import copy
import datetime as dt
import unittest
from pathlib import Path
from zoneinfo import ZoneInfo
from validation.orchestration.plan_premorning_vix_recovery_v1 import assess

ROOT = Path(__file__).resolve().parents[2]
ROME = ZoneInfo("Europe/Rome")


def model(day, value=16.91):
    return {"risk": {"VIX": {
        "dates": ["2026-01-27", day], "values": [17.3, value],
        "last_date": day, "last_value": value,
    }}}


class PreMorningVixTests(unittest.TestCase):
    def test_october_30_current_close_skips_without_fetch(self):
        state = assess(dt.datetime.fromisoformat("2026-10-30T07:45:00+01:00"),
                       model("2026-10-29"))
        self.assertEqual(state["status"], "SKIP_OFFICIAL_PREVIOUS_CLOSE_VERIFIED")
        self.assertEqual(state["required_previous_weekday"], "2026-10-29")
        self.assertTrue(state["source_history_integrity"])

    def test_stale_close_requires_real_cboe_fetch(self):
        state = assess(dt.datetime.fromisoformat("2026-10-30T07:45:00+01:00"),
                       model("2026-10-28"))
        self.assertEqual(state["status"], "RETRY_OFFICIAL_CBOE_CHECK")
        self.assertEqual(state["observed_official_date"], "2026-10-28")

    def test_dst_monday_uses_last_friday(self):
        for instant in ("2026-10-26T07:45:00+01:00", "2026-07-20T07:45:00+02:00"):
            now = dt.datetime.fromisoformat(instant)
            expected = now.astimezone(ROME).date() - dt.timedelta(days=3)
            state = assess(now, model(expected.isoformat()))
            self.assertEqual(state["required_previous_weekday"], expected.isoformat())
            self.assertEqual(state["status"], "SKIP_OFFICIAL_PREVIOUS_CLOSE_VERIFIED")

    def test_corruption_or_future_data_cannot_skip(self):
        now = dt.datetime.fromisoformat("2026-10-30T07:45:00+01:00")
        good = model("2026-10-29")
        for variant in ("mismatch", "no_values", "different_value", "future", "bad_date", "missing"):
            x = copy.deepcopy(good)
            row = x["risk"]["VIX"]
            if variant == "mismatch":
                row["dates"][-1] = "2026-10-28"
            elif variant == "no_values":
                row["values"] = []
            elif variant == "different_value":
                row["last_value"] += 1
            elif variant == "future":
                row["last_date"] = "2026-10-30"
                row["dates"][-1] = "2026-10-30"
            elif variant == "bad_date":
                row["last_date"] = "not-a-date"
            elif variant == "missing":
                x = {}
            self.assertEqual(assess(now, x)["status"], "RETRY_OFFICIAL_CBOE_CHECK", variant)
        self.assertEqual(assess(now, [])["status"], "RETRY_OFFICIAL_CBOE_CHECK")

    def test_naive_clock_rejected(self):
        with self.assertRaisesRegex(ValueError, "Timezone-aware"):
            assess(dt.datetime(2026, 10, 30, 7, 45), model("2026-10-29"))

    def test_orchestrator_admits_one_conditional_recovery_without_new_cron(self):
        workflow = (ROOT / ".github/workflows/daily-data-orchestrator-v2.yml").read_text()
        segment = workflow.split('              premorning)', 1)[1].split('              morning)', 1)[0]
        self.assertEqual(segment.count('vix-persistent-apply-v1.yml'), 1)
        self.assertIn('if [[ "$phase" == "premorning" && "$wf" == "vix-persistent-apply-v1.yml" ]]', workflow)
        self.assertIn("--source-file /tmp/premorning-vix-current-main.json", workflow)
        self.assertIn("git show origin/main:live_data/sections/D.json", workflow)
        self.assertIn("07:45 VIX: **SKIPPED**", workflow)
        self.assertIn("07:45 VIX: **RETRY**", workflow)
        self.assertEqual(workflow.count("    - cron:"), 10)


if __name__ == "__main__":
    unittest.main()
