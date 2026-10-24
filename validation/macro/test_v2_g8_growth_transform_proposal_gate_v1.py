import copy
import json
import unittest
from datetime import date

from validation.macro.v2_g8_growth_transform_proposal_gate_v1 import (
    FILE, OBSERVED, audit, shadow_math, validate_contract, PINNED, RULES,
)
from validation.macro.v2_pit_g8_control_plane_v1 import run as g8_control_plane


class G8GrowthTransformProposalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads(FILE.read_text(encoding="utf-8"))
        cls.observed=json.loads(OBSERVED.read_text(encoding="utf-8"))
        cls.common=g8_control_plane(as_of="2026-10-24T00:00:00Z")
        cls.rows=cls.fixture["feature_proposals"]

    def proposal(self,c):
        return next(x for x in self.rows if x["currency"]==c)

    def run_audit(self,fixture=None,observed=None,common=None):
        return audit(self.fixture if fixture is None else fixture,
                     self.observed if observed is None else observed,
                     self.common if common is None else common)

    def test_eight_pinned_distinct_g8_series_and_three_incompatible_horizons(self):
        r=self.run_audit()
        self.assertEqual([x["currency"] for x in r["rows"]],
                         ["USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"])
        self.assertEqual(r["summary"],{
            "g8_growth_candidates":8,
            "monthly_level_transform_proposals":6,
            "quarterly_reported_qoq_proposals":1,
            "quarterly_reported_yoy_proposals":1,
            "observed_current_revised_history_rows_not_first_release":567,
            "g8_growth_slots_with_model_selected":0,
            "g8_growth_slots_with_complete_first_release_vintage":0,
            "g8_growth_slots_with_common_comparable_horizon":0,
            "g8_growth_scores_newly_approved":0,
        })
        self.assertEqual({x["underlying_economic_family"] for x in r["rows"]},
                         {"INDUSTRIAL_PRODUCTION","REAL_GDP_INDUSTRY","REAL_GDP"})
        self.assertEqual(len({x["growth_horizon"] for x in r["rows"]}),3)
        self.assertEqual(set(PINNED),{x["currency"] for x in r["rows"]})
        self.assertEqual(len(RULES),5)
        self.assertFalse(r["cross_fx_zscore_fitted"])
        self.assertFalse(r["scores_computed"])

    def test_us_eur_gbp_jpy_chf_cad_monthly_levels_need_six_real_pit_vintages(self):
        receipt=self.run_audit()
        for cc in ("USD","EUR","GBP","JPY","CHF","CAD"):
            with self.subTest(currency=cc):
                r=next(x for x in receipt["rows"] if x["currency"]==cc)
                self.assertEqual(r["frequency"],"M")
                self.assertEqual(r["proposed_transform"],"LEVEL_3M3M")
                self.assertEqual(r["minimum_same_vintage_observations_for_math"],6)
                self.assertEqual(r["publisher_first_release_periods_in_common_gateway"],1)
                self.assertEqual(r["first_releases_minimum_per_single_series"],25)
                self.assertEqual(r["observed_revised_history_periods_not_first_release"],82)
                self.assertFalse(r["feature_computable_from_documented_first_web_source_events"])
                self.assertFalse(r["new_macro_score_permitted"])
        self.assertEqual(receipt["rows"][1]["candidate_source_relation"],
                         "MOM_RATE_VS_INDEX_LEVEL")
        self.assertEqual(receipt["rows"][2]["candidate_source_relation"],
                         "PUBLISHED_3M3M_RATE_VS_INDEX_LEVEL")
        self.assertEqual(receipt["rows"][4]["candidate_source_relation"],
                         "DIFFERENT_INDICATOR_GDP_QUARTERLY_VS_INDUSTRIAL_MONTHLY")

    def test_aud_nzd_quarterly_reported_rate_not_automatically_comparable(self):
        r=self.run_audit()
        aus=next(x for x in r["rows"] if x["currency"]=="AUD")
        nzd=next(x for x in r["rows"] if x["currency"]=="NZD")
        self.assertEqual(aus["proposed_transform"],"REPORTED_QOQ_RATE")
        self.assertEqual(aus["growth_horizon"],"QUARTER_ON_QUARTER")
        self.assertEqual(aus["latest_observed_revised_value"],0.4)
        self.assertEqual(nzd["proposed_transform"],"REPORTED_YOY_RATE")
        self.assertEqual(nzd["growth_horizon"],"SAME_QUARTER_PREVIOUS_YEAR")
        self.assertEqual(nzd["latest_observed_revised_value"],2.6)
        self.assertEqual(aus["first_releases_minimum_per_single_series"],13)
        self.assertEqual(nzd["first_releases_minimum_per_single_series"],13)
        self.assertFalse(aus["normalization_permitted"])
        self.assertFalse(nzd["normalization_permitted"])
        self.assertEqual(aus["observed_revised_history_periods_not_first_release"],33)
        self.assertEqual(nzd["observed_revised_history_periods_not_first_release"],42)

    @staticmethod
    def six_month_source_events():
        periods=["2026-01","2026-02","2026-03","2026-04","2026-05","2026-06"]
        published=["2026-02-01T00:00:00Z","2026-03-01T00:00:00Z",
                   "2026-04-01T00:00:00Z","2026-05-01T00:00:00Z",
                   "2026-06-01T00:00:00Z","2026-07-01T00:00:00Z"]
        values=[100,100,100,110,110,110]
        return [{"reference_period":p,"published_at_utc":t,"kind":"FIRST_WEB","value":v}
                for p,t,v in zip(periods,published,values)]

    def test_synthetic_monthly_level_3m3m_no_future_data_leak(self):
        events=self.six_month_source_events()
        p=self.proposal("USD")
        old=shadow_math(p,events,as_of="2026-06-30T23:59:59Z")
        final=shadow_math(p,events,as_of="2026-07-01T00:00:00Z")
        self.assertIsNone(old["research_feature_percent"])
        self.assertEqual(old["status"],"MISSING_SIX_CONSECUTIVE_FIRST_VINTAGE_PERIODS")
        self.assertEqual(final["status"],"SIX_MONTH_DESCRIPTIVE_RESEARCH_MATH_ONLY")
        self.assertAlmostEqual(final["research_feature_percent"],10.0)
        self.assertEqual(final["underlying_periods_in_formula"],
                         ["2026-01","2026-02","2026-03",
                          "2026-04","2026-05","2026-06"])
        self.assertFalse(final["eligible_for_backtest"])
        self.assertFalse(final["eligible_for_macro_score"])
        self.assertFalse(final["safe_to_publish_new_D"])

    def test_synthetic_revisions_visible_only_after_new_source_publication(self):
        events=self.six_month_source_events()
        events.append({"reference_period":"2026-06","kind":"REVISION_WEB",
                       "published_at_utc":"2026-08-01T00:00:00Z","value":121})
        a=shadow_math(self.proposal("USD"),events,
                      as_of="2026-07-31T23:59:59Z")
        b=shadow_math(self.proposal("USD"),events,
                      as_of="2026-08-01T00:00:00Z")
        self.assertAlmostEqual(a["research_feature_percent"],10.0)
        self.assertAlmostEqual(b["research_feature_percent"],13.66666666666667)
        self.assertNotEqual(a["research_feature_percent"],b["research_feature_percent"])
        self.assertFalse(b["eligible_for_macro_score"])

    def test_synthetic_gap_refuses_six_level_3m3m_and_rate_passthrough_is_descriptive(self):
        events=self.six_month_source_events()
        missing=events[:2]+events[3:]
        r=shadow_math(self.proposal("EUR"),missing,
                      as_of="2026-07-01T00:00:00Z")
        self.assertEqual(r["status"],"MISSING_SIX_CONSECUTIVE_FIRST_VINTAGE_PERIODS")
        self.assertIsNone(r["research_feature_percent"])
        aus=shadow_math(self.proposal("AUD"),[{
            "reference_period":"2026Q2","kind":"FIRST_WEB",
            "published_at_utc":"2026-09-02T01:30:00Z","value":0.4,
        }],as_of="2026-09-02T01:30:00Z")
        nzd=shadow_math(self.proposal("NZD"),[{
            "reference_period":"2026Q2","kind":"FIRST_WEB",
            "published_at_utc":"2026-09-18T00:00:00Z","value":2.6,
        }],as_of="2026-09-18T00:00:00Z")
        self.assertEqual(aus["research_feature_percent"],0.4)
        self.assertEqual(nzd["research_feature_percent"],2.6)
        self.assertEqual(aus["status"],"DESCRIPTIVE_QUARTERLY_RATE_NO_CROSS_COUNTRY_SCORE")
        self.assertEqual(nzd["status"],"DESCRIPTIVE_QUARTERLY_RATE_NO_CROSS_COUNTRY_SCORE")
        self.assertNotEqual(self.proposal("AUD")["comparable_growth_horizon"],
                            self.proposal("NZD")["comparable_growth_horizon"])

    def test_first_release_revision_and_timestamp_contract_fail_closed(self):
        base=self.six_month_source_events()
        bad=[]
        x=copy.deepcopy(base);x.append(copy.deepcopy(x[0]));bad.append(x)
        x=copy.deepcopy(base);x.append({"reference_period":"2026-07","kind":"REVISION_WEB",
                        "published_at_utc":"2026-08-01T00:00:00Z","value":110});bad.append(x)
        x=copy.deepcopy(base);x.append({"reference_period":"2026-01","kind":"REVISION_WEB",
                        "published_at_utc":"2026-01-01T00:00:00Z","value":101});bad.append(x)
        x=copy.deepcopy(base);x[0]["published_at_utc"]="2026-01-31T10:00:00";bad.append(x)
        x=copy.deepcopy(base);x[0]["value"]=float("nan");bad.append(x)
        x=copy.deepcopy(base);x[0]["value"]=False;bad.append(x)
        x=copy.deepcopy(base);x[0]["value"]=0;bad.append(x)
        x=copy.deepcopy(base);x[0]["reference_period"]="2026Q1";bad.append(x)
        x=copy.deepcopy(base);x[0]["kind"]="DETAILED_WEB";bad.append(x)
        for k,items in enumerate(bad):
            with self.subTest(k=k):
                with self.assertRaises((ValueError,TypeError)):
                    shadow_math(self.proposal("USD"),items,
                                as_of="2026-10-24T00:00:00Z")

    def test_tampered_proposal_never_passes_to_g8_score(self):
        for cc,field,new in (
            ("EUR","proposal_transform","REPORTED_QOQ_RATE"),
            ("USD","raw_unit","percent month on month"),
            ("CAD","latest_observed_value",0.3),
            ("AUD","comparable_growth_horizon","SAME_QUARTER_PREVIOUS_YEAR"),
            ("NZD","observed_revised_history_length",24),
            ("CHF","candidate_web_series_id","CH_PRODUCTION_history_value"),
            ("JPY","canonical_growth_source_selected",True),
        ):
            with self.subTest(currency=cc,field=field):
                obj=copy.deepcopy(self.fixture)
                next(x for x in obj["feature_proposals"] if x["currency"]==cc)[field]=new
                with self.assertRaises((ValueError,TypeError)):
                    validate_contract(obj)
        obj=copy.deepcopy(self.fixture);obj["cross_currency_growth_zscore_comparable"]=True
        with self.assertRaises(ValueError):
            validate_contract(obj)
        obj=copy.deepcopy(self.fixture);obj["write_macro_scores"]=True
        with self.assertRaises(ValueError):
            validate_contract(obj)

    def test_observed_history_drift_and_missing_source_evidence_fail_closed(self):
        obs=copy.deepcopy(self.observed)
        next(x for x in obs["EUR"] if x["id"]=="EA_IP_history_value")["last_value"]=97.1
        with self.assertRaises(ValueError):
            self.run_audit(observed=obs)
        obs=copy.deepcopy(self.observed)
        next(x for x in obs["CAD"] if x["id"]=="CA_REAL_GDP_M_history_value")["dates"].pop()
        with self.assertRaises(ValueError):
            self.run_audit(observed=obs)
        obs=copy.deepcopy(self.observed)
        row=next(x for x in obs["CHF"] if x["id"]=="CH_PRODUCTION_history_value")
        row["dates"][-2]=row["dates"][-3]
        with self.assertRaises(ValueError):
            self.run_audit(observed=obs)
        common=copy.deepcopy(self.common)
        next(x for x in common["rows"] if (x["currency"],x["pillar"])==("EUR","growth"))[
            "candidate_evidence_source_id"]="NOT_EUROSTAT"
        with self.assertRaises(ValueError):
            self.run_audit(common=common)

    def test_proposal_and_observed_sources_never_mutated(self):
        obj=copy.deepcopy(self.fixture)
        dat=copy.deepcopy(self.observed)
        cp=copy.deepcopy(self.common)
        a=audit(obj,dat,cp)
        b=audit(obj,dat,cp)
        self.assertEqual(a,b)
        self.assertEqual(obj,self.fixture)
        self.assertEqual(dat,self.observed)
        self.assertEqual(cp,self.common)
        for k in ("historical_revised_series_consumed_for_macro_factor",
                  "derived_growth_values_from_live_series_computed",
                  "cross_fx_zscore_fitted","scores_computed",
                  "model_parameters_fitted","ready_for_backtest",
                  "safe_to_publish_new_D","safe_to_update_pair_theses",
                  "writes_live_data"):
            self.assertFalse(a[k])


if __name__=="__main__":
    unittest.main()
