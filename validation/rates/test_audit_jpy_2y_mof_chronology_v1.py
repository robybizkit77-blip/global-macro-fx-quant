"""Preserve JPY yield pairing while staging strict original MoF checks."""
import copy
from datetime import date
import json
import unittest
from validation.rates import audit_jpy_2y_mof_chronology_v1 as m


class Japan2YRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orig=json.loads(m.SOURCE.read_text(encoding="utf-8"))
        cls.stage=m.normalize_source(cls.orig)

    def test_all_273_pairs_preserved_with_no_value_changes(self):
        c=self.stage
        self.assertEqual(c["original_row_count"],273)
        self.assertEqual(c["normalized_row_count"],273)
        self.assertTrue(c["date_value_pairs_preserved"])
        self.assertFalse(c["yield_values_modified"])
        self.assertFalse(c["missing_dates_imputed"])
        self.assertFalse(c["promoted_into_live_rates"])
        self.assertFalse(c["promoted_into_beta"])
        expected={(m.day(d).isoformat(),v) for d,v in zip(
            self.orig["JPY"]["history2"]["dates"],
            self.orig["JPY"]["history2"]["values"])}
        actual={(x["date"],x["yield_pct"]) for x in c["candidate_rows"]}
        self.assertEqual(expected,actual)
        self.assertEqual(len(expected),273)

    def test_246_legacy_noniso_dates_and_30_chronology_inversions(self):
        self.assertEqual(self.stage["noncanonical_date_strings"],246)
        self.assertEqual(self.stage["chronological_reversals"],30)
        self.assertEqual(self.stage["first_day"],"2025-05-08")
        self.assertEqual(self.stage["last_day"],"2026-10-23")

    def test_formerly_lexicographic_june_2_is_before_june_19(self):
        a=[x["date"] for x in self.stage["candidate_rows"]]
        self.assertLess(a.index("2025-06-02"),a.index("2025-06-19"))
        self.assertLess(a.index("2025-06-03"),a.index("2025-06-27"))
        self.assertEqual(a,sorted(a))

    def test_monthly_2026_official_anchor_rates_keep_same_dates(self):
        rows={x["date"]:x["yield_pct"] for x in self.stage["candidate_rows"]}
        for day,value in [("2026-10-02",1.919),("2026-10-06",1.930),
                          ("2026-10-20",1.909),("2026-10-22",1.914)]:
            self.assertAlmostEqual(rows[day],value,places=3)

    def test_stale_and_nonofficial_quality_must_not_get_repair(self):
        src=copy.deepcopy(self.orig)
        src["JPY"]["quality"]="WITHHELD"
        with self.assertRaisesRegex(ValueError,"unexpected JPY rate provenance"):
            m.normalize_source(src)

    def test_duplicate_day_after_normalize_fails(self):
        src=copy.deepcopy(self.orig)
        src["JPY"]["history2"]["dates"][0]=src["JPY"]["history2"]["dates"][1]
        with self.assertRaisesRegex(ValueError,"duplicated 2Y observation"):
            m.normalize_source(src)

    def test_reject_unaligned_number_of_values(self):
        src=copy.deepcopy(self.orig)
        src["JPY"]["history2"]["values"].pop()
        with self.assertRaisesRegex(ValueError,"unbalanced"):
            m.normalize_source(src)

    def test_mof_header_2y_selected_not_1y_10y(self):
        raw=("Interest Rate,,,,(Unit : %)\n"
             "Date,1Y,2Y,10Y\n"
             "2026/10/02,1.6,1.919,3.1\n"
             "2026/10/06,1.7,1.930,3.2\n").encode("cp932")
        d=m.parse_mof_csv(raw,source=m.CURR_URL)
        self.assertEqual(d[date(2026,10,2)],1.919)
        self.assertEqual(d[date(2026,10,6)],1.930)

    def test_mof_era_calendar_supported_not_silently_invented(self):
        raw=("Interest Rate\nDate,1Y,2Y,10Y\n"
             "R8.10.21,1.8,1.914,3.2\n"
             "R8.10.22,1.8,1.914,3.2\n").encode("cp932")
        d=m.parse_mof_csv(raw,source=m.CURR_URL)
        self.assertEqual(d[date(2026,10,21)],1.914)
        self.assertEqual(d[date(2026,10,22)],1.914)

    def test_official_complete_fixture_certifies_only_observation_agreement(self):
        rows=self.stage["candidate_rows"]
        sep=date(2026,9,30)
        past=[x for x in rows if date.fromisoformat(x["date"])<=sep]
        current=[x for x in rows if date.fromisoformat(x["date"])>sep]
        def to_csv(arr):
            return ("Interest Rate\nDate,1Y,2Y,10Y\n"+
                   "".join(f"{x['date'].replace('-','/')},0,{x['yield_pct']:.3f},3\n" for x in arr)).encode("cp932")
        out=m.verify_official(self.stage,to_csv(past),to_csv(current))
        self.assertEqual(out["state"],"ALL_2Y_POINTS_AGREE_WITH_MOF")
        self.assertEqual(out["matched"],273)
        self.assertFalse(out["historical_first_publication_pit_certified"])
        self.assertFalse(out["candidate_promoted_into_live_rates"])

    def test_one_mof_disagreement_blocks_even_if_272_match(self):
        rows=self.stage["candidate_rows"]
        def c(x):
            return ("Interest Rate\nDate,1Y,2Y\n"+"".join(
                f"{y['date'].replace('-','/')},1,{y['yield_pct'] + (.02 if y is x[0] else 0):.3f}\n" for y in x)).encode("cp932")
        official=m.verify_official(self.stage,c(rows[:150]),c(rows[150:]))
        self.assertEqual(official["state"],"NOT_CERTIFIED_OFFICIAL_COMPARISON_FAILED")
        self.assertEqual(len(official["mismatches"]),1)
        self.assertEqual(official["matched"],272)

    def test_official_missing_one_day_does_not_implicitly_fill(self):
        rows=self.stage["candidate_rows"]
        def c(x):
            return ("Interest Rate\nDate,1Y,2Y\n"+"".join(
                f"{y['date'].replace('-','/')},1,{y['yield_pct']:.3f}\n" for y in x)).encode("cp932")
        official=m.verify_official(self.stage,c(rows[:100]),c(rows[101:]))
        self.assertEqual(official["state"],"NOT_CERTIFIED_OFFICIAL_COMPARISON_FAILED")
        self.assertEqual(len(official["missing"]),1)

    def test_invalid_official_nan_and_duplicate_are_rejected(self):
        with self.assertRaisesRegex(ValueError,"nonfinite"):
            m.parse_mof_csv(b"Date,1Y,2Y\n2026/10/02,1,nan\n",source=m.HIST_URL)
        with self.assertRaisesRegex(ValueError,"duplicated"):
            m.parse_mof_csv(b"Date,1Y,2Y\n2026/10/02,1,1.919\n2026/10/02,1,1.919\n",
                            source=m.HIST_URL)

    def test_bad_source_asof_rejected(self):
        src=copy.deepcopy(self.orig)
        src["JPY"]["date"]="2026-10-24"
        with self.assertRaisesRegex(ValueError,"last dated"):
            m.normalize_source(src)


if __name__=="__main__":
    unittest.main()
