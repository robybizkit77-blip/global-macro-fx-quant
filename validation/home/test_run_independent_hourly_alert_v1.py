#!/usr/bin/env python3
"""Offline CI tests: prevent ungrounded hourly publication and ChatGPT coupling."""
import importlib.util
import json
from pathlib import Path
import unittest
from datetime import datetime,timezone
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("standalone_hourly",ROOT/"validation/home/run_independent_hourly_alert_v1.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
NOW=datetime(2026,11,13,12,20,tzinfo=timezone.utc)
SRC=["https://www.federalreserve.gov/newsevents/pressreleases/monetary20261113a.htm",
     "https://www.reuters.com/world/europe/economic-developments-2026-11-13/",
     "https://www.bls.gov/news.release/ppi.htm"]
def sample():
    d={"headline":"Mercati in equilibrio instabile tra crescita, tassi relativi e rischio globale",
       "lead":"L'ultimo quadro multi-asset indica attese monetarie che evolvono in modo disomogeneo. I movimenti valutari richiedono un confronto fra aree, non una lettura isolata.",
       "news":[
           {"headline":"Dollaro e aspettative sui rendimenti relativi",
            "analysis":"Il quadro dei tassi relativi orienta il dollaro senza attribuire i movimenti a operatori non identificati. La differenza con l'euro rimane la verifica più importante.",
            "kind":"NEWS","published_date":"2026-11-13","event_date":"2026-11-13","market_area":"FX",
            "sources":[SRC[0]]},
           {"headline":"Azionario e credito con segnali da confrontare",
            "analysis":"Le chiusure precedenti e il credito mostrano elementi da leggere insieme alla volatilità. L'alternativa è che il movimento rifletta una rotazione piuttosto che un cambio di regime.",
            "kind":"FOLLOW_UP","published_date":"2026-11-13","event_date":"2026-11-12","market_area":"EQUITY",
            "sources":[SRC[1]]},
           {"headline":"Dati dei prezzi USA come catalizzatore",
            "analysis":"Il dato sui prezzi alla produzione è in calendario. Una sorpresa rispetto al consenso potrebbe alterare il percorso Fed prezzato dal mercato; il momento di uscita va rispettato.",
            "kind":"PREVIEW","published_date":"2026-11-13","event_date":"2026-11-13","market_area":"MACRO",
            "sources":[SRC[2]]}],
       "desk_judgment":"La tesi principale è il confronto fra banche centrali e attese monetarie. Una prova contraria sarebbe un rialzo del dollaro con differenziale in calo su osservazioni confrontabili.",
       "fx_implications":"Per EUR/USD conta la differenza tra aspettative Fed e BCE; USD/JPY richiede anche la BoJ e il rischio globale. Nessun movimento di una sola valuta spiega tutta la coppia.",
       "what_changed":"I riferimenti di mercato datati aggiungono un segnale recente, ma il tema di fondo rimane il pricing relativo delle banche centrali.",
       "contrary_evidence":"Il rischio globale e il comportamento dei tassi possono divergere dal Forex: una correlazione temporanea non prova un flusso.",
       "watch":"La prossima pubblicazione macro e i cambiamenti nei differenziali, nel credito e nelle valute cicliche faranno capire se la tesi si rafforza o si indebolisce."}
    return d
def raw(doc=None,sources=None):
    return {"status":"completed","output":[
        {"type":"web_search_call","action":{"type":"search","sources":[{"url":x,"title":"Fonte"} for x in (sources or SRC)]}},
        {"type":"message","content":[{"type":"output_text","text":json.dumps(doc or sample(),ensure_ascii=False)}]}]}

class DeskTests(unittest.TestCase):
    def test_canonical_is_copied_not_rewritten(self):
        policy=(ROOT/"validation/home/CHATGPT_ALERT_EDITORIAL_V3_CANONICAL.md").read_text()
        self.assertTrue(policy.startswith("# GLOBAL MACRO & CROSS-ASSET RESEARCH DESK — STANDARD EDITORIALE CANONICO V3"))
        self.assertIn("METODO DI INTERPRETAZIONE «SERAFINI»",policy)
        self.assertIn("GEOPOLITICA E POLICY",policy)
        self.assertIn("Frequenza oraria invariata",policy)
    def test_market_context_is_dated_and_cross_asset(self):
        data=mod.source_bundle(ROOT,NOW)
        self.assertGreaterEqual(len(data["observed_market_events"]),4)
        self.assertIn("news_content_as_of",data)
        self.assertGreaterEqual(len(data["commodity_futures_proxies"]),2)
        self.assertTrue(any(x["category"]=="MARKET_CREDIT_OAS" for x in data["observed_market_events"]))
        self.assertTrue(any(x["category"]=="MARKET_FX_ECB_FIXING" for x in data["observed_market_events"]))
    def test_model_prompt_uses_exact_v3_and_enables_web_search(self):
        policy=(ROOT/"validation/home/CHATGPT_ALERT_EDITORIAL_V3_CANONICAL.md").read_text()
        p=mod.request_payload(policy,mod.source_bundle(ROOT,NOW),NOW,"gpt-6.1-terra")
        self.assertTrue(p["instructions"].startswith(policy))
        self.assertEqual(p["tools"],[{"type":"web_search"}])
        self.assertEqual(p["tool_choice"],"required")
        self.assertIn("web_search_call.action.sources",p["include"])
        self.assertFalse(p["store"])
    def test_successful_mocked_ai_output_requires_no_chatgpt_access(self):
        with patch.object(mod,"call_ai",side_effect=AssertionError("must not call external API in a fixture test")):
            r=mod.generate(ROOT,NOW,ai_response=raw())
        self.assertEqual(r["status"],"ACTIVE")
        self.assertEqual(len(r["news"]),3)
        self.assertEqual(r["provenance"]["chatgpt_automation_unchanged"],True)
        self.assertEqual(r["edition_time_rome"],"2026-11-13 13:20")
    def test_reject_output_without_real_web_search(self):
        d=raw()
        d["output"]=d["output"][1:]
        with self.assertRaisesRegex(ValueError,"web search"):
            mod.generate(ROOT,NOW,ai_response=d)
    def test_reject_fabricated_source_url(self):
        d=sample()
        d["news"][0]["sources"]=["https://madeup.example.net/press"]
        with self.assertRaisesRegex(ValueError,"not supported"):
            mod.generate(ROOT,NOW,ai_response=raw(d))
    def test_reject_future_release_as_actual(self):
        d=sample()
        d["news"][0]["event_date"]="2026-11-17"
        with self.assertRaisesRegex(ValueError,"Future event"):
            mod.generate(ROOT,NOW,ai_response=raw(d))
    def test_reject_stale_event_and_defensive_text(self):
        d=sample()
        d["news"][0]["published_date"]="2026-10-01"
        with self.assertRaisesRegex(ValueError,"stale"):
            mod.generate(ROOT,NOW,ai_response=raw(d))
        d=sample();d["lead"]="Non abbiamo dati, quindi non possiamo trarre conclusioni ragionevoli sul dollaro."
        with self.assertRaisesRegex(ValueError,"Defensive"):
            mod.generate(ROOT,NOW,ai_response=raw(d))
    def test_missing_secret_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"not configured"):
            mod.call_ai({"model":"test"},None)
    def test_prior_content_keeps_history_with_sources(self):
        prior=mod.generate(ROOT,NOW,ai_response=raw())
        newer=mod.generate(ROOT,NOW.replace(hour=13),prior=prior,ai_response=raw())
        self.assertEqual(len(newer["history"]),1)
        self.assertEqual(newer["history"][0]["headline"],prior["headline"])
        self.assertEqual(newer["history"][0]["generated_at_utc"],prior["generated_at_utc"])
    def test_source_helper_never_claims_live_reaction(self):
        v=mod.source_bundle(ROOT,NOW)
        self.assertIn("NOT intraday event reactions",v["NOTE"])
        self.assertNotIn("chatgpt",str(v).lower())

if __name__=="__main__":
    unittest.main(verbosity=2)
