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

class FreeDeskTest(unittest.TestCase):
 def build(self,now=NOW,previous=None,rss=None,root=ROOT):
  return free.build(root,now,previous=previous,rss=rss if rss is not None else {"headlines":[]})
 def test_no_paid_runtime_contract(self):
  workflow=(ROOT/".github/workflows/next-independent-ai-hourly-desk-v1.yml").read_text(encoding="utf-8")
  self.assertNotIn("MARKET_DESK_API_KEY",workflow)
  self.assertNotIn("openai.com",workflow)
  self.assertNotIn("secrets.FXQ_MARKET_DESK_API_KEY",workflow)
  self.assertNotIn("run_independent_hourly_alert_v1.py",workflow)
  self.assertIn("build_free_hourly_desk_v1.py",workflow)
  self.assertIn("cron: '17 * * * *'",workflow)
  self.assertNotIn("mcp__Automations",workflow)
 def test_free_overview_is_general_and_source_linked(self):
  r=self.build()
  self.assertEqual(r["schema"],free.SCHEMA)
  self.assertEqual(r["status"],"ACTIVE")
  self.assertTrue(r["provenance"]["no_paid_api"])
  self.assertTrue(r["provenance"]["chatgpt_automation_unchanged"])
  self.assertGreaterEqual(len(r["news"]),3)
  self.assertLessEqual(len(r["news"]),6)
  self.assertIn("dollaro",r["headline"].lower())
  self.assertIn("euro",r["desk_judgment"])
  self.assertIn("volatilità",r["desk_judgment"])
  self.assertIn("oro",r["desk_judgment"].lower())
  self.assertIn("petrolio",r["desk_judgment"].lower())
  self.assertIn("Fed",r["fx_implications"])
  self.assertIn("BoJ",r["fx_implications"])
  self.assertNotIn("non possiamo",r["lead"].lower())
  self.assertTrue(all(x["sources"] for x in r["news"]))
  self.assertEqual(sorted(set(u for n in r["news"] for u in n["sources"])),r["provenance"]["web_source_urls"])
  self.assertEqual(r["edition_time_rome"],"2026-11-13 14:14")
 def test_no_recycled_hourly_story(self):
  first=self.build()
  again=self.build(now=NOW+timedelta(hours=1),previous=first)
  self.assertEqual(again,first)
  self.assertEqual(first["generated_at_utc"],again["generated_at_utc"])
  self.assertEqual(first["material_digest"],again["material_digest"])
 def test_new_market_input_changes_edition(self):
  first=self.build()
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp)/"live_data/sections"
   d.mkdir(parents=True)
   for name in ("NEWS_PULSE_OPERATIONAL.json","ESTIMATED_RESIDUAL_GAPS.json","CALENDAR_OPERATIONAL_VIEW.json"):
    (d/name).write_bytes((ROOT/"live_data/sections"/name).read_bytes())
   p=d/"NEWS_PULSE_OPERATIONAL.json"
   x=json.loads(p.read_text(encoding="utf-8"))
   x["items"][0]["title"]="JPY: repricing implicito da futures più hawkish (+7.2 bp 6M in 1D)"
   p.write_text(json.dumps(x))
   new=self.build(previous=first,root=Path(tmp),now=NOW+timedelta(hours=1))
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
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp)/"live_data/sections"
   d.mkdir(parents=True)
   for name in ("NEWS_PULSE_OPERATIONAL.json","ESTIMATED_RESIDUAL_GAPS.json","CALENDAR_OPERATIONAL_VIEW.json"):
    (d/name).write_bytes((ROOT/"live_data/sections"/name).read_bytes())
   p=d/"NEWS_PULSE_OPERATIONAL.json";x=json.loads(p.read_text())
   x["content_as_of"]="2026-11-14";p.write_text(json.dumps(x))
   with self.assertRaisesRegex(ValueError,"window"):
    self.build(root=Path(tmp))
 def test_malformed_rss_does_not_publish_fake_source(self):
  rss={"headlines":[{"title":"Unexpected rate cut", "source_id":"FED_PRESS",
   "published_at_utc":"2026-11-13T12:30:00Z",
   "url":"javascript:alert(1)","desk_context":{}}]}
  out=self.build(rss=rss)
  self.assertFalse(any(x["headline"]=="Unexpected rate cut" for x in out["news"]))
 def test_old_pulse_stops_refresh(self):
  with self.assertRaisesRegex(ValueError,"window"):
   self.build(now=NOW+timedelta(days=9))
 def test_no_external_api_on_explicit_rss_fixture(self):
  # Explicit RSS injection provides complete offline path without API calls.
  r=self.build(rss={"headlines":[]})
  self.assertEqual(r["engine"],"FREE_DETERMINISTIC_CROSS_ASSET_RESEARCH")

if __name__=="__main__":
 unittest.main(verbosity=2)
