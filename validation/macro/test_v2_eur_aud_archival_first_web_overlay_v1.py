"""139 individually archived EUR/AUD first-publication records, fail closed."""
from __future__ import annotations

import base64
import copy
import json
import lzma
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from validation.macro.v2_eur_aud_archival_first_web_overlay_v1 import (
    ENTRIES, ROOT, archived_overlay, rows_and_events
)
from validation.macro.v2_g8_labour_inflation_web_asof_timeline_v1 import (
    run as timeline_run
)


class OriginalCsvEurostatAbsArchive(unittest.TestCase):
    def test_full_139_source_records_and_issuer_publisher_dates_are_distinct(self):
        report = archived_overlay(as_of="2026-10-27T00:00:00Z")
        self.assertEqual(report["summary"]["pinned_original_first_web_rows"], 139)
        self.assertEqual(report["summary"]["eur_inflation_monthly"], 105)
        self.assertEqual(report["summary"]["aud_inflation_quarterly"], 34)
        self.assertEqual(report["summary"]["source_archival_receipts_reconciled"], 2)
        self.assertEqual(report["summary"]["official_source_csvs_permanently_committed_in_repo"], 2)
        for key, item in report["histories"].items():
            spec = ENTRIES[key]
            self.assertEqual(item["reference_periods"], spec["count"])
            self.assertEqual(item["frequency"], spec["frequency"])
            self.assertEqual(item["source_csv_sha256"], spec["original_csv_sha256"])
            self.assertEqual(item["source_semantic_sha256"],
                             spec["expected_semantic_hash"])
            self.assertEqual(item["visible_initial_web_periods"], spec["count"])
            self.assertTrue(all(event["source_url"].startswith("https://")
                                and len(event["archived_source_sha256"]) == 64
                                and event["stage"] == "FIRST_WEB"
                                and event["PIT_history_replay_for_trading_authorized"] is False
                                for event in item["events"]))
        for name in ("safe_to_publish_new_D", "safe_to_change_28_pairs",
                     "safe_for_beta", "safe_for_forward", "writes_live_data"):
            self.assertFalse(report[name])
        self.assertFalse(report["historical_aggregate_score_pit_certified"])

    def test_no_flash_or_cpi_early_visibility_from_historic_issuer_clock(self):
        eur = rows_and_events("EUR.inflation")
        au = rows_and_events("AUD.inflation")
        e = eur["events"][-1]
        self.assertEqual(e["reference_period"], "2026-09")
        self.assertEqual(e["reported_value"], 3.8)
        self.assertEqual(e["visible_from_utc"], "2026-10-03T00:00:00+00:00")
        self.assertEqual(e["publisher_clock_quality"], "CONSERVATIVE_NEXT_UTC_DAY")
        a = au["events"][-1]
        self.assertEqual(a["reference_period"], "2026-06")
        self.assertEqual(a["reported_value"], 3.9)
        self.assertEqual(a["visible_from_utc"], "2026-07-29T01:30:00+00:00")
        self.assertEqual(a["publisher_clock_quality"],
                         "ABS_PUBLISHED_LOCAL_TIME_IANA_SYDNEY_CANBERRA_CONVERTED_TO_UTC")
        earliest = au["events"][0]
        self.assertEqual(earliest["reference_period"], "2018-03")
        self.assertEqual(earliest["publisher_clock_quality"],
                         "ABS_PUBLISHED_LOCAL_TIME_IANA_SYDNEY_CANBERRA_CONVERTED_TO_UTC")
        before_eur = archived_overlay(as_of="2026-10-02T23:59:59Z")
        self.assertEqual(
            before_eur["histories"]["EUR.inflation"]["most_recent_first_web_at_cutoff"]["reference_period"],
            "2026-08")
        before_aud = archived_overlay(as_of="2026-07-29T01:29:59Z")
        self.assertEqual(
            before_aud["histories"]["AUD.inflation"]["most_recent_first_web_at_cutoff"]["reference_period"],
            "2026-03")
        self.assertNotEqual(before_eur["histories"]["EUR.inflation"]
                            ["most_recent_first_web_at_cutoff"]["reported_value"], 3.8)

    def test_archived_csvs_are_permanently_readable_from_repository_not_actions(self):
        for key, spec in ENTRIES.items():
            path = ROOT / "validation/macro/fixtures" / spec["fixture"]
            self.assertTrue(path.is_file())
            self.assertLess(path.stat().st_size, 13000)
            self.assertEqual(len(rows_and_events(key)["events"]), spec["count"])

    def test_timeline_adds_independent_canonical_layer_but_preserves_old_candidates(self):
        r = timeline_run(start="2026-10-01", end="2026-10-27")
        self.assertEqual(r["summary"]["additional_canonical_EUR_AUD_initial_publisher_periods_loaded"], 139)
        self.assertEqual(r["summary"]["archived_EUR_months"], 105)
        self.assertEqual(r["summary"]["archived_AUD_quarters"], 34)
        self.assertEqual(r["summary"]["candidate_source_mismatches_or_frequency_mismatches"], 4)
        self.assertEqual(r["summary"]["joint_PIT_training_histories_certified"], 0)
        self.assertEqual(r["source_catalogue"]["AUD.inflation"]["candidate_frequency"], "M")
        self.assertEqual(
            r["canonical_EUR_AUD_first_web_archival_overlay"]["histories"]["AUD.inflation"]["frequency"],
            "Q")
        first_day = r["daily_web_release_snapshots"][0]
        last_day = r["daily_web_release_snapshots"][-1]
        self.assertEqual(first_day["canonical_EUR_AUD_archival_first_web_overlay"]
                         ["EUR.inflation"]["most_recent_canonical_archival_economic_period"], "2026-08")
        self.assertEqual(last_day["canonical_EUR_AUD_archival_first_web_overlay"]
                         ["EUR.inflation"]["most_recent_canonical_archival_economic_period"], "2026-09")
        self.assertEqual(last_day["canonical_EUR_AUD_archival_first_web_overlay"]
                         ["AUD.inflation"]["most_recent_canonical_archival_economic_period"], "2026-06")
        self.assertFalse(r["safe_to_publish_new_D"])

    def test_tamper_first_publisher_csv_receipt_or_original_compression_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for key, spec in ENTRIES.items():
                d = root / "validation/macro/fixtures" / spec["fixture"]
                d.parent.mkdir(parents=True, exist_ok=True)
                d.write_bytes((ROOT / "validation/macro/fixtures" / spec["fixture"]).read_bytes())
                evidence = root / "validation/macro" / spec["evidence"]
                evidence.parent.mkdir(parents=True, exist_ok=True)
                evidence.write_bytes((ROOT / "validation/macro" / spec["evidence"]).read_bytes())
            # Flip a REAL first-publisher reported EUR value in original CSV.
            spec = ENTRIES["EUR.inflation"]
            fixture = root / "validation/macro/fixtures" / spec["fixture"]
            raw = lzma.decompress(base64.b64decode("".join(fixture.read_text().split())))
            self.assertIn(b"2018-01,1.3", raw)
            fake = raw.replace(b"2018-01,1.3", b"2018-01,8.3", 1)
            fixture.write_text(base64.b64encode(lzma.compress(fake)).decode())
            with self.assertRaisesRegex(ValueError, "ORIGINAL CSV bytes"):
                rows_and_events("EUR.inflation", root=root)
            fixture.write_bytes((ROOT / "validation/macro/fixtures" / spec["fixture"]).read_bytes())
            ev = root / "validation/macro" / spec["evidence"]
            evidence = json.loads(ev.read_text())
            evidence["semantic_rowset_sha256"] = "f" * 64
            ev.write_text(json.dumps(evidence))
            with self.assertRaisesRegex(ValueError, "receipt not identical"):
                rows_and_events("EUR.inflation", root=root)

    def test_no_core_D_or_28pair_modifications(self):
        base = ROOT / "live_data/sections"
        keep = ("D.json", "PAIR_SETUP_OPERATIONAL_VIEW.json")
        before = {p: (base / p).read_bytes() for p in keep}
        archived_overlay()
        timeline_run(start="2026-10-25", end="2026-10-27")
        after = {p: (base / p).read_bytes() for p in keep}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
