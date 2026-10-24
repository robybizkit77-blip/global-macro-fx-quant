#!/usr/bin/env python3
"""Fail-closed separation of the legacy NZD mirror and verified direct adapter."""
import copy
import json
import unittest

from validation.macro.check_macro_source_registry import (
    REGISTRY, HEATMAP, checked_public_source_label,
    certified_adapter_contract, load, main,
)


class SourceLabelAndTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry=load(REGISTRY)
        cls.heatmap=load(HEATMAP)
        cls.nz=cls.registry["series"]["NZD.inflation"]
        cls.hm=cls.heatmap["currencies"]["NZD"]["inflation"]

    def test_nzd_inflation_original_mirror_and_official_direct_adapter_not_conflated(self):
        row=self.nz
        self.assertEqual(row["source"],"Stats NZ via Figure.NZ mirror")
        self.assertEqual(row["transport_class"],"SECONDARY_MIRROR")
        self.assertEqual(row["source_adapter_status"],"READY")
        self.assertEqual(self.hm["source"],"Stats NZ")
        eff, adapter=certified_adapter_contract("NZD.inflation",row)
        self.assertEqual(eff,"OFFICIAL_DIRECT")
        self.assertEqual(adapter["source"],"Stats NZ")
        self.assertTrue(adapter["read_only"])
        self.assertTrue(adapter["dynamic_release_discovery"])
        self.assertEqual(
            checked_public_source_label("NZD.inflation",row,self.hm,adapter),
            "CERTIFIED_OFFICIAL_ADAPTER_LABEL_LEGACY_TRANSPORT_RETAINED",
        )
        self.assertFalse(self.registry["rules"]["automatic_publication"])
        self.assertEqual(self.hm["series_id"],row["series_id"])
        self.assertEqual(self.hm["transformation"],row["transformation"])

    def test_all_other_fifteen_labels_still_match_registered_legacy_name(self):
        count=0
        for key,row in sorted(self.registry["series"].items()):
            if key=="NZD.inflation":continue
            cc,pillar=key.split(".")
            label=self.heatmap["currencies"][cc][pillar]
            _,adapter=certified_adapter_contract(key,row)
            with self.subTest(key=key):
                self.assertEqual(
                    checked_public_source_label(key,row,label,adapter),
                    "CANONICAL_SOURCE_LABEL")
            count+=1
        self.assertEqual(count,15)

    def test_a_direct_adaptor_must_not_make_any_spoofed_source_official(self):
        row=self.nz
        hm=self.hm
        _,adapter=certified_adapter_contract("NZD.inflation",row)
        cases=[
            ({**row,"source_adapter_status":"NEEDS_SOURCE_ADAPTER"},hm,adapter),
            ({**row,"transport_class":"OFFICIAL_DIRECT"},hm,adapter),
            (row,{"source":"Some Arbitrary Private Service"},adapter),
            (row,hm,None),
            (row,hm,{**adapter,"transport_class":"SECONDARY_MIRROR"}),
            (row,hm,{**adapter,"read_only":False}),
            (row,hm,{**adapter,"dynamic_release_discovery":False}),
            (row,hm,{**adapter,"source":"Figure.NZ"}),
        ]
        for i,(r,h,a) in enumerate(cases):
            with self.subTest(case=i):
                with self.assertRaises(ValueError):
                    checked_public_source_label("NZD.inflation",r,h,a)

    def test_nzd_labour_retains_mirror_label_even_with_certified_adapter(self):
        row=self.registry["series"]["NZD.labour"]
        hm=self.heatmap["currencies"]["NZD"]["labour"]
        _,adapter=certified_adapter_contract("NZD.labour",row)
        self.assertEqual(row["source"],"Stats NZ via Figure.NZ mirror")
        self.assertEqual(hm["source"],row["source"])
        self.assertEqual(
            checked_public_source_label("NZD.labour",row,hm,adapter),
            "CANONICAL_SOURCE_LABEL",
        )

    def test_real_registry_validator_passes_without_live_mutation(self):
        before_reg=copy.deepcopy(self.registry)
        before_heat=copy.deepcopy(self.heatmap)
        self.assertEqual(main(),0)
        self.assertEqual(load(REGISTRY),before_reg)
        self.assertEqual(load(HEATMAP),before_heat)


if __name__=="__main__":
    unittest.main()
