#!/usr/bin/env python3
import importlib.util
from pathlib import Path

P = Path(__file__).with_name("build_macro_research_desk_alert.py")
spec = importlib.util.spec_from_file_location("desk", P); desk = importlib.util.module_from_spec(spec); spec.loader.exec_module(desk)

def lane(name, source="Official", as_of="2026-10-17"):
    return {"name":name,"alert_eligible":True,"source":source,"as_of":as_of,"age_days":0}

snapshot = {"generated_at_utc":"2026-10-17T12:00:00Z","lanes":{"macro":lane("MACRO"),"fx":lane("FX","ECB reference rates"),"ois":{"GBP":lane("OIS.GBP")},"g8_bonds":{"GBP":lane("G8_BOND.GBP")}}}
event = {"event_id":"uk-cpi-20261017","headline_it":"Inflazione UK pubblicata.","source":"ONS","observed_at_utc":"2026-10-17T10:00:00Z","macro_assessment_it":"Dato verificato nel registro di rilascio.","ois_currency":"GBP","market_pricing_it":"Il pricing richiede confronto con una curva timestampata.","thesis_strength":"MEDIA","trade_attractiveness":"ATTENDERE","risk_it":"Rischio: conferma FX assente."}

fallback = desk.build(snapshot, None, set())
assert fallback["message"] == desk.FALLBACK and fallback["kind"] == "FALLBACK"
alert = desk.build(snapshot, event, set())
assert alert["kind"] == "SIGNIFICANT" and 250 <= alert["word_count"] <= 350
snapshot["lanes"]["macro"]["event"] = {
    "event_id": "uk-cpi-20261017", "currency": "GBP", "indicator": "CPI YoY", "period": "2026-09",
    "release_timestamp_utc": "2026-10-17T10:00:00Z", "actual": 3.2, "consensus": 3.1, "previous": 3.0,
    "revisions": [], "source": {"authority": "ONS", "release_url": "https://example.invalid/ons"},
}
from_feed = desk.build(snapshot, desk.event_from_macro_snapshot(snapshot), set())
assert from_feed["kind"] == "SIGNIFICANT" and from_feed["delivery"]["mode"] == "CHATGPT_PULL_ONLY"
assert desk.build(snapshot, event, {event["event_id"]})["kind"] == "FALLBACK"
bad = dict(event, ois_currency="USD")
assert desk.build(snapshot, bad, set())["kind"] == "FALLBACK"
print("macro research desk alert tests passed")
