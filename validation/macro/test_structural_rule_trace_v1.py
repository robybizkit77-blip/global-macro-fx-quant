#!/usr/bin/env python3
"""Reference policy fixtures: independent of DOM and canonical browser calls."""
import unittest

from validation.macro.verify_structural_rule_trace_v1 import (
    category, derive_pair, direction, polarity, policy,
)


def c(macro, policy_value, rate):
    return {"macro": macro, "policy": policy_value, "rate2y": rate}


class StructuralRulesOracleTests(unittest.TestCase):
    def test_macro_label_direction(self):
        self.assertEqual(polarity(["Favorevole"]), 1)
        self.assertEqual(polarity(["Contrario"]), -1)
        self.assertEqual(polarity(["Divergente"]), 0)
        self.assertEqual(polarity(["Neutrale"]), 0)

    def test_sfavorevole_substring_is_not_accepted_as_favorable(self):
        with self.assertRaisesRegex(ValueError, "ambiguous sfavorevole"):
            polarity(["Sfavorevole"])

    def test_front_end_overrides_opposite_cb(self):
        layers = {"rates": ["Contrario"], "cb": ["Favorevole"]}
        self.assertEqual(policy(layers), -1)

    def test_cb_fills_truly_neutral_rates_only(self):
        self.assertEqual(policy({"rates": ["Neutrale"], "cb": ["Favorevole"]}), 1)

    def test_divergent_rates_neutralize_cb_even_when_hawkish(self):
        self.assertEqual(policy({"rates": ["Divergente"], "cb": ["Favorevole"]}), 0)

    def test_all_five_currency_structure_categories(self):
        self.assertEqual(category(1, 1), "FORTE")
        self.assertEqual(category(-1, -1), "FRAGILE")
        self.assertEqual(category(1, 0), "COSTRUTTIVA")
        self.assertEqual(category(0, -1), "DEBOLE")
        self.assertEqual(category(1, -1), "MISTA")

    def test_confirmed_both_pillars(self):
        x = derive_pair("EUR", "USD", c(1, 1, 3.2), c(0, 0, 4.5))
        self.assertEqual(x["favored"], "EUR")
        self.assertEqual(x["quality"], "CONTRASTO STRUTTURALE FORTE")

    def test_macro_only_is_partial(self):
        x = derive_pair("EUR", "USD", c(1, 0, 3.2), c(-1, 0, 4.5))
        self.assertEqual(x["favored"], "EUR")
        self.assertEqual(x["quality"], "VANTAGGIO RELATIVO PARZIALE")

    def test_divided_pillars_no_trade_bias(self):
        x = derive_pair("EUR", "USD", c(1, -1, 3.2), c(-1, 1, 4.5))
        self.assertEqual(x["favored"], "—")
        self.assertEqual(x["quality"], "PILASTRI DIVISI")

    def test_material_2y_is_not_automatic_direction(self):
        x = derive_pair("EUR", "USD", c(0, 0, 3.1), c(0, 0, 4.4))
        self.assertEqual(x["favored"], "—")
        self.assertEqual(x["quality"], "SEPARAZIONE RATES MATERIALE")
        self.assertEqual(x["rate_side"], "USD")

    def test_small_rate_gap_no_contrast(self):
        x = derive_pair("EUR", "USD", c(0, 0, 3.1), c(0, 0, 3.7))
        self.assertEqual(x["favored"], "—")
        self.assertEqual(x["quality"], "NESSUN CONTRASTO")

    def test_null_yield_must_not_be_treated_as_zero(self):
        with self.assertRaisesRegex(ValueError, "missing rate2y"):
            derive_pair("EUR", "USD", c(0, 0, None), c(0, 0, 3.5))

    def test_direction_never_uses_relative_scoring_average(self):
        self.assertEqual(direction(-1, 1), "B")
        self.assertEqual(direction(0, 0), "TIE")
        self.assertEqual(direction(1, -1), "A")


if __name__ == "__main__":
    unittest.main()
