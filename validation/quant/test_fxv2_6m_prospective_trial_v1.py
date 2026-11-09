#!/usr/bin/env python3
"""Future-only experiment: synthetic examples must never enter live journals."""
import copy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

from validation.quant.fxv2_6m_prospective_trial_v1 import (
    FX_PATH, QUOTES_PATH, MACRO_PATH, POLICY_PATH,
    SCHEMA, OUT_SCHEMA, seal, freeze, observe, policy_ok,
    verified_journal, verified_outcomes,
)

ROME=ZoneInfo("Europe/Rome")
def at(s): return datetime.fromisoformat(s).replace(tzinfo=ROME)
def fixture():
    policy=json.loads(POLICY_PATH.read_text())
    fx=json.loads(FX_PATH.read_text())
    quotes=[json.loads(s) for s in QUOTES_PATH.read_text().splitlines() if s.strip()]
    macro=json.loads(MACRO_PATH.read_text())
    # Fixed pre-registration fixture: the LIVE ECB history now extends past
    # Nov 06. Truncate to the *real* Nov 04 reference fixing before appending
    # two synthetic test-only sessions. Never append backward/duplicate dates
    # or relax the strict chronological validator.
    base_day="2026-11-04"
    base_idx=next((i for i,r in enumerate(fx["rows"]) if r["Date"]==base_day),None)
    assert base_idx is not None and base_idx >= 100, "Missing real Nov 04 ECB fixture anchor"
    fx["rows"]=fx["rows"][:base_idx+1]
    assert fx["rows"][-1]["Date"]==base_day
    last=copy.deepcopy(fx["rows"][-1])
    for d in ("2026-11-05","2026-11-06"):
        row={**last,"Date":d,"USD":last["USD"]*1.002,"CHF":last["CHF"]*.999}
        fx["rows"].append(row);last=row
    fx["last_as_of"]="2026-11-06"
    fx["row_count"]=len(fx["rows"])
    return policy,fx,quotes,macro

class Preregistered6mProspectiveTests(unittest.TestCase):
    def test_real_preregistered_contract_not_tradable(self):
        p,_,_,_=fixture()
        policy_ok(p)
        self.assertEqual(p["earliest_eligible_capture_rome"],"2026-11-06")
        self.assertFalse(p["eligible_for_trading"])
        self.assertEqual(p["analysis_controls"]["minimum_distinct_capture_days_for_inferential_review"],60)
        self.assertEqual(p["target"]["horizon"],"FIVE_FUTURE_ECB_REFERENCE_FIXING_SESSIONS")

    def test_earliest_legitimate_synthetic_cutoff_and_28_pair_abstentions(self):
        p,fx,q,m=fixture()
        now=at("2026-11-06T20:15:00")
        doc,status=freeze(now,p,fx,q,m,[])
        self.assertEqual(status,"FROZEN_PROSPECTIVE_COHORT")
        self.assertEqual(doc["schema"],SCHEMA)
        self.assertEqual(doc["rome_day"],"2026-11-06")
        self.assertEqual(len(doc["pairs"]),28)
        self.assertEqual(doc["frozen_sha256"],seal({k:v for k,v in doc.items() if k!="frozen_sha256"}))
        self.assertFalse(doc["future_price_observed_at_capture"])
        self.assertFalse(doc["eligible_for_fx_engine"])
        self.assertTrue(doc["experimental_not_trading"])
        self.assertEqual(doc["pairs"]["AUD/CAD"]["status"],"ABSTAIN_NO_SUPPORTED_6M_SOURCE")
        self.assertIsNone(doc["pairs"]["AUD/CAD"]["experimental_rate_hypothesis_sign"])
        for v in doc["pairs"].values():
            self.assertIsNone(v["expected_fx_return"])
            self.assertIsNone(v["trade_signal"])
        # The next available identical-contract pair has last market date
        # Wed Nov 4, captured no later than Fri Nov 6; directional but not
        # a bank OIS signal. The USD leg rose less than CHF fell.
        row=doc["pairs"]["USD/CHF"]
        self.assertEqual(row["last_rate_market_date"],"2026-11-04")
        self.assertEqual(row["source_lag_ecb_sessions"],2)
        self.assertEqual(row["status"],"FROZEN_EXPERIMENTAL_DIRECTION")
        self.assertEqual(row["rate_change_bp"],2.0)
        self.assertEqual(row["experimental_rate_hypothesis_sign"],1)
        self.assertEqual(row["base_contract"],"ZQJ2027")
        self.assertEqual(row["quote_contract"],"SA3M2027")
        self.assertLessEqual(row["feature_first_usable_at_utc"],doc["captured_at_utc"])
        self.assertEqual(verified_journal([doc],seal(p)),{"2026-11-06"})
        duplicate,msg=freeze(now,p,fx,q,m,[doc])
        self.assertIsNone(duplicate)
        self.assertEqual(msg,"ALREADY_FROZEN_NO_OVERWRITE")

    def test_never_reconstruct_pre_registration_or_missing_ecb_fixing(self):
        p,fx,q,m=fixture()
        for dt in ("2026-11-05T20:00:00","2026-11-06T18:59:00",
                   "2026-11-07T20:00:00"):
            with self.assertRaisesRegex(ValueError,"not an eligible"):
                freeze(at(dt),p,fx,q,m,[])
        fx["rows"].pop()
        fx["last_as_of"]="2026-11-05"
        fx["row_count"]=len(fx["rows"])
        no,status=freeze(at("2026-11-06T20:00:00"),p,fx,q,m,[])
        self.assertIsNone(no)
        self.assertEqual(status,"NO_SAME_DAY_OFFICIAL_ECB_FIXING")

    def test_no_future_quote_used_or_roll_signal(self):
        p,fx,q,m=fixture()
        delayed=copy.deepcopy(q)
        for r in delayed:
            if (r["currency"]=="CHF" and r["observed_under_horizon"]=="6m"
                and r["observation_date"]=="2026-11-04"):
                r["first_seen_at_utc"]="2026-11-07T06:00:00Z"
        doc,_=freeze(at("2026-11-06T20:00:00"),p,fx,delayed,m,[])
        self.assertNotEqual(doc["pairs"]["USD/CHF"]["status"],"FROZEN_EXPERIMENTAL_DIRECTION")
        self.assertIsNone(doc["pairs"]["USD/CHF"]["experimental_rate_hypothesis_sign"])

    def test_future_observer_after_five_REAL_future_fixings_only(self):
        p,fx,q,m=fixture()
        doc,_=freeze(at("2026-11-06T20:00:00"),p,fx,q,m,[])
        rows=observe(at("2026-11-06T20:01:00"),p,fx,[doc],[])
        self.assertEqual(rows,[])
        synthetic=copy.deepcopy(fx)
        for d in ("2026-11-09","2026-11-10","2026-11-11","2026-11-12","2026-11-13"):
            last=synthetic["rows"][-1]
            row={**last,"Date":d,"CHF":last["CHF"]*1.004}
            synthetic["rows"].append(row)
        synthetic["last_as_of"]="2026-11-13"
        synthetic["row_count"]=len(synthetic["rows"])
        matured=observe(at("2026-11-13T20:00:00"),p,synthetic,[doc],[])
        self.assertEqual(len(matured),doc["new_experimental_directions"])
        self.assertGreater(len(matured),0)
        for r in matured:
            self.assertEqual(r["schema"],OUT_SCHEMA)
            self.assertEqual(r["t5_fixing_date"],"2026-11-13")
            self.assertFalse(r["statistically_validated"])
            self.assertIsNone(r["trade_PNL"])
            self.assertIsNone(r["alpha"])
            self.assertEqual(r["observation_sha256"],seal({
                k:v for k,v in r.items() if k!="observation_sha256"
            }))
        self.assertEqual(observe(at("2026-11-13T20:00:00"),p,synthetic,[doc],matured),[])
        verified_outcomes(matured,{doc["rome_day"]:doc})

    def test_tampering_rejected(self):
        p,fx,q,m=fixture()
        doc,_=freeze(at("2026-11-06T20:00:00"),p,fx,q,m,[])
        bad=copy.deepcopy(doc)
        bad["pairs"]["USD/CHF"]["rate_change_bp"]=800
        with self.assertRaisesRegex(ValueError,"tampered"):
            verified_journal([bad],seal(p))
        changed=copy.deepcopy(p)
        changed["signal_definition"]["magnitude_threshold_abs_bp"]=0
        with self.assertRaisesRegex(ValueError,"preregistration"):
            policy_ok(changed)
        with self.assertRaisesRegex(ValueError,"journal"):
            # original payload hash cannot silently be rebound to another
            # experiment policy.
            verified_journal([doc],seal({**p,"notes":"version drift"}))

if __name__=="__main__": unittest.main()
