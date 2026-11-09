"""Contract tests for the research-only G8 macro → CB reaction country book."""
import json
from pathlib import Path
import unittest
from itertools import combinations

PATH = Path(__file__).with_name("G8_CAUSAL_REACTION_COUNTRY_BOOK_V1.json")
FX = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
REQUIRED = {"firms", "labor", "households", "inflation", "reaction_question",
            "market_check", "mandate_focus", "bank", "official_bank_url"}


class CausalCountryBookContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(PATH.read_text(encoding="utf-8"))

    def test_g8_complete_once_and_all_twenty_eight_pairs(self):
        x = self.data
        self.assertEqual(x["schema"], "GMFQ_G8_CAUSAL_CB_REACTION_COUNTRY_BOOK_V1")
        self.assertEqual(tuple(x["country_order"]), FX)
        self.assertEqual(set(x["countries"]), set(FX))
        self.assertEqual(len(set(combinations(FX, 2))), 28)
        self.assertIn("28 unique", x["relative_pair_application"]["universe"])

    def test_economic_firms_labour_consumers_for_all_g8(self):
        for ccy, p in self.data["countries"].items():
            with self.subTest(ccy=ccy):
                self.assertTrue(REQUIRED <= set(p))
                self.assertGreaterEqual(len(p["firms"]), 3)
                self.assertGreaterEqual(len(p["labor"]), 3)
                self.assertGreaterEqual(len(p["households"]), 3)
                self.assertGreaterEqual(len(p["inflation"]), 3)
                self.assertGreaterEqual(len(p["market_check"]), 3)
                self.assertTrue(p["official_bank_url"].startswith("https://"))
                self.assertIn("?", p["reaction_question"])

    def test_causal_process_and_no_fake_production(self):
        x = self.data
        self.assertEqual(
            [r["key"] for r in x["method"]["stages"]],
            ["WHAT_IS_HAPPENING", "WHAT_IS_CHANGING",
             "CENTRAL_BANK_REACTION", "RATES_MARKET_PRICING", "RELATIVE_FX_AND_RISK"],
        )
        self.assertTrue(x["method"]["hypotheses_are_not_forecasts"])
        self.assertFalse(x["relative_pair_application"]["no_automatic_signal"] is False)
        self.assertFalse(x["scope"]["connected_to_live_site"])
        self.assertFalse(x["scope"]["prospective_tests_completed"])
        self.assertFalse(x["scope"]["production_eligible"])
        self.assertIn("NO_DASHBOARD", " ".join(
            rule.upper() for rule in x["method"]["causal_guardrails"]).replace("NEW DASHBOARDS", "NO_DASHBOARD"))

    def test_country_central_bank_mandates_not_identical(self):
        d = self.data["countries"]
        self.assertIn("dual", d["AUD"]["mandate_focus"])
        self.assertIn("exchange rate", d["CHF"]["mandate_focus"])
        self.assertIn("not a coequal", d["NZD"]["mandate_focus"])
        self.assertIn("maximum employment", d["USD"]["mandate_focus"])


if __name__ == "__main__":
    unittest.main()
