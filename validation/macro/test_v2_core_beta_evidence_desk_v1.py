"""Adversarial bounded beta evidence preview; never promote an FX signal."""
import copy
import json
import unittest
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from validation.macro.v2_domestic_candidate_explicit_formula_v1 import run as domestic_run
from validation.macro.v2_core_beta_evidence_desk_v1 import (
    ROOT, G8, SCHEMA, build, render, run
)


class IntegratedBetaDeskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        read=lambda f:json.loads((ROOT/"live_data/sections"/(f+".json")).read_text())
        cls.audit_day=datetime.now(ZoneInfo("Europe/Rome")).date().isoformat()
        cls.candidate=domestic_run(as_of=cls.audit_day)
        cls.legacy=read("D")
        cls.pairs=read("PAIR_SETUP_OPERATIONAL_VIEW")
        cls.cb=read("NATIVE_CB_DATA")
        cls.ois=read("OIS_OPERATIONAL_VIEW")
        cls.rates=read("NATIVE_RATES_DATA")

    def make(self, **overrides):
        data={
            "candidate":copy.deepcopy(self.candidate),
            "legacy":copy.deepcopy(self.legacy),
            "pairs":copy.deepcopy(self.pairs),
            "banks":copy.deepcopy(self.cb),
            "ois":copy.deepcopy(self.ois),
            "rates":copy.deepcopy(self.rates),
        }
        data.update(overrides)
        return build(**data, as_of=self.audit_day)

    def test_all_eight_leg_sources_and_all_28_unchanged_pair_context(self):
        result=self.make()
        self.assertEqual(result["schema"],SCHEMA)
        self.assertEqual(set(result["countries"]),set(G8))
        self.assertEqual(len(result["pairs"]),28)
        self.assertEqual(result["legacy_model_baseline_as_of"],"2026-09-25")
        self.assertEqual(result["official_price_overlay_as_of"],self.pairs["price_asof"])
        self.assertEqual(result["summary"]["domestic_classes_robust"],4)
        kinds=[v["six_month_source_class"] for v in result["countries"].values()]
        self.assertEqual(result["summary"]["official_policy_pricing"],
                         kinds.count("OFFICIAL_POLICY_PRICING"))
        self.assertEqual(result["summary"]["indicative_policy_pricing"],
                         kinds.count("ESTIMATED_POLICY_PRICING_NOT_OFFICIAL"))
        self.assertEqual(result["summary"]["pre_decision_6m_quotes"],
                         sum(k.startswith("PRE_DECISION_") for k in kinds))
        self.assertEqual(result["summary"]["context_only_non_policy_6m"],
                         8-kinds.count("OFFICIAL_POLICY_PRICING")
                         -kinds.count("ESTIMATED_POLICY_PRICING_NOT_OFFICIAL"))
        self.assertEqual(result["summary"]["new_country_FX_scores"],0)
        self.assertEqual(result["summary"]["new_pair_theses"],0)
        for flag in ("safe_to_republish_D",
                     "safe_to_recalculate_pair_rankings",
                     "eligible_for_beta_model_validation",
                     "eligible_for_forward_trade_attribution",
                     "forecast_or_entry_generated","writes_live_data"):
            self.assertFalse(result[flag],flag)
        self.assertTrue(result["no_cross_country_z_score_rank_generated"])
        for c, r in result["countries"].items():
            self.assertIsNone(r["trade_signal"],c)
            self.assertIsNone(r["FX_strength_score"],c)
            self.assertEqual(r["cb_CAN_status"],
                             "NOT_CALIBRATED_FROM_ECONOMIC_LEVELS")
            self.assertEqual(r["cb_WANT_status"],
                             "RECORDED_COMMUNICATION_NOT_NEW_DECISION")
        for item in result["pairs"]:
            self.assertIsNone(item["fx_bias_from_beta_candidate"])
            self.assertIsNone(item["trade_entry_from_beta_candidate"])
            self.assertTrue(item["economic_classes_NOT_cross_country_comparable"])

    def test_source_tiers_prevent_fake_g8_official_ois(self):
        x=self.make()["countries"]
        official={k for k,v in x.items()
                  if v["six_month_source_class"]=="OFFICIAL_POLICY_PRICING"}
        self.assertTrue({"GBP","JPY","AUD"}.issubset(official))
        self.assertTrue(official.issubset({"GBP","JPY","AUD","CAD"}))
        self.assertEqual({k for k,v in x.items()
            if v["six_month_source_class"]=="CONFLICTED_FUTURES_6M_CONTEXT_ONLY_NO_POLICY_DELTA"},
            {"USD","EUR"})
        for c in ("USD","EUR"):
            self.assertIsNone(x[c]["six_month_policy_delta_bp"])
            self.assertEqual(
                x[c]["six_month_rate_pct_descriptive_only"],
                self.ois["currencies"][c]["horizons"]["6m"]["rate"])
        self.assertEqual(x["CHF"]["six_month_source_class"],
                         "ESTIMATED_FUTURES_6M_CONTEXT_ONLY_NO_POLICY_DELTA")
        self.assertIsNone(x["CHF"]["six_month_policy_delta_bp"])
        self.assertEqual(x["CHF"]["six_month_rate_pct_descriptive_only"],
                         self.ois["currencies"]["CHF"]["horizons"]["6m"]["rate"])
        self.assertFalse(self.ois["currencies"]["CHF"]["policy_repricing_inference_allowed"])
        self.assertEqual(x["CAD"]["official_current_cb_rate_pct"],2.50)
        self.assertEqual(x["CAD"]["six_month_quote_date"],
                         self.ois["currencies"]["CAD"]["as_of"])
        pre=(self.cb["CAD"]["rate"]!=self.ois["currencies"]["CAD"]["policy_rate"]
             and self.ois["currencies"]["CAD"]["as_of"]<self.cb["CAD"]["last_date"])
        if pre:
            self.assertEqual(x["CAD"]["six_month_source_class"],
                             "PRE_DECISION_OFFICIAL_QUOTE_NO_CURRENT_POLICY_DELTA")
            self.assertIsNone(x["CAD"]["six_month_policy_delta_bp"])
        else:
            self.assertEqual(x["CAD"]["six_month_source_class"],
                             "OFFICIAL_POLICY_PRICING")
            self.assertIsNotNone(x["CAD"]["six_month_policy_delta_bp"])
        self.assertEqual(x["NZD"]["six_month_source_class"],
                         "BANK_BILL_BASIS_DIRECTIONAL_CONTEXT_ONLY")
        self.assertIsNone(x["NZD"]["six_month_policy_delta_bp"])

    def test_futures_same_day_source_disputes_never_create_policy_deltas(self):
        for c in ("USD", "EUR"):
            with self.subTest(ccy=c):
                row=self.make()["countries"][c]
                self.assertEqual(row["six_month_source_class"],
                                 "CONFLICTED_FUTURES_6M_CONTEXT_ONLY_NO_POLICY_DELTA")
                self.assertIsNone(row["six_month_policy_delta_bp"])
                self.assertEqual(row["six_month_quote_date"],
                                 self.ois["currencies"][c]["as_of"])
                self.assertIsNone(row["trade_signal"])
                self.assertIsNone(row["FX_strength_score"])
        for c in ("USD", "EUR"):
            for label,change in (
                ("false_policy_delta",lambda p:p["horizons"]["6m"].__setitem__("policy_delta_bp",15)),
                ("fake_change_1d",lambda p:p["horizons"]["6m"].__setitem__("change_1d_bp",4)),
                ("fake_change_1w",lambda p:p["horizons"]["6m"].__setitem__("change_1w_bp",-2)),
                ("false_backtest",lambda p:p.__setitem__("backtest_eligible_as_official",True)),
                ("false_policy_direction",lambda p:p.__setitem__("direction_vs_policy","UP")),
                ("forged_event",lambda p:p["source_conflict_keys"][0].__setitem__("event_id","x"*64)),
                ("wrong_contract",lambda p:p["source_conflict_keys"][0].__setitem__("contract","FAKE")),
                ("fake_clear_conflict",lambda p:p.__setitem__("source_conflict_keys",[])),
                ("source_grade_upgrade",lambda p:p.__setitem__("source_quality","OFFICIAL_CERTIFIED")),
            ):
                with self.subTest(ccy=c,case=label):
                    wrong=copy.deepcopy(self.ois)
                    change(wrong["currencies"][c])
                    with self.assertRaises(ValueError):
                        self.make(ois=wrong)

    def test_disputed_six_month_print_unverified_but_healthy_other_tenor_accepted(self):
        for c in ("USD", "EUR"):
            p=self.ois["currencies"][c]
            original=p["horizons"]["6m"]
            # In the Oct30 source USD 6M is itself conflicted; EUR 6M
            # is individually verified but another EUR tenor is disputed.
            required=any(k["horizon"]=="6m" for k in p["source_conflict_keys"])
            self.assertEqual(original["quote_timestamp_verified"],not required)
            tampered=copy.deepcopy(self.ois)
            q=tampered["currencies"][c]["horizons"]["6m"]
            q["quote_timestamp_verified"]=required
            with self.assertRaises(ValueError):
                self.make(ois=tampered)

    def test_predecision_mismatch_must_have_strictly_older_ois_quote(self):
        # A same-day 2.25% curve cannot masquerade as a valid quote against
        # the new official BoC 2.50% rate.
        invalid=copy.deepcopy(self.ois)
        invalid["currencies"]["CAD"]["as_of"]=self.cb["CAD"]["last_date"]
        invalid["currencies"]["CAD"]["policy_rate"]=self.cb["CAD"]["rate"]-0.25
        with self.assertRaisesRegex(ValueError, "policy rate and market bridge disagree"):
            self.make(ois=invalid)
        # An isolated pre-decision scenario must remain context-only even
        # after the live exchange file advances on the next working day.
        valid=copy.deepcopy(invalid)
        valid["currencies"]["CAD"]["as_of"]=(date.fromisoformat(
            self.cb["CAD"]["last_date"])-timedelta(days=1)).isoformat()
        row=self.make(ois=valid)["countries"]["CAD"]
        self.assertEqual(row["six_month_source_class"],
                         "PRE_DECISION_OFFICIAL_QUOTE_NO_CURRENT_POLICY_DELTA")
        self.assertIsNone(row["six_month_policy_delta_bp"])

    def test_historical_bond_not_described_current_and_no_tenor_mixup(self):
        x=self.make()["countries"]
        self.assertEqual(x["CHF"]["bond_freshness"],"HISTORICAL_NOT_CURRENT")
        self.assertEqual(x["NZD"]["bond_freshness"],"HISTORICAL_NOT_CURRENT")
        self.assertEqual(x["USD"]["bond_freshness"],"OBSERVED_RECENT")
        for c,v in x.items():
            self.assertAlmostEqual(v["two_ten_curve_bp_derived"],
                 round((self.rates[c]["10Y"]-self.rates[c]["2Y"])*100,2))

    def test_no_promotion_of_inconsistent_official_pricing_claims(self):
        for mutate in [
            lambda x:x["currencies"]["CHF"].update(
                {"operational_status":"GREEN_OFFICIAL"}),
            lambda x:x["currencies"]["CAD"].update(
                {"backtest_eligible_as_official":False}),
            lambda x:x["currencies"]["USD"].update(
                {"quality":"OFFICIAL_CERTIFIED"}),
            lambda x:x["currencies"]["NZD"]["horizons"]["6m"].update(
                {"rate":3.84,"policy_delta_bp":109}),
            lambda x:x["currencies"]["AUD"].update(
                {"as_of":"2026-10-29"}),
        ]:
            wrong=copy.deepcopy(self.ois)
            mutate(wrong)
            with self.assertRaises(ValueError):
                self.make(ois=wrong)

    def test_no_future_cb_yield_or_bad_pair_universe(self):
        wrong=copy.deepcopy(self.cb)
        wrong["EUR"]["last_date"]=(date.fromisoformat(self.audit_day)+timedelta(days=2)).isoformat()
        with self.assertRaises(ValueError):
            self.make(banks=wrong)
        wrong=copy.deepcopy(self.rates)
        wrong["CHF"]["date"]=(date.fromisoformat(self.audit_day)+timedelta(days=1)).isoformat()
        with self.assertRaises(ValueError):
            self.make(rates=wrong)
        wrong=copy.deepcopy(self.pairs)
        del wrong["pairs"]["AUDCAD"]
        with self.assertRaises(ValueError):
            self.make(pairs=wrong)
        wrong=copy.deepcopy(self.pairs)
        wrong["macro_baseline_asof"]="2026-10-27"
        with self.assertRaises(ValueError):
            self.make(pairs=wrong)
        wrong=copy.deepcopy(self.candidate)
        wrong["safe_to_publish_D"]=True
        with self.assertRaises(ValueError):
            self.make(candidate=wrong)

    def test_responsive_dark_editorial_html_and_no_signal_promises(self):
        x=self.make()
        markup=render(x)
        self.assertIn('name="viewport"',markup)
        self.assertIn("RESEARCH BETA",markup)
        self.assertIn("28 coppie",markup)
        self.assertIn("Want",markup)
        self.assertIn("Can",markup)
        self.assertIn("6M indicativo, non ufficiale",markup)
        self.assertIn("Bank bill: solo contesto direzionale",markup)
        self.assertIn("NON ROBUSTA AI PESI",markup)
        self.assertEqual(markup.count('<article class="country">'),8)
        self.assertEqual(markup.count("<tr><td><b>"),28)
        self.assertIn(x["receipt_sha256"],markup)
        self.assertNotIn("<script",markup)
        self.assertNotIn("Nuovo segnale BUY",markup)

    def test_read_only_repository_files_stay_identical(self):
        root=ROOT/"live_data/sections"
        names=("D.json","PAIR_SETUP_OPERATIONAL_VIEW.json",
               "NATIVE_CB_DATA.json","OIS_OPERATIONAL_VIEW.json",
               "NATIVE_RATES_DATA.json")
        before={f:(root/f).read_bytes() for f in names}
        a=run()
        b=run()
        self.assertEqual(a["receipt_sha256"],b["receipt_sha256"])
        self.assertEqual(before,{f:(root/f).read_bytes() for f in names})


if __name__=="__main__":
    unittest.main()
