#!/usr/bin/env python3
"""G8 NEWS_PULSE issuer actual bridge: real signed evidence and offline future GDP."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
import copy
import unittest

from validation.macro.build_g8_official_news_items_v1 import build
from validation.macro import capture_aud_labour_official_firstseen_v12 as aud
from validation.macro.test_capture_aud_labour_firstseen_v12 import (
    AFTER as AUD_AFTER, SEEN as AUD_SEEN, fetch as aud_fetch,
)
from validation.macro import capture_uk_ch_gdp_official_firstseen_v11 as v11
from validation.macro.test_capture_uk_ch_gdp_firstseen_v11 import (
    OFFICIAL, FORECASTS, UK_RELEASED, UK_OBSERVED, CH_RELEASED,
    CH_OBSERVED, fake_fetch,
)

UTC=timezone.utc

class G8OfficialNewsTests(unittest.TestCase):
    def test_signed_eci_and_canadian_gdp_not_survey_surprises(self):
        rows=build(datetime(2026,10,31,8,tzinfo=UTC))
        self.assertEqual({x["ccy"] for x in rows},{"USD","CAD"})
        self.assertEqual({x["event_type"] for x in rows},{"GROWTH","LABOUR_COST"})
        self.assertTrue(all(x["category"]=="MACRO_OFFICIAL_ACTUAL" for x in rows))
        self.assertTrue(all("NON con un consenso survey certificato" in x["detail"] for x in rows))
        self.assertTrue(all("Non attribuiamo causalmente" in x["detail"] for x in rows))
        self.assertTrue(all(x["source_url"].startswith("https://") for x in rows))
        self.assertIsNone(next(x for x in rows if x["ccy"]=="USD")["metric_id"])
        # The issuer event is historical, not a fake fresh headline in November.
        self.assertEqual(build(datetime(2026,11,11,9,tzinfo=UTC)),[])

    def test_uk_gdp_capture_becomes_post_event_observation(self):
        records,_=v11.capture(OFFICIAL,FORECASTS,[],UK_RELEASED,fake_fetch,
                               observed_clock=lambda: UK_OBSERVED)
        before=build(UK_RELEASED, v11_actuals=records)
        self.assertEqual(before,[],"No future actual before runner observation")
        after=build(UK_OBSERVED+timedelta(minutes=1),v11_actuals=records)
        uk=next(x for x in after if x["ccy"]=="GBP")
        self.assertEqual(uk["event_type"],"GROWTH")
        self.assertEqual(uk["as_of"],"2026-11-12")
        self.assertEqual(uk["metric_id"],"UK_REAL_GDP_PRELIM_QOQ_SA")
        self.assertIn("+0,5%",uk["title"])
        self.assertIn("-0,2 punti percentuali",uk["detail"])
        self.assertNotIn("sorpresa positiva certificata",uk["detail"])

    def test_swiss_flash_has_no_forged_forecast(self):
        prior,_=v11.capture(OFFICIAL,FORECASTS,[],UK_RELEASED,fake_fetch,
                             observed_clock=lambda:UK_OBSERVED)
        rows,_=v11.capture(OFFICIAL,FORECASTS,prior,CH_RELEASED,fake_fetch,
                           observed_clock=lambda:CH_OBSERVED)
        news=build(CH_OBSERVED+timedelta(minutes=1),v11_actuals=rows)
        ch=next(x for x in news if x["ccy"]=="CHF")
        self.assertIn("non disponibile",ch["detail"])
        self.assertIn("aggiustamento",ch["detail"])
        self.assertEqual(ch["source_url"],"https://www.seco.admin.ch/en/gdp-flash")

    def test_signed_archive_tampering_is_blocked(self):
        records,_=v11.capture(OFFICIAL,FORECASTS,[],UK_RELEASED,fake_fetch,
                               observed_clock=lambda:UK_OBSERVED)
        bad=copy.deepcopy(records)
        bad[0]["actual_percent"]=19.0
        with self.assertRaises(ValueError):
            build(UK_OBSERVED+timedelta(minutes=1),v11_actuals=bad)

    def test_abs_sa_unemployment_rate_is_not_a_positive_fx_change_or_survey_surprise(self):
        rows,_=aud.capture([],AUD_AFTER,aud_fetch,observed_clock=lambda:AUD_SEEN)
        before=build(AUD_AFTER,v12_aud_actuals=rows)
        self.assertEqual(before,[], "Source not observed until runner's actual parse timestamp")
        news=build(AUD_SEEN+timedelta(minutes=1),v12_aud_actuals=rows)
        item=next(x for x in news if x["metric_id"]=="AU_UNEMP_RATE_SA")
        self.assertEqual(item["ccy"],"AUD")
        self.assertEqual(item["event_type"],"LABOUR")
        self.assertEqual(item["as_of"],"2026-11-19")
        self.assertIn("4,9%",item["title"])
        self.assertNotIn("+4,9%",item["title"],"Unemployment is a level, not positive change")
        self.assertIn("non disponibile",item["detail"])
        self.assertIn("Non attribuiamo causalmente",item["detail"])
        self.assertFalse(item.get("FX_signal"))
        changed=copy.deepcopy(rows)
        changed[0]["survey_consensus_percent"]=4.7
        with self.assertRaises(ValueError):
            build(AUD_SEEN+timedelta(minutes=1),v12_aud_actuals=changed)

    def test_unsupported_g8_calendar_alone_does_not_create_actuals(self):
        rows=build(datetime(2026,11,11,9,tzinfo=UTC))
        self.assertFalse(any(x["ccy"] in {"AUD","NZD","JPY","EUR"} for x in rows))
        self.assertFalse(any(x.get("FX_signal") for x in rows))
        with self.assertRaisesRegex(ValueError,"Offset-aware"):
            build(datetime(2026,11,11,9))

if __name__=="__main__":
    unittest.main()
