"""Fail-closed source catalogue and scheduled embargo clock audit (offline)."""
import copy
import json
import unittest

from validation.news_event_source_readiness_gate_v1 import REGISTRY, audit


class SourceReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = json.loads(REGISTRY.read_text(encoding="utf-8"))

    def check_invalid(self, mutate):
        data = copy.deepcopy(self.reference)
        mutate(data)
        with self.assertRaises(ValueError):
            audit(data)

    def test_official_calendar_is_schedule_not_actual_delivery(self):
        result = audit(self.reference)
        self.assertEqual(result["state"], "BLOCKED_NOT_CERTIFIED")
        self.assertEqual(result["scheduled_embargo_utc"], "2026-10-02T12:30:00Z")
        self.assertTrue(result["scheduled_embargo_verified_against_official_archive"])
        self.assertFalse(result["actual_first_public_delivery_verified"])
        self.assertFalse(result["publisher_wall_clock_is_actual_delivery_proof"])
        self.assertFalse(result["fx_source_usage_rights_verified"])
        self.assertFalse(result["short_rate_futures_intraday_acquired"])
        self.assertFalse(result["treasury_2y_intraday_acquired"])
        self.assertFalse(result["eligible_for_score"])
        self.assertFalse(result["eligible_for_backtest"])
        self.assertFalse(result["eligible_for_live_data"])
        self.assertEqual(result["market_reaction"], "NOT_CERTIFIED")

    def test_invalid_schema(self):
        self.check_invalid(lambda d: d.update(schema="PRODUCTION"))

    def test_no_hidden_promotion_into_production(self):
        self.check_invalid(lambda d: d.update(scope="PRODUCTION"))

    def test_wrong_employment_release(self):
        self.check_invalid(lambda d: d["event"].update(
            official_archived_release_url="https://www.bls.gov/news.release/archives/empsit_09042026.htm"))

    def test_official_publisher_accession_required(self):
        self.check_invalid(lambda d: d["event"].update(official_release_id="OTHER"))

    def test_wrong_local_timezone(self):
        self.check_invalid(lambda d: d["event"].update(timezone="Europe/Rome"))

    def test_wrong_utc_conversion_and_dst(self):
        self.check_invalid(lambda d: d["event"].update(expected_scheduled_utc="2026-10-02T13:30:00Z"))

    def test_daily_or_rss_timestamp_cannot_be_instant_proof(self):
        self.check_invalid(lambda d: d["event"].update(
            independently_verified_first_public_delivery_utc="2026-10-02T12:30:00Z"))

    def test_unsupported_external_delivery_receipt(self):
        self.check_invalid(lambda d: d["event"].update(first_public_delivery_receipt={"pretend": True}))

    def test_marking_dukascopy_licensed_fails(self):
        self.check_invalid(lambda d: d["providers"][0].update(commercial_use_rights="GRANTED"))

    def test_public_data_distribution_rights_are_separate(self):
        self.check_invalid(lambda d: d["providers"][1].update(publication_rights="GRANTED"))

    def test_pretending_ticks_are_authorized_fails(self):
        self.check_invalid(lambda d: d["providers"][0].update(raw_ticks_authorized_retained=True))

    def test_proof_flag_cannot_be_self_attested(self):
        self.check_invalid(lambda d: d["providers"][0].update(
            cross_event_quote_receipt_independently_verified=True))

    def test_catalogue_is_not_market_data(self):
        self.check_invalid(lambda d: d["providers"][1].update(acquisition_state="TRANSPORT_PROBED_RESEARCH_ONLY"))

    def test_no_missing_fx_or_rates_source(self):
        self.check_invalid(lambda d: d["providers"].pop())

    def test_no_duplicate_source(self):
        self.check_invalid(lambda d: d["providers"].__setitem__(2, copy.deepcopy(d["providers"][0])))

    def test_no_redirected_vendor_host(self):
        self.check_invalid(lambda d: d["providers"][1].update(source_url="https://fake-cme.com/data"))

    def test_no_userinfo_trick_in_host(self):
        self.check_invalid(lambda d: d["providers"][2].update(
            source_url="https://evil.example@cmegroupclientsite.atlassian.net/foo"))

    def test_unlicensed_automated_fetch_stays_blocked(self):
        result = audit(self.reference)
        self.assertFalse(result["dukascopy_automated_access_enabled"])
        self.assertFalse(result["dukascopy_prior_written_consent_verified"])
        self.assertIn("DUKASCOPY_AUTOMATED_ACCESS_PRIOR_WRITTEN_CONSENT_ABSENT", result["blocked_by"])
        self.check_invalid(lambda d: d["providers"][0].update(automated_fetch_enabled=True))
        self.check_invalid(lambda d: d["providers"][0].update(automation_permission_verified=True))

    def test_original_three_catalog_sources_unacquired(self):
        results = [p["acquisition_state"] for p in self.reference["providers"]]
        self.assertEqual(results.count("CATALOG_ONLY_NOT_ACQUIRED"), 3)


if __name__ == "__main__":
    unittest.main()
