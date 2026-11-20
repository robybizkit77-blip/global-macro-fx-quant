#!/usr/bin/env python3
"""Deterministic no-network tests for the free GitHub hourly market desk."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
from datetime import datetime,timezone,timedelta
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("free_desk",ROOT/"validation/home/build_free_hourly_desk_v1.py")
free=importlib.util.module_from_spec(spec)
spec.loader.exec_module(free)
NOW=datetime(2026,11,13,13,14,tzinfo=timezone.utc)
FIXTURE=ROOT/"validation/home/fixtures/free_hourly_desk_2026-11-13.json"

class FreeDeskTest(unittest.TestCase):
 def setUp(self):
  tmp=tempfile.TemporaryDirectory()
  self.addCleanup(tmp.cleanup)
  self.root=Path(tmp.name)
  self.sections=self.root/"live_data/sections"
  self.sections.mkdir(parents=True)
  fixture=json.loads(FIXTURE.read_text(encoding="utf-8"))
  for name,data in fixture.items():
   (self.sections/(name+".json")).write_text(json.dumps(data),encoding="utf-8")
  fx={"schema":"GMFQ_ECB_G8_PRICE_HISTORY_V1","status":"CURRENT_OFFICIAL_HISTORY","base":"EUR",
      "source_url":free.ECB_FIXING,"last_as_of":"2026-11-13",
      "rows":[{"Date":"2026-11-12","USD":1.0968,"JPY":174.85},
              {"Date":"2026-11-13","USD":1.0992,"JPY":175.84}]}
  (self.sections/"ECB_G8_PRICE_HISTORY.json").write_text(json.dumps(fx),encoding="utf-8")
  market=self.root/"site/fx-quant-v2"
  market.mkdir(parents=True)
  closes={k:{"date":"2026-11-12","value":v,"previous":prior,"source_url":f"https://example.com/{k}",
             "quality":"PUBLISHED_SOURCE_RESEARCH_ONLY","not_intraday":True}
          for k,v,prior in (("SP500",7323.63,7340.53),("VIX",24.56,25.46),("HY_OAS",3.47,3.43))}
  (market/"cross-asset-live-data.json").write_text(json.dumps({"streams":closes}),encoding="utf-8")
 def build(self,now=NOW,previous=None,rss=None):
  return free.build(self.root,now,previous=previous,rss=rss if rss is not None else {"headlines":[]})
 def test_no_paid_runtime_contract(self):
  workflow=(ROOT/".github/workflows/next-independent-ai-hourly-desk-v1.yml").read_text(encoding="utf-8")
  self.assertNotIn("MARKET_DESK_API_KEY",workflow)
  self.assertNotIn("openai.com",workflow)
  self.assertNotIn("secrets.FXQ_MARKET_DESK_API_KEY",workflow)
  self.assertNotIn("run_independent_hourly_alert_v1.py",workflow)
  self.assertIn("build_free_hourly_desk_v1.py",workflow)
  self.assertIn("--check-output",workflow)
  self.assertIn("hourly-market-desk-check.json",workflow)
  self.assertIn("cron: '17 * * * *'",workflow)
  self.assertNotIn("mcp__Automations",workflow)
 def test_refresh_and_publication_follow_production_source_runs(self):
  workflow=(ROOT/".github/workflows/next-independent-ai-hourly-desk-v1.yml").read_text()
  for source in ("Calendar News Operational Refresh V1", "FX Quant V2 Cross-Asset Published Source Refresh"):
   self.assertIn(source, workflow)
  self.assertIn("github.event.workflow_run.head_branch == 'main'", workflow)
  self.assertIn("github.event.workflow_run.conclusion == 'success'", workflow)
  self.assertIn("Verify the public edition and its source receipt", workflow)
  cross=(ROOT/".github/workflows/fx-quant-v2-cross-asset-sources.yml").read_text()
  self.assertIn("workflows: ['Calendar News Operational Refresh V1']", cross)
  self.assertIn("github.event.workflow_run.head_branch == 'main'", cross)
 def test_later_nasdaq_close_updates_narrative_while_sp500_waits(self):
  path=self.root/"site/fx-quant-v2/cross-asset-live-data.json"
  feed=json.loads(path.read_text())
  feed["streams"]["NASDAQCOM"]={**feed["streams"]["SP500"],"date":"2026-11-13",
   "value":23879.2,"previous":24429.88,"source_url":"https://example.com/NASDAQCOM"}
  path.write_text(json.dumps(feed))
  result=self.build()
  row=next(row for row in result["news"] if row["market_area"]=="RISCHIO")
  self.assertEqual(row["headline"],"Il Nasdaq Composite scende")
  self.assertIn("Nasdaq Composite −2,25%",row["evidence"])
  self.assertNotIn("S&P 500",row["evidence"])
 def test_overview_describes_the_fixing_and_previous_close_with_sources(self):
  r=self.build()
  self.assertEqual(r["schema"],free.SCHEMA)
  self.assertEqual(r["status"],"ACTIVE")
  self.assertTrue(r["provenance"]["no_paid_api"])
  self.assertTrue(r["provenance"]["chatgpt_automation_unchanged"])
  self.assertGreaterEqual(len(r["news"]),3)
  self.assertLessEqual(len(r["news"]),6)
  self.assertEqual(r["headline"],"Dollaro misto")
  self.assertIn("Il 13 novembre il dollaro ha ceduto contro l’euro e guadagnato contro lo yen",r["lead"])
  self.assertIn("Alla chiusura del 12 novembre, Wall Street ha perso terreno e il premio sul debito più rischioso è salito",r["lead"])
  for key in ("headline","lead","desk_judgment","fx_implications","what_changed","watch","contrary_evidence"):
   self.assertNotRegex(r[key],r"\d+(?:,\d+)?\s*(?:%|pb\b|punti\b)|(?i:fixing|\bBCE\b)")
  fx=next(item for item in r["news"] if item["market_area"]=="FOREX")
  self.assertEqual(fx["headline"],"Dollaro misto")
  self.assertIn("ceduto contro l’euro e guadagnato contro lo yen",fx["analysis"])
  self.assertIn("Al fixing BCE del 13 novembre, EUR/USD ha segnato +0,22% e USD/JPY +0,35%",fx["evidence"])
  risk=next(item for item in r["news"] if item["market_area"]=="RISCHIO")
  self.assertIn("Wall Street ha perso terreno",risk["analysis"])
  self.assertIn("S&P 500 −0,23%, VIX −0,90 punti e spread high yield +4 pb",risk["evidence"])
  for item in (fx,risk):
   self.assertNotRegex(item["headline"]+" "+item["analysis"],r"\d+(?:,\d+)?\s*(?:%|pb\b)|(?i:fixing|\bBCE\b)")
  self.assertIn("VIX è sceso",r["contrary_evidence"])
  self.assertIn(free.ECB_FIXING,r["provenance"]["web_source_urls"])
  self.assertTrue(all(x["sources"] for x in r["news"]))
  self.assertEqual(sorted(set(u for n in r["news"] for u in n["sources"])),r["provenance"]["web_source_urls"])
  self.assertEqual(r["edition_time_rome"],"2026-11-13 14:14")
 def test_macro_release_and_next_event_use_published_time_and_rome_date(self):
  path=self.sections/"NEWS_PULSE_OPERATIONAL.json"
  pulse=json.loads(path.read_text())
  release={"category":"MACRO_OFFICIAL_ACTUAL","as_of":"2026-11-13","ccy":"AUD",
           "metric_id":"AU_UNEMP_RATE_SA","first_runner_observed_at_utc":"2026-11-13T02:00:00Z",
           "title":"Australia · tasso di disoccupazione destagionalizzato, ottobre 2026: 4,9%",
           "source_url":"https://www.abs.gov.au/statistics/labour/labour-force"}
  pulse["items"].insert(0,release)
  path.write_text(json.dumps(pulse))
  calendar=self.sections/"CALENDAR_OPERATIONAL_VIEW.json"
  cpi={"title":"Japan Consumer Price Index","ccy":"JPY","event_type":"INFLATION",
       "date":"2026-11-14","time_local":"08:30","timezone":"Asia/Tokyo",
       "status":"UPCOMING","importance":"HIGH","quality":"OFFICIAL_CONFIRMED"}
  passed={**cpi,"date":"2026-11-13"}
  calendar.write_text(json.dumps({"events":[passed,cpi]}))
  series={"AUD":[{"id":"AU_UNEMP_RATE_history_value","unit":"%","frequency":"M",
                  "dates":["2026-09-01","2026-10-01"],"values":[4.7,4.9]}]}
  macro_path=self.sections/"MACRO_SERIES.json"
  macro_path.write_text(json.dumps(series))
  r=self.build()
  self.assertTrue(r["lead"].startswith("In Australia la disoccupazione è aumentata a ottobre."))
  self.assertNotIn("4,9",r["lead"])
  macro=next(item for item in r["news"] if item["market_area"]=="MACRO")
  self.assertEqual(macro["headline"],"In Australia la disoccupazione è aumentata a ottobre")
  self.assertNotIn("4,9%",macro["headline"]+" "+macro["analysis"])
  self.assertIn("4,9%",macro["evidence"])
  self.assertIn("14 novembre alle 00:30 italiane",r["fx_implications"])
  self.assertIn("BoJ",r["fx_implications"])
  self.assertNotIn("13 novembre alle 00:30",r["fx_implications"])
  series["AUD"][0]["dates"][0]="2026-08-01"
  macro_path.write_text(json.dumps(series))
  self.assertIn("L’Australia ha pubblicato il dato sulla disoccupazione di ottobre",self.build()["lead"])
  release["first_runner_observed_at_utc"]="2026-11-13T23:59:00Z"
  path.write_text(json.dumps(pulse))
  self.assertNotIn("disoccupazione",self.build()["lead"])
 def test_later_fixing_changes_the_edition_without_news_pulse_update(self):
  first=self.build()
  p=self.sections/"ECB_G8_PRICE_HISTORY.json"
  d=json.loads(p.read_text())
  d["rows"][-1]["USD"]=1.0868
  p.write_text(json.dumps(d))
  second=self.build(now=NOW+timedelta(hours=1),previous=first)
  self.assertNotEqual(first["material_digest"],second["material_digest"])
  self.assertEqual(second["headline"],"Dollaro in rialzo")
  d["status"]="ESTIMATED"
  p.write_text(json.dumps(d))
  invalid=self.build()
  self.assertNotIn("Dollaro",invalid["headline"])
  self.assertNotIn("USD/JPY",invalid["lead"])
 def test_no_recycled_hourly_story(self):
  first=self.build()
  again=self.build(now=NOW+timedelta(hours=1),previous=first)
  self.assertEqual(again,first)
  self.assertEqual(first["generated_at_utc"],again["generated_at_utc"])
  self.assertEqual(first["material_digest"],again["material_digest"])

 def test_hourly_check_receipt_does_not_recycle_edition(self):
  first=self.build()
  new_time=NOW+timedelta(hours=1)
  same=self.build(now=new_time,previous=first)
  self.assertEqual(first,same)
  receipt=free.make_check_receipt(new_time,same,previous=first)
  self.assertEqual(receipt["schema"],"GMFQ_NEXT_HOURLY_CHECK_V1")
  self.assertEqual(receipt["status"],"VERIFIED")
  self.assertFalse(receipt["edition_changed"])
  self.assertEqual(receipt["edition_generated_at_utc"],first["generated_at_utc"])
  self.assertEqual(receipt["material_digest"],first["material_digest"])
  self.assertEqual(receipt["checked_at_utc"],"2026-11-13T14:14:00Z")
  self.assertNotIn("checked_at_utc",same)
 def test_receipt_new_edition_and_aware_clock(self):
  first=self.build()
  receipt=free.make_check_receipt(NOW,first)
  self.assertTrue(receipt["edition_changed"])
  self.assertEqual(receipt["edition_generated_at_utc"],receipt["checked_at_utc"])
  with self.assertRaises(ValueError):
   free.make_check_receipt(datetime(2026,11,13,13,14),first)
  with self.assertRaises(ValueError):
   free.make_check_receipt(NOW,{"schema":free.SCHEMA,"status":"FAILED"})

 def test_new_market_input_changes_edition(self):
  first=self.build()
  p=self.sections/"NEWS_PULSE_OPERATIONAL.json"
  x=json.loads(p.read_text(encoding="utf-8"))
  repricing=next(item for item in x["items"] if item["category"]=="FUTURES_IMPLIED_REPRICING" and item["ccy"]=="JPY")
  repricing["title"]="JPY: repricing implicito da futures più hawkish (+7.2 bp 6M in 1D)"
  p.write_text(json.dumps(x),encoding="utf-8")
  new=self.build(previous=first,now=NOW+timedelta(hours=1))
  self.assertNotEqual(first["material_digest"],new["material_digest"])
  self.assertNotEqual(first["generated_at_utc"],new["generated_at_utc"])
  self.assertEqual(new["history"][0]["headline"],first["headline"])
 def test_rss_source_is_only_headline_not_imagined_policy(self):
  rss={"headlines":[{"title":"Bank of Canada publishes outlook survey",
      "source_id":"BOC_PRESS","ccy":"CAD",
      "published_at_utc":"2026-11-13T12:30:00Z",
      "url":"https://www.bankofcanada.ca/2026/11/outlook-survey/",
      "desk_context":{"why_watch":"Indagine sulle aspettative delle imprese.",
      "verify_next":"Confrontare dati, precedenti e pricing BoC."}}]}
  out=self.build(rss=rss)
  self.assertTrue(any("outlook survey" in x["headline"] for x in out["news"]))
  self.assertFalse(any("BoC ha tagliato" in x["analysis"] for x in out["news"]))
  self.assertTrue(any("bankofcanada.ca" in u for u in out["provenance"]["web_source_urls"]))
 def test_future_dates_do_not_create_market_reaction(self):
  p=self.sections/"NEWS_PULSE_OPERATIONAL.json"
  x=json.loads(p.read_text(encoding="utf-8"))
  x["content_as_of"]="2026-11-14"
  p.write_text(json.dumps(x),encoding="utf-8")
  with self.assertRaisesRegex(ValueError,"window"):
   self.build()
 def test_malformed_rss_does_not_publish_fake_source(self):
  rss={"headlines":[{"title":"Unexpected rate cut", "source_id":"FED_PRESS",
   "published_at_utc":"2026-11-13T12:30:00Z",
   "url":"javascript:alert(1)","desk_context":{}}]}
  out=self.build(rss=rss)
  self.assertFalse(any(x["headline"]=="Unexpected rate cut" for x in out["news"]))
 def test_institutional_notices_do_not_displace_news_with_market_context(self):
  base={"ccy":"USD","published_at_utc":"2026-11-13T12:30:00Z"}
  notice={**base,"title":"Federal Reserve issues enforcement notice",
          "url":"https://www.federalreserve.gov/notice","desk_context":{"topic":"INSTITUTIONAL"}}
  policy={**base,"title":"Federal Reserve monetary policy statement",
          "url":"https://www.federalreserve.gov/statement","desk_context":{"topic":"CB_POLICY"}}
  out=self.build(rss={"headlines":[notice,policy]})
  self.assertFalse(any(notice["url"] in item["sources"] for item in out["news"]))
  story=next(item for item in out["news"] if policy["url"] in item["sources"])
  self.assertIn("attese sui tassi",story["analysis"])
  self.assertNotIn("taglio",story["analysis"])
 def test_old_pulse_stops_refresh(self):
  with self.assertRaisesRegex(ValueError,"window"):
   self.build(now=NOW+timedelta(days=9))
 def test_no_external_api_on_explicit_rss_fixture(self):
  # Explicit RSS injection provides complete offline path without API calls.
  r=self.build(rss={"headlines":[]})
  self.assertEqual(r["engine"],"FREE_DETERMINISTIC_CROSS_ASSET_RESEARCH")

if __name__=="__main__":
 unittest.main(verbosity=2)
