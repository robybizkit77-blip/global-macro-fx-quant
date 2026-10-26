"""Never promote unverified EUR2Y/10Y historical curves; pure candidate tests."""
from __future__ import annotations

import copy
from datetime import date,timedelta
import json
import unittest

from validation.rates import build_eur_full_2y_10y_ecb_history_candidate_v1 as m


class FullECBSameBasisHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live=json.loads(m.CURRENT.read_text(encoding="utf-8"))
        cls.orig={}
        for tenor in ("2Y","10Y"):
            h=cls.live["EUR"]["history"+tenor[:-1]]
            cls.orig[tenor]=dict(zip(h["dates"],h["values"]))

    def make_csv(self,tenor,*,revisions=None,add=None,omit=None):
        revisions=revisions or {}
        dic={**self.orig[tenor],**(add or {})}
        dic.update(revisions)
        if omit:
            for k in omit:
                dic.pop(k,None)
        return ("KEY,TIME_PERIOD,OBS_VALUE\n"+"".join(
            f"{m.SERIES[tenor]},{d},{value:.10f}\n"
            for d,value in sorted(dic.items())
        )).encode("utf-8")

    def pair(self,**kwargs):
        return self.make_csv("2Y",**kwargs),self.make_csv("10Y",**kwargs)

    def test_offline_original_source_equal_is_read_only_candidate(self):
        before=json.dumps(self.live,sort_keys=True)
        a,b=self.pair()
        cand,receipt=m.build_candidate(self.live,a,b)
        self.assertEqual(receipt["status"],"CANDIDATE_FOR_SEPARATE_REVIEW_NOT_PUBLISHED")
        self.assertFalse(receipt["actual_production_promotion"])
        self.assertFalse(receipt["first_release_vintage_certified"])
        self.assertTrue(receipt["current_rate_snapshot_unchanged"])
        self.assertEqual([cc for cc in self.live if cand[cc]!=self.live[cc]],["EUR"])
        self.assertEqual(json.dumps(self.live,sort_keys=True),before)
        self.assertEqual(cand["EUR"]["2Y"],self.live["EUR"]["2Y"])
        self.assertEqual(cand["EUR"]["10Y"],self.live["EUR"]["10Y"])
        self.assertEqual(cand["EUR"]["tenors"],self.live["EUR"]["tenors"])
        self.assertEqual(cand["EUR"]["history2"]["dates"],self.live["EUR"]["history2"]["dates"])
        self.assertIn("NOT_PIT",cand["EUR"]["history2_quality"])
        notice=cand["EUR"]["historical_curve_rebase"]
        self.assertEqual(notice["schema"],"GMFQ_EUR_2Y_10Y_HISTORY_REBASE_NOTICE_V1")
        self.assertEqual(notice["status"],"RESEARCH_CANDIDATE_NOT_PUBLISHED")
        self.assertEqual(notice["original_point_count"],271)
        self.assertTrue(notice["requires_explicit_release"])
        self.assertTrue(notice["source_rebase_not_market_move"])
        self.assertFalse(notice["historical_first_release_pit_certified"])
        self.assertEqual(notice["original_paired_values_sha256"],
                         receipt["official_paired_observations_sha256"])
        self.assertFalse(receipt["actual_production_promotion"])

    def test_historic_source_discrepancies_corrected_in_candidate_only(self):
        v={"2026-09-21":3.1476088412,"2026-09-22":3.135563132}
        a=self.make_csv("2Y",revisions=v)
        b=self.make_csv("10Y")
        cand,receipt=m.build_candidate(self.live,a,b)
        self.assertEqual(receipt["per_tenor_official_parity"]["2Y"]["overlap_yield_mismatches"],2)
        self.assertEqual(receipt["per_tenor_official_parity"]["10Y"]["overlap_yield_mismatches"],0)
        mapping=dict(zip(cand["EUR"]["history2"]["dates"],cand["EUR"]["history2"]["values"]))
        self.assertEqual(mapping["2026-09-21"],3.1476088412)
        self.assertEqual(self.live["EUR"]["history2"]["values"][
            self.live["EUR"]["history2"]["dates"].index("2026-09-21")],3.2598888904)

    def test_new_official_week_date_cannot_be_invented_or_relabelled(self):
        a=self.make_csv("2Y",add={"2026-09-23":3.12345})
        b=self.make_csv("10Y",add={"2026-09-23":3.94567})
        cand,receipt=m.build_candidate(self.live,a,b)
        self.assertEqual(receipt["per_tenor_official_parity"]["2Y"]["new_publisher_dates"],
                         ["2026-09-23"])
        self.assertEqual(cand["EUR"]["history2"]["dates"].count("2026-09-23"),1)
        self.assertFalse(receipt["no_core_or_forward_mutation"] is False)

    def test_incomplete_single_tenor_dates_is_fatal(self):
        a=self.make_csv("2Y",add={"2026-09-23":3.12345})
        b=self.make_csv("10Y")
        with self.assertRaisesRegex(ValueError,"same-day complete"):
            m.build_candidate(self.live,a,b)

    def test_official_current_rate_mismatch_blocks_even_if_history_complete(self):
        a=self.make_csv("2Y",revisions={"2026-10-22":5.5})
        with self.assertRaisesRegex(ValueError,"snapshot disagrees"):
            m.build_candidate(self.live,a,self.make_csv("10Y"))

    def test_wrong_named_ecb_curve_not_accepted(self):
        wrong=self.make_csv("2Y").replace(b"SR_2Y",b"SR_10Y")
        with self.assertRaisesRegex(ValueError,"series name/tenor mismatch"):
            m.build_candidate(self.live,wrong,self.make_csv("10Y"))

    def test_duplicate_historical_date_is_fatal(self):
        raw=self.make_csv("10Y")
        tail=f"{m.SERIES['10Y']},2026-10-22,3.3844008945\n".encode()
        with self.assertRaisesRegex(ValueError,"duplicate ECB"):
            m.build_candidate(self.live,self.make_csv("2Y"),raw+tail)

    def test_original_history_outside_current_asof_not_accepted(self):
        with self.assertRaisesRegex(ValueError,"outside verified historical period"):
            m.build_candidate(self.live,self.make_csv("2Y"),
                self.make_csv("10Y")+f"{m.SERIES['10Y']},2026-10-23,3.5\n".encode())

    def test_wrong_live_authority_blocks_publisher_candidate(self):
        bad=copy.deepcopy(self.live)
        bad["EUR"]["source"]="Another vendor"
        with self.assertRaisesRegex(ValueError,"source identity"):
            m.build_candidate(bad,*self.pair())

    def test_original_2y_and_10y_wrong_mirror_date_length_fails_closed(self):
        bad=copy.deepcopy(self.live)
        bad["EUR"]["history10"]["dates"].pop(-4)
        bad["EUR"]["history10"]["values"].pop(-4)
        with self.assertRaisesRegex(ValueError,"legacy EUR 2Y and 10Y historical dates differ"):
            m.build_candidate(bad,*self.pair())


if __name__=="__main__":
    unittest.main()
