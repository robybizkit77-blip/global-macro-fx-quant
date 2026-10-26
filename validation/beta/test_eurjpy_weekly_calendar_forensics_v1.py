"""EURJPY exact same-day source calendar and OOS absence regression tests."""
from __future__ import annotations

from datetime import date, timedelta
import unittest

from validation.beta import eurjpy_weekly_calendar_forensics_v1 as m


def week_dates(start, n):
    return [
        [start+timedelta(days=7*i+j) for j in range(5)]
        for i in range(n)
    ]


class EURJPYWeeklyCalendarTests(unittest.TestCase):
    def test_fully_common_58_weeks_supports_first_oos(self):
        weeks=week_dates(date(2025,9,15),58)
        all_dates=[d for wk in weeks for d in wk]
        x=m.analyze_calendar(all_dates,all_dates,all_dates,
            start=weeks[0][0],end=weeks[-1][-1])
        self.assertEqual(x["exact_common_week_count"],58)
        self.assertEqual(x["longest_consecutive_exact_week_span"],58)
        self.assertTrue(x["full_exact_week_panel_ready"])
        self.assertEqual(x["weeks_no_triple"],0)

    def test_one_no_common_week_splits_the_52_week_train(self):
        weeks=week_dates(date(2025,9,15),58)
        fx=[x for wk in weeks for x in wk]
        eur=[x for i,wk in enumerate(weeks) for x in (wk[:2] if i==26 else wk)]
        jpy=[x for i,wk in enumerate(weeks) for x in (wk[3:] if i==26 else wk)]
        x=m.analyze_calendar(fx,eur,jpy,start=weeks[0][0],end=weeks[-1][-1])
        self.assertEqual(x["weeks_no_triple"],1)
        self.assertEqual(x["gaps"][0]["status"],
                         "UNMATCHED_EUR_JPY_FX_DATES_DESPITE_BOTH_PUBLISHING")
        self.assertEqual(x["longest_consecutive_exact_week_span"],31)
        self.assertFalse(x["full_exact_week_panel_ready"])
        self.assertFalse(x["asynchronous_cross_day_returns_used"])
        self.assertFalse(x["missing_values_interpolated"])

    def test_no_2y_week_identified_not_mislabeled_as_trade(self):
        w=week_dates(date(2025,9,15),4)
        all=[d for v in w for d in v]
        eur=[d for i,v in enumerate(w) for d in v if i!=2]
        x=m.analyze_calendar(all,eur,all,start=w[0][0],end=w[-1][-1])
        self.assertEqual(x["gaps"][0]["status"],"NO_ECB_EUR2Y_OBSERVATION_IN_WEEK")
        self.assertFalse(x["full_exact_week_panel_ready"])
        self.assertFalse(x["beta_promoted"])

    def test_missing_japan_entire_week_identified(self):
        w=week_dates(date(2025,9,15),4)
        all=[d for v in w for d in v]
        jpy=[d for i,v in enumerate(w) for d in v if i!=1]
        x=m.analyze_calendar(all,all,jpy,start=w[0][0],end=w[-1][-1])
        self.assertEqual(x["gaps"][0]["status"],"NO_MOF_JPY2Y_OBSERVATION_IN_WEEK")

    def test_source_date_invariants(self):
        one=date(2025,9,15)
        with self.assertRaisesRegex(ValueError,"invalid audit range"):
            m.analyze_calendar([],[],[],start=one+timedelta(days=10),end=one)
        with self.assertRaisesRegex(ValueError,"non-date source"):
            m.analyze_calendar(["2025-09-15"],[one],[one],
                               start=one,end=one+timedelta(days=4))

    def test_output_has_54_week_requirement_for_52w_prior_and_test(self):
        w=week_dates(date(2025,9,15),53)
        all=[d for v in w for d in v]
        x=m.analyze_calendar(all,all,all,start=w[0][0],end=w[-1][-1])
        self.assertEqual(x["theoretical_minimum_consecutive_weekly_fixings_for_first_52w_oos"],54)
        self.assertFalse(x["full_exact_week_panel_ready"])
        self.assertEqual(x["longest_consecutive_exact_week_span"],53)


if __name__=="__main__":
    unittest.main()
