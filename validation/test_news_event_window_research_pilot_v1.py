"""Adversarial synthetic receipts: no vendor ticks are shipped in tests."""
import copy
import unittest
from validation.news_event_window_research_pilot_v1 import audit

URL = "https://datafeed.dukascopy.com/datafeed/EURUSD/2026/09/02/12h_ticks.bi5"
EVENT = {
    "scheduled_release_utc": "2026-10-02T12:30:00Z",
    "official_event_source_url": "https://www.bls.gov/news.release/empsit.toc.htm",
}


def fixture():
    return {
        "source_url": URL,
        "source_sha256": "a" * 64,  # Synthetic dummy, not a downloaded source hash.
        "source_bytes_n": 58963,
        "tick_count": 13340,
        "source_bytes_externally_retrieved": True,  # Simulated external receipt.
        "transport_receipt": {
            "http_status": 200, "effective_url": URL,
            "content_length": 58963,
        },
        "release_at": "2026-10-02T12:30:00+00:00",
        "pre_0825_new_york": {
            "observed_at_utc": "2026-10-02T12:24:58.327+00:00",
            "bid": 1.12275, "ask": 1.12277, "mid": 1.12276,
        },
        "post_0835_new_york": {
            "observed_at_utc": "2026-10-02T12:34:59.859+00:00",
            "bid": 1.12481, "ask": 1.12486, "mid": 1.124835,
        },
        "mid_move_pips": 20.75,
        "source_license_independently_certified": True,  # Untrusted assertion!
    }


class EventWindowResearchTest(unittest.TestCase):
    def test_descriptive_observation_does_not_certify_causality_or_licence(self):
        out = audit(fixture(), EVENT)
        self.assertEqual(out["status"], "DESCRIPTIVE_FX_WINDOW_RIGHTS_UNVERIFIED")
        self.assertEqual(out["delta_pips"], 20.75)
        self.assertTrue(out["intraday_fx_descriptive_window"])
        self.assertFalse(out["source_usage_rights_independently_verified"])
        self.assertFalse(out["independently_verified_release_instant"])
        self.assertEqual(out["causal_attribution"], "NOT_ESTABLISHED")
        self.assertEqual(out["intraday_ois"], "NOT_AVAILABLE")
        self.assertEqual(out["intraday_government_2y"], "NOT_AVAILABLE")
        self.assertFalse(out["eligible_for_backtest"])
        self.assertFalse(out["safe_to_publish_live_data"])
        self.assertFalse(out["writes_live_data"])

    def assert_invalid(self, patch, where="probe"):
        p, e = fixture(), copy.deepcopy(EVENT)
        patch(p if where == "probe" else e)
        out = audit(p, e)
        self.assertFalse(out["intraday_fx_descriptive_window"], out)
        self.assertFalse(out["safe_to_publish_live_data"])

    def test_no_claim_if_transport_unproven(self):
        p = fixture()
        p["transport_receipt"] = None
        self.assertEqual(audit(p, EVENT)["status"], "NO_EXTERNAL_TRANSPORT_RECEIPT")

    def test_fake_hash(self):
        self.assert_invalid(lambda p: p.update(source_sha256="not-a-sha"))

    def test_source_mismatch(self):
        self.assert_invalid(lambda p: p["transport_receipt"].update(effective_url="https://example.com"))

    def test_malformed_bid_ask(self):
        self.assert_invalid(lambda p: p["post_0835_new_york"].update(ask=1.1))

    def test_inconsistent_mid(self):
        self.assert_invalid(lambda p: p["pre_0825_new_york"].update(mid=1.2))

    def test_stale_pre_event_quote(self):
        self.assert_invalid(lambda p: p["pre_0825_new_york"].update(observed_at_utc="2026-10-02T12:14:00Z"))

    def test_post_event_quote_before_release(self):
        self.assert_invalid(lambda p: p["post_0835_new_york"].update(observed_at_utc="2026-10-02T12:20:00Z"))

    def test_timezone_naive_is_not_reinterpreted_as_utc(self):
        self.assert_invalid(lambda p: p["pre_0825_new_york"].update(observed_at_utc="2026-10-02T12:24:58"))

    def test_future_day_or_wrong_event_timestamp(self):
        self.assert_invalid(lambda e: e.update(scheduled_release_utc="2026-10-03T12:30:00Z"), "event")

    def test_unrelated_official_source(self):
        self.assert_invalid(lambda e: e.update(official_event_source_url="https://example.com/news"), "event")

    def test_wrong_month_in_bi5_url(self):
        self.assert_invalid(lambda p: p.update(source_url=URL.replace("/2026/09/02/", "/2026/08/02/")))

    def test_claimed_pips_must_match_bid_ask(self):
        self.assert_invalid(lambda p: p.update(mid_move_pips=999))

    def test_missing_quote_and_missing_probe(self):
        self.assert_invalid(lambda p: p.pop("pre_0825_new_york"))
        self.assertEqual(audit(None, EVENT)["status"], "MISSING_SOURCE")


if __name__ == "__main__":
    unittest.main()
