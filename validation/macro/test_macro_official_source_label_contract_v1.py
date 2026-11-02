"""Official-label alignment must not admit arbitrary source identity drift."""
import copy
import unittest
from validation.macro.check_macro_source_registry import (
    REGISTRY, HEATMAP, load, certified_adapter_contract,
    checked_public_source_label,
)

class SourceLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = load(REGISTRY)["series"]
        cls.heat = load(HEATMAP)["currencies"]

    def check(self, key, row=None, presented=None):
        c, d = key.split(".")
        row = copy.deepcopy(row if row is not None else self.reg[key])
        h = {"source": presented if presented is not None
             else self.heat[c][d]["source"]}
        _, certified = certified_adapter_contract(key, row)
        return checked_public_source_label(key, row, h, certified)

    def test_eurostat_direct_official_adapter(self):
        self.assertEqual(
            self.check("EUR.labour"),
            "CERTIFIED_OFFICIAL_ADAPTER_LABEL_LEGACY_TRANSPORT_RETAINED")
        r = copy.deepcopy(self.reg["EUR.labour"])
        r["certified_adapter"]["source"] = "Unregistered vendor"
        with self.assertRaisesRegex(ValueError, "source drift"):
            self.check("EUR.labour", r)
        r = copy.deepcopy(self.reg["EUR.labour"])
        r["source_adapter_status"] = "NEEDS_OFFICIAL_DIRECT_TRANSPORT"
        with self.assertRaisesRegex(ValueError, "source drift"):
            self.check("EUR.labour", r)
        with self.assertRaisesRegex(ValueError, "source drift"):
            self.check("EUR.labour", presented="Secondary unknown provider")

    def test_japan_direct_survey_same_publisher(self):
        self.assertEqual(
            self.check("JPY.labour"),
            "SAME_OFFICIAL_JPY_ESTAT_LABOUR_SURVEY_SOURCE")
        r = copy.deepcopy(self.reg["JPY.labour"])
        r["adapter"] = "unregistered/adapter.py"
        with self.assertRaisesRegex(ValueError, "source drift"):
            self.check("JPY.labour", r)
        r = copy.deepcopy(self.reg["JPY.labour"])
        r["transport_class"] = "SECONDARY_MIRROR"
        with self.assertRaisesRegex(ValueError, "source drift"):
            self.check("JPY.labour", r)
        with self.assertRaisesRegex(ValueError, "source drift"):
            self.check("JPY.labour", presented="Unverified exchange proxy")

    def test_nzd_legacy_mirror_needs_certified_adapter(self):
        self.assertEqual(
            self.check("NZD.inflation"),
            "CERTIFIED_OFFICIAL_ADAPTER_LABEL_LEGACY_TRANSPORT_RETAINED")
        r = copy.deepcopy(self.reg["NZD.inflation"])
        r.pop("certified_adapter")
        with self.assertRaisesRegex(ValueError, "source drift"):
            self.check("NZD.inflation", r)

    def test_plain_canonical_labels_unmodified(self):
        self.assertEqual(self.check("USD.inflation"), "CANONICAL_SOURCE_LABEL")

if __name__ == "__main__":
    unittest.main()
