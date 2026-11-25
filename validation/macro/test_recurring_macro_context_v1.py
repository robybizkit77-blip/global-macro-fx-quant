import unittest
from datetime import datetime, timezone
from validation.macro.recurring_official_actuals_v1 import build, archive
from validation.macro.test_recurring_official_actuals_v1 import ABS,GDP,PCE,HTML_ABS,HTML_GDP,HTML_PCE,NOW
from validation.macro.recurring_macro_context_v1 import apply

class Tests(unittest.TestCase):
    def test_three_release_history_and_downstream_gdp_revision(self):
        source=lambda u: HTML_ABS if "abs.gov" in u else HTML_GDP if "/gdp-" in u else HTML_PCE
        items,checks=build({"events":[ABS,GDP,PCE]},NOW,fetch=source,clock=lambda:NOW)
        self.assertEqual(len(items),3)
        records=archive([],items,NOW)
        self.assertEqual(len(records),3)
        self.assertEqual(archive(records,items,NOW),records)
        import copy
        invalid=copy.deepcopy(records[0]); invalid['source_url']='https://example.com/wrong'
        with self.assertRaises(ValueError): archive([], [invalid], NOW)
        invalid=copy.deepcopy(records[0]); invalid['issuer_html_sha256']=''
        with self.assertRaises(ValueError): archive([], [invalid], NOW)
        later=datetime(2026,12,10,tzinfo=timezone.utc)
        self.assertEqual(archive(records,[],later),records)
        countries={"USD":{"growth":{"reference_quarter":"2026Q3","publisher_release_day":"2026-10-29"},"inflation":{"observation_period":"2026-09"}},"AUD":{"inflation":{"observation_period":"2026Q3"}}}
        apply(countries,records,"2026-11-25")
        self.assertEqual(countries["USD"]["growth"]["reported_value"],4.3)
        self.assertEqual(countries["USD"]["growth"]["prior_documented_quarter"]["reference_quarter"],"2026Q2")
        self.assertEqual(countries["USD"]["growth"]["prior_documented_quarter"]["reported_value"],2.2)
        self.assertEqual(len(countries["USD"]["issuer_releases"]),2)
        self.assertEqual(len(countries["AUD"]["issuer_releases"]),1)
        self.assertEqual(countries["AUD"]["inflation"]["observation_period"],"2026Q3")
        self.assertEqual(countries["USD"]["inflation"]["observation_period"],"2026-09")
    def test_does_not_overwrite_newer_quarter(self):
        items,_=build({"events":[GDP]},NOW,fetch=lambda u:HTML_GDP,clock=lambda:NOW)
        countries={"USD":{"growth":{"reference_quarter":"2026Q4","publisher_release_day":"2027-01-29"}}}
        apply(countries,archive([],items,NOW),"2027-02-01")
        self.assertEqual(countries["USD"]["growth"]["reference_quarter"],"2026Q4")
    def test_no_future_data(self):
        items,_=build({"events":[GDP]},NOW,fetch=lambda u:HTML_GDP,clock=lambda:NOW)
        c={"USD":{"growth":{"reference_quarter":"2026Q3","publisher_release_day":"2026-10-29"}}}
        apply(c,archive([],items,NOW),"2026-11-24")
        self.assertNotIn("issuer_releases",c["USD"])
