"""V11 offline issuer contracts — do not confuse GDP vintages, quarters or methods."""
from __future__ import annotations

import copy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import tempfile
import unittest

from validation.macro import capture_uk_ch_gdp_official_firstseen_v11 as v11
from validation.macro.freeze_exact_metric_forecasts_v9 import read_rows, LEDGER
from validation.macro.freeze_pre_release_consensus_v1 import digest

OFFICIAL = json.loads(v11.OFFICIAL.read_text(encoding="utf-8"))
FORECASTS = read_rows(LEDGER)
BEFORE = datetime(2026, 11, 9, 16, 30, tzinfo=timezone.utc)
UK_RELEASED = datetime(2026, 11, 12, 7, 5, tzinfo=timezone.utc)
CH_RELEASED = datetime(2026, 11, 16, 8, 5, tzinfo=timezone.utc)
CH_OBSERVED = CH_RELEASED + timedelta(seconds=4)
UK_OBSERVED = UK_RELEASED + timedelta(seconds=4)
ONS_Q3 = b"""
<html><body><h1>GDP first quarterly estimate, UK: July to September 2026</h1>
<p>Release date: 12 November 2026</p>
<h2>1. Main points</h2>
<p>UK real gross domestic product (GDP) is estimated to have increased by
0.5% in Quarter 3 (July to Sept) 2026, following growth of 0.6% in Quarter 2.</p>
<p>Real GDP per head is estimated to have declined by 0.1%.</p>
<h2>2. Headline GDP figures</h2><p>GDP increased 0.5%.</p>
</body></html>"""
ONS_Q2 = ONS_Q3.replace(b"July to September", b"April to June").replace(
    b"July to Sept", b"Apr to June").replace(
    b"12 November 2026", b"13 August 2026").replace(
    b"Quarter 3", b"Quarter 2")
SECO_Q3 = b"""
<html><body><h1>GDP flash for the third quarter of 2026: Moderate growth</h1>
<p>According to the early estimate of Switzerland's quarterly real GDP
approximately 45 days after the quarter end ('GDP flash'), the Swiss
economy is estimated to have grown by 0.3% in the third quarter of 2026.
Services contributed to growth.</p>
<h2>Further information</h2><p>Q3 flash may be revised.</p>
<h2>Publication schedule</h2><p>4th quarter 2026</p>
</body></html>"""
SECO_Q2 = SECO_Q3.replace(b"third quarter of 2026", b"second quarter of 2026")


def fake_fetch(url, host):
    assert url == next(t["source_url"] for t in v11.TARGETS.values() if t["host"] == host)
    return (ONS_Q3 if host == "www.ons.gov.uk" else SECO_Q3), url


class GDPFirstSeenV11Tests(unittest.TestCase):
    def test_official_calendar_metric_identity_and_clocks(self):
        c = v11.release_contracts(OFFICIAL)
        self.assertEqual(set(c), set(v11.ORDER))
        self.assertEqual(c["UK_REAL_GDP_PRELIM_QOQ_SA"]["release"],
                         datetime(2026, 11, 12, 7, 0, tzinfo=timezone.utc))
        self.assertEqual(c["CH_REAL_GDP_FLASH_QOQ"]["release"],
                         datetime(2026, 11, 16, 8, 0, tzinfo=timezone.utc))

    def test_before_publication_no_ons_no_seco_http(self):
        calls = []
        def never(url, host):
            calls.append((url,host))
            raise AssertionError("No future actual downloads")
        records, receipt = v11.capture(OFFICIAL, FORECASTS, [], BEFORE, never)
        self.assertEqual(records, [])
        self.assertEqual(calls, [])
        self.assertEqual(set(receipt["states"].values()), {"BEFORE_RELEASE_NO_HTTP"})

    def test_ons_q3_only_exact_first_quarterly_and_not_monthly(self):
        self.assertEqual(v11.parse_ons(ONS_Q3), 0.5)
        for bad in (
            ONS_Q2,
            ONS_Q3.replace(b"first quarterly estimate", b"quarterly national accounts"),
            ONS_Q3.replace(b"12 November 2026", b"11 November 2026"),
            ONS_Q3.replace(b"UK real gross domestic product", b"UK nominal GDP"),
            ONS_Q3.replace(b"in Quarter 3", b"in Quarter 2"),
            ONS_Q3.replace(b"Release date: 12 November 2026",
                           b"Release date: 12 November 2026"
                           b"<p>This release is not yet published</p>"),
            ONS_Q3.replace(b"0.5% in Quarter 3", b"0.5% in the three months to September"),
        ):
            with self.subTest(source=bad[:70]), self.assertRaises(v11.Pending):
                v11.parse_ons(bad)

    def test_ons_gdp_decrease_and_absent_rate(self):
        self.assertEqual(v11.parse_ons(
            ONS_Q3.replace(b"increased by", b"contracted by")), -0.5)
        with self.assertRaises(v11.Pending):
            v11.parse_ons(ONS_Q3.replace(b"0.5%", b"not supplied", 1))

    def test_seco_q3_not_old_q2_or_schedule_stub(self):
        self.assertEqual(v11.parse_seco(SECO_Q3), 0.3)
        for bad in (
            SECO_Q2,
            SECO_Q3.replace(b"grown by 0.3%", b"grown by unknown"),
            SECO_Q3.replace(b"third quarter of 2026", b"fourth quarter of 2026",1),
            SECO_Q3.replace(b"Swiss", b"German"),
        ):
            with self.subTest(source=bad[:70]),self.assertRaises(v11.Pending):
                v11.parse_seco(bad)

    def test_only_uk_after_uk_publication_and_links_v9(self):
        records, receipt = v11.capture(
            OFFICIAL, FORECASTS, [], UK_RELEASED, fake_fetch,
            observed_clock=lambda: UK_OBSERVED)
        self.assertEqual(len(records), 1)
        r = records[0]
        self.assertEqual(r["metric_id"], "UK_REAL_GDP_PRELIM_QOQ_SA")
        self.assertEqual(r["actual_percent"], 0.5)
        self.assertEqual(r["v9_secondary_forecast_pct"], 0.7)
        self.assertEqual(r["actual_minus_v9_secondary_pp"], -0.2)
        self.assertEqual(receipt["states"]["CH_REAL_GDP_FLASH_QOQ"],
                         "BEFORE_RELEASE_NO_HTTP")
        self.assertIsNone(r["certified_macro_surprise"])
        self.assertIsNone(r["FX_signal"])

    def test_swiss_release_uses_separate_exact_metric_without_unverified_forecast(self):
        first, _ = v11.capture(
            OFFICIAL, FORECASTS, [], UK_RELEASED, fake_fetch,
            observed_clock=lambda: UK_OBSERVED)
        rows, receipt = v11.capture(
            OFFICIAL, FORECASTS, first, CH_RELEASED, fake_fetch,
            observed_clock=lambda: CH_OBSERVED)
        self.assertEqual(len(rows), 2)
        self.assertEqual(receipt["new_official_metric_actuals"], 1)
        self.assertEqual(rows[1]["actual_percent"], 0.3)
        self.assertIsNone(rows[1]["v9_secondary_forecast_pct"])
        self.assertIsNone(rows[1]["actual_minus_v9_secondary_pp"])
        self.assertEqual(rows[1]["metric_unit_hypothesis"], "PCT_QOQ")
        self.assertTrue(rows[1]["gdp_qoq_source_adjustment_not_independently_verified"])
        v11.validate_actuals(rows, OFFICIAL, FORECASTS)

    def test_missing_issuer_source_no_actual_and_no_false_zero(self):
        def down(url,host): raise OSError("offline")
        rows, receipt = v11.capture(
            OFFICIAL, FORECASTS, [], CH_RELEASED, down)
        self.assertEqual(rows, [])
        self.assertEqual(set(receipt["states"].values()),
                         {"SOURCE_NOT_AVAILABLE_OR_TARGET_SERIES_NOT_CERTIFIED"})
        self.assertEqual(receipt["certified_macro_surprises"], 0)

    def test_first_source_hash_remains_immutable_after_future_change(self):
        records, _ = v11.capture(
            OFFICIAL, FORECASTS, [], CH_RELEASED, fake_fetch,
            observed_clock=lambda: CH_OBSERVED)
        def never(url,host): raise AssertionError("Archived must not re-fetch")
        same, receipt = v11.capture(
            OFFICIAL, FORECASTS, records, CH_RELEASED + timedelta(hours=1), never)
        self.assertEqual(same, records)
        self.assertEqual(receipt["new_official_metric_actuals"], 0)
        self.assertEqual(set(receipt["states"].values()),
                         {"ACTUAL_ALREADY_FIRST_OBSERVED_NO_HTTP"})

    def test_wrong_redirect_date_or_clock_rejected(self):
        # Wrong final URL is a source failure, never a certified actual.
        rows, receipt = v11.capture(
            OFFICIAL, FORECASTS, [], CH_RELEASED,
            fetch=lambda url,host: (SECO_Q3, "https://not-seco.example.com"),
            observed_clock=lambda: CH_OBSERVED)
        self.assertEqual(rows, [])
        with self.assertRaises(ValueError):
            v11.capture(OFFICIAL, FORECASTS, [], CH_RELEASED, fake_fetch,
                        observed_clock=lambda: CH_RELEASED-timedelta(minutes=1))

    def test_archive_signature_and_semantic_status_cannot_change(self):
        rows, _ = v11.capture(
            OFFICIAL, FORECASTS, [], CH_RELEASED, fake_fetch,
            observed_clock=lambda: CH_OBSERVED)
        edits = (
            lambda x: x[0].update(actual_percent=9.8),
            lambda x: x[0].update(FX_signal="GBPUSD_UP"),
            lambda x: x[0].update(publisher_first_delivery_PIT_verified=True),
            lambda x: x[0].update(metric_id="UK_MONTHLY_GDP"),
        )
        for edit in edits:
            broken = copy.deepcopy(rows)
            edit(broken)
            with self.subTest(edit=str(edit)), self.assertRaises(ValueError):
                v11.validate_actuals(broken, OFFICIAL, FORECASTS)
        broken = copy.deepcopy(rows)
        broken[0]["FX_signal"] = "GBPUSD_UP"
        broken[0]["record_sha256"] = digest({
            k:v for k,v in broken[0].items() if k!="record_sha256"})
        with self.assertRaisesRegex(ValueError,"unsupported"):
            v11.validate_actuals(broken, OFFICIAL, FORECASTS)

    def test_no_write_to_legacy_and_research_idempotence(self):
        prior = LEDGER.read_bytes()
        legacy = (v11.ROOT / "validation/macro/MACRO_PRE_RELEASE_CONSENSUS_LEDGER_V1.jsonl").read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "actual.jsonl"
            receipt = v11.run(actual_path=out, now=BEFORE)
            self.assertEqual(receipt["new_official_metric_actuals"], 0)
            self.assertFalse(out.exists())
            a = v11.run(actual_path=out, now=CH_RELEASED, fetch=fake_fetch,
                        observed_clock=lambda:CH_OBSERVED)
            self.assertEqual(a["new_official_metric_actuals"], 2)
            raw = out.read_bytes()
            again = v11.run(actual_path=out, now=CH_RELEASED, fetch=fake_fetch,
                            observed_clock=lambda:CH_OBSERVED)
            self.assertEqual(again["new_official_metric_actuals"], 0)
            self.assertEqual(out.read_bytes(),raw)
        self.assertEqual(LEDGER.read_bytes(),prior)
        self.assertEqual((v11.ROOT / "validation/macro/MACRO_PRE_RELEASE_CONSENSUS_LEDGER_V1.jsonl").read_bytes(),legacy)


if __name__ == "__main__":
    unittest.main()
