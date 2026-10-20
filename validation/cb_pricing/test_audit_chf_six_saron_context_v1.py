#!/usr/bin/env python3
"""Negative tests for the CHF SIX retrospective benchmark / rights barrier."""
from __future__ import annotations

import copy
import json
import unittest

from validation.cb_pricing.audit_chf_six_saron_context_v1 import (
    FILE, SYMBOLS, audit,
)


def original():
    return json.loads(FILE.read_text(encoding="utf-8"))


class CHFSIXSARONContextTests(unittest.TestCase):
    def test_official_identifiers_licence_and_no_promotion(self):
        a = audit(original())
        self.assertEqual(a["authoritative_symbols"], sorted(SYMBOLS))
        self.assertTrue(a["retrospective_only"])
        self.assertFalse(a["forward_policy_curve_available"])
        self.assertFalse(a["ois_forward_level_available"])
        self.assertFalse(a["policy_repricing_1d_1w_available"])
        self.assertFalse(a["derived_data_rights_certified"])
        self.assertFalse(a["automated_ingestion_authorized"])
        self.assertFalse(a["official_chf_ois_promotion_eligible"])
        self.assertIsNone(a["published_market_rates"])
        self.assertFalse(a["safe_to_update_live_ois"])
        self.assertFalse(a["safe_to_change_control_room"])
        self.assertFalse(a["writes_live_data"])

    def test_mutated_isin_blocks(self):
        x = original()
        x["instruments"]["SAR3MC"]["isin"] = "CH9999999999"
        with self.assertRaisesRegex(ValueError, "source identity"):
            audit(x)

    def test_swapped_tenor_blocks(self):
        x = original()
        x["instruments"]["SAR12MC"]["tenor"] = "3M"
        with self.assertRaisesRegex(ValueError, "retrospection drift"):
            audit(x)

    def test_compound_mislabeled_as_forward_blocks(self):
        x = original()
        x["instruments"]["SAR6MC"]["forward_looking"] = True
        with self.assertRaisesRegex(ValueError, "promoted forward"):
            audit(x)

    def test_overnight_mislabeled_as_forward_blocks(self):
        x = original()
        x["instruments"]["SARON"]["type"] = "OIS_SPOT"
        with self.assertRaisesRegex(ValueError, "retrospection drift"):
            audit(x)

    def test_ois_curve_promotion_blocks(self):
        x = original()
        x["deployment"]["no_ois_curve_substitution"] = False
        with self.assertRaisesRegex(ValueError, "forbidden promotion"):
            audit(x)

    def test_repricing_signal_blocks(self):
        x = original()
        x["deployment"]["no_policy_repricing_signal"] = False
        with self.assertRaisesRegex(ValueError, "forbidden promotion"):
            audit(x)

    def test_numeric_rate_injection_blocks(self):
        x = original()
        x["instruments"]["SAR3MC"]["rate"] = 0.0123
        with self.assertRaisesRegex(ValueError, "unexpected numeric"):
            audit(x)

    def test_numeric_snapshot_field_injection_blocks(self):
        x = original()
        x["rates"] = {"SARON": 0.0123}
        with self.assertRaisesRegex(ValueError, "unexpected source contract"):
            audit(x)

    def test_live_rate_eligibility_drift_blocks(self):
        x = original()
        x["usage"]["official_numeric_snapshot_attested"] = True
        with self.assertRaisesRegex(ValueError, "rights or source data"):
            audit(x)

    def test_derived_data_clearance_unverified_blocks(self):
        x = original()
        x["usage"]["external_derived_data_right"] = "FREE"
        with self.assertRaisesRegex(ValueError, "licence clearance"):
            audit(x)

    def test_auto_download_entitlement_unverified_blocks(self):
        x = original()
        x["usage"]["automated_download_right"] = "FREE"
        with self.assertRaisesRegex(ValueError, "licence clearance"):
            audit(x)

    def test_six_host_spoof_rejected(self):
        x = original()
        x["source"]["official_page"] = (
            "https://www.six-group.com.evil.test/en/market-data/indices/switzerland/saron.html")
        with self.assertRaisesRegex(ValueError, "public SIX"):
            audit(x)

    def test_stale_old_faq_drift_rejected(self):
        x = original()
        x["source"]["licensing_faq_revision"] = "2025-10-01"
        with self.assertRaisesRegex(ValueError, "licensing revision"):
            audit(x)

    def test_unconditional_historical_display_right_rejected(self):
        x = original()
        x["usage"]["raw_historical_display_right"] = "FREE_UNRESTRICTED_REALTIME"
        with self.assertRaisesRegex(ValueError, "historical display is conditional"):
            audit(x)

    def test_instant_compound_publication_rejected(self):
        x = original()
        x["usage"]["release_latency"] = "REALTIME"
        with self.assertRaisesRegex(ValueError, "delayed compound"):
            audit(x)

    def test_unapproved_scheduling_rejected(self):
        x = original()
        x["deployment"]["no_new_scheduled_workflow"] = False
        with self.assertRaisesRegex(ValueError, "forbidden promotion"):
            audit(x)

    def test_public_dashboard_flag_rejected(self):
        x = original()
        x["usage"]["public_dashboard_permission_certified"] = True
        with self.assertRaisesRegex(ValueError, "rights or source data"):
            audit(x)

    def test_deterministic_no_data_no_input_modification(self):
        x = original()
        frozen = copy.deepcopy(x)
        first, second = audit(x), audit(x)
        self.assertEqual(first, second)
        self.assertEqual(frozen, x)
        self.assertNotIn("settlement_price", json.dumps(first))
        self.assertNotIn("rate", first)
        self.assertNotIn("as_of", first)


if __name__ == "__main__":
    unittest.main()
