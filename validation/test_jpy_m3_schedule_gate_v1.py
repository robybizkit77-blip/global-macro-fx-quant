import unittest
from datetime import datetime
from pathlib import Path

from validation.jpy_m3_schedule_gate_v1 import SLOTS, gate


class JpyM3GateTest(unittest.TestCase):
    def test_delayed_winter_slots(self):
        now = datetime.fromisoformat("2026-11-27T05:50:19+00:00")
        for cron in ("0 1 * * 1-5", "30 1 * * 1-5"):
            self.assertEqual(gate("schedule", cron, now),
                             (True, "VALID_DELAY_TOLERANT_ROME_SLOT"))
        for cron in ("0 0 * * 1-5", "30 0 * * 1-5"):
            self.assertEqual(gate("schedule", cron, now),
                             (False, "DUPLICATE_DST_SLOT"))

    def test_summer_slots_and_duplicates(self):
        now = datetime.fromisoformat("2026-07-24T03:40:00+00:00")
        for cron in ("0 0 * * 1-5", "30 0 * * 1-5"):
            self.assertTrue(gate("schedule", cron, now)[0])
        for cron in ("0 1 * * 1-5", "30 1 * * 1-5"):
            self.assertFalse(gate("schedule", cron, now)[0])

    def test_early_weekend_and_unknown(self):
        self.assertFalse(gate("schedule", "30 1 * * 1-5",
                              datetime.fromisoformat("2026-11-27T01:29:00+00:00"))[0])
        self.assertFalse(gate("schedule", "0 1 * * 1-5",
                              datetime.fromisoformat("2026-11-28T05:50:00+00:00"))[0])
        with self.assertRaises(ValueError):
            gate("schedule", "", datetime.fromisoformat("2026-11-27T05:50:00+00:00"))
        with self.assertRaises(ValueError):
            gate("schedule", "0 1 * * 1-5", datetime(2026, 11, 27, 5, 50))

    def test_explicit_validation_and_workflow_wiring(self):
        now = datetime.fromisoformat("2026-11-27T05:50:00+00:00")
        for event in ("push", "pull_request", "workflow_dispatch"):
            self.assertTrue(gate(event, "", now)[0])
        text = (Path(__file__).resolve().parents[1] /
                ".github/workflows/liquidity-jpy-m3-persistent-daily-v1.yml").read_text()
        self.assertEqual(text.count("    - cron:"), len(SLOTS))
        for cron in SLOTS:
            self.assertIn("cron: '" + cron + "'", text)
        self.assertIn("github.event.schedule", text)
        self.assertIn("validation.jpy_m3_schedule_gate_v1", text)
        self.assertIn("validation.test_jpy_m3_schedule_gate_v1", text)
        self.assertNotIn('hhmm=', text)
