#!/usr/bin/env python3
"""Calendar/News may be verified today even when valid market content is unchanged."""
from __future__ import annotations

import datetime as dt
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import build_calendar_operational_v1 as calendar
import build_news_pulse_operational_v1 as news
import collect_official_news_rss_v1 as officialrss
from refresh_macro_consensus_secondary_v1 import series_compatible

UTC = dt.timezone.utc


def at(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value)


def test_builder(module) -> None:
    # Friday vintage persisted before the Sunday and Monday validation runs.
    old_time = "2026-10-23T06:52:00Z"
    friday_content = {"schema": "TEST_NO_NEW_SIGNAL", "items": [{"as_of": "2026-10-22"}]}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "output.json"
        original = dict(friday_content, generated_at_utc=old_time)
        path.write_text(json.dumps(original), encoding="utf-8")
        with patch.object(module, "OUT", path):
            # Sunday check is not a content update.
            assert module.stable_write(friday_content, at("2026-10-25T08:10:00+01:00")) is False
            sunday = json.loads(path.read_text(encoding="utf-8"))
            assert sunday["generated_at_utc"] == old_time
            assert sunday["last_checked_at_utc"] == "2026-10-25T07:10:00Z"
            assert sunday["items"][0]["as_of"] == "2026-10-22"

            # Monday 05:00 CET: source re-verified, same last meaningful signal.
            assert module.stable_write(friday_content, at("2026-10-26T05:12:00+01:00")) is False
            monday = json.loads(path.read_text(encoding="utf-8"))
            assert monday["generated_at_utc"] == old_time
            assert monday["last_checked_at_utc"] == "2026-10-26T04:12:00Z"
            assert monday["items"][0]["as_of"] == "2026-10-22"

            # Subsequent runs on same Rome date do not churn main with a new
            # timestamp; this avoids repeat publication loops.
            before = path.read_bytes()
            assert module.stable_write(friday_content, at("2026-10-26T07:48:00+01:00")) is False
            assert path.read_bytes() == before

            # A real new signal does advance the content-generated time too.
            changed = {"schema": "TEST_NO_NEW_SIGNAL", "items": [{"as_of": "2026-10-26"}]}
            assert module.stable_write(changed, at("2026-10-26T08:01:00+01:00")) is True
            latest = json.loads(path.read_text(encoding="utf-8"))
            assert latest["generated_at_utc"] == "2026-10-26T07:01:00Z"
            assert latest["last_checked_at_utc"] == "2026-10-26T07:01:00Z"
            assert latest["items"][0]["as_of"] == "2026-10-26"


for builder in (calendar, news):
    test_builder(builder)

print("CALENDAR_NEWS_TRUE_RECHECK_VINTAGE_CET_CEST_PASS")


# The same country and date do not make two macro indicators the same
# economic series. Regressions documented from the 25 October public feed.
bad_pairs = [
    ("AUD", "INFLATION", "Consumer Price Index, Australia", "Import Prices q/q"),
    ("EUR", "GROWTH", "Euro area preliminary flash GDP", "French Flash GDP q/q"),
    ("EUR", "LABOUR", "Euro area unemployment", "German Unemployment Change"),
    ("JPY", "LABOUR", "Labour Force Survey - Basic Tabulation", "Unemployment Rate"),
    ("AUD", "INFLATION", "Consumer Price Index, Australia", "CPI m/m"),
]
for ccy, event_type, official_title, provider_title in bad_pairs:
    assert not series_compatible(
        {"ccy": ccy, "event_type": event_type, "title": official_title},
        {"event": provider_title}
    ), (official_title, provider_title)

good_pairs = [
    ("USD", "LABOUR_COST", "Employment Cost Index", "Employment Cost Index q/q"),
    ("CAD", "GROWTH", "Gross domestic product by industry", "GDP m/m"),
    ("EUR", "GROWTH", "Euro area preliminary flash GDP", "Eurozone Flash GDP q/q"),
    ("EUR", "LABOUR", "Euro area unemployment", "Eurozone Unemployment Rate"),
]
for ccy, event_type, official_title, provider_title in good_pairs:
    assert series_compatible(
        {"ccy": ccy, "event_type": event_type, "title": official_title},
        {"event": provider_title}
    ), (official_title, provider_title)

# Defense in depth: even when the previously persisted secondary JSON still
# carries invalid matches, the independently rebuilt public calendar must
# quarantine their values before they are ever exposed to the user.
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    day = "2099-10-28"
    examples = [
        ("AUD", "INFLATION", "Consumer Price Index, Australia", "Import Prices q/q"),
        ("EUR", "GROWTH", "Euro area preliminary flash GDP", "French Flash GDP q/q"),
        ("EUR", "LABOUR", "Euro area unemployment", "German Unemployment Change"),
        ("USD", "LABOUR_COST", "Employment Cost Index", "Employment Cost Index q/q"),
    ]
    macro_rows = [
        {"ccy": ccy, "date": day, "event_type": kind,
         "title": title, "quality": "OFFICIAL_CALENDAR"}
        for ccy, kind, title, provider in examples
    ]
    consensus_rows = [
        {"event_key": "|".join((ccy, day, kind, title)),
         "status": "AVAILABLE", "consensus": "1.8%", "previous": "5.7%",
         "provider_event": provider, "provider": "TEST"}
        for ccy, kind, title, provider in examples
    ]
    cb_file = root / "cb.json"
    official_file = root / "official.json"
    consensus_file = root / "consensus.json"
    public_file = root / "calendar.json"
    cb_file.write_text(json.dumps({}, indent=2))
    official_file.write_text(json.dumps({"events": macro_rows}, indent=2))
    consensus_file.write_text(json.dumps({"events": consensus_rows}, indent=2))
    with (patch.object(calendar, "ROOT", root),
          patch.object(calendar, "CB", cb_file),
          patch.object(calendar, "MACRO", official_file),
          patch.object(calendar, "CONSENSUS", consensus_file),
          patch.object(calendar, "OUT", public_file)):
        calendar.main()
    result = json.loads(public_file.read_text(encoding="utf-8"))
    assert len(result["events"]) == 4
    assert result["coverage"]["consensus_available_events"] == 1
    for event in result["events"]:
        if event["ccy"] == "USD":
            assert event["consensus_status"] == "AVAILABLE"
            assert event["consensus"] == "1.8%"
        else:
            assert event["consensus_status"] == "NOT_PRESENT"
            assert "consensus" not in event and "previous" not in event

print("MACRO_CONSENSUS_EXACT_SERIES_AND_REGION_GUARDS_PASS")


# News Pulse is a market signal receipt, not a substitute for dated news.
# A WITHHELD source must never be promoted because it contains a numeric
# movement; source, quality and date must all certify the same observation.
ois_base = {
    'currencies': {
        'CAD': {
            'operational_status': 'GREEN_OFFICIAL',
            'quality': 'OFFICIAL_CERTIFIED',
            'confidence': 'A',
            'as_of': '2026-10-23',
            'source': 'Verified test source',
            'horizons': {
                '6m': {'change_1d_bp': -3.0, 'change_1w_bp': 1.0}
            },
        }
    }
}
news_day = dt.date(2026, 10, 25)
assert len(news.ois_items(ois_base, today=news_day)) == 1
for change in (
    {'operational_status': 'WITHHELD'},
    {'operational_status': 'GREEN_ESTIMATED'},
    {'source': ''},
    {'as_of': '2026-10-26'},
    {'as_of': 'invalid'},
    {'horizons': {'6m': {'change_1d_bp': float('nan')}}},
    {'horizons': {'6m': {'change_1d_bp': float('inf')}}},
    {'horizons': {'6m': {'change_1d_bp': '3.0'}}},
):
    x = json.loads(json.dumps(ois_base))
    x['currencies']['CAD'].update(change)
    assert news.ois_items(x, today=news_day) == [], change

proxy = json.loads(json.dumps(ois_base))
proxy['currencies']['CAD'].update(
    operational_status='GREEN_ESTIMATED', quality='ESTIMATED_INFORMATIONAL'
)
proxy_item = news.ois_items(proxy, today=news_day)[0]
assert proxy_item['category'] == 'OIS_PROXY_REPRICING'
assert 'non è una curva OIS ufficiale' in proxy_item['detail']
assert proxy_item['source'] == 'Verified test source'

# An exchange futures contract is an official underlying source, but not an
# observed OIS curve. Never use the same label for the two instruments.
futures = json.loads(json.dumps(ois_base))
futures['currencies']['CAD']['source'] = 'Montréal Exchange · CORRA futures'
futures_item = news.ois_items(futures, today=news_day)[0]
assert futures_item['category'] == 'FUTURES_IMPLIED_REPRICING'
assert 'repricing implicito da futures' in futures_item['title']
assert 'non equivale a una curva OIS osservata' in futures_item['detail']
futures['currencies']['CAD'].update(
    operational_status='GREEN_ESTIMATED',
    quality='ESTIMATED_INFORMATIONAL'
)
estimated_futures_item = news.ois_items(futures, today=news_day)[0]
assert estimated_futures_item['category'] == 'FUTURES_IMPLIED_REPRICING'
assert 'indicativo da futures' in estimated_futures_item['title']

# A monthly observation period can never be mistaken for its release date.
macro_base = {'currencies': {'USD': {'inflation': {
    'as_of': '2026-10', 'label': 'Inflazione',
    'source': 'BLS', 'latest_value': 3.2, 'direction': 'SALE',
    'acceleration': 'ACCELERA', 'temperature_label': 'CALDO',
    'percentile': 70.0,
}}}}
assert news.macro_items(macro_base, today=news_day) == []
macro = json.loads(json.dumps(macro_base))
macro['currencies']['USD']['inflation'].update(
    release_date='2026-10-23', release_date_verified=False
)
assert news.macro_items(macro, today=news_day) == []
macro['currencies']['USD']['inflation']['release_date_verified'] = True
verified_item = news.macro_items(macro, today=news_day)[0]
assert verified_item['as_of'] == '2026-10-23'
assert verified_item['reference_period'] == '2026-10'
assert verified_item['quality'] == 'VERIFIED_RELEASE_DATE_MACRO_OBSERVATION'
print('NEWS_PULSE_SOURCE_VINTAGE_AND_QUALITY_FAIL_CLOSED_PASS')


# Official headlines: strictly sourced Fed/ECB RSS, dated article URL, no
# cross-host injection, false publication date, cached old story or fake impact.
rss_now = at("2026-10-25T15:00:00+00:00")
fed_rss = b"""<?xml version="1.0" encoding="utf-8"?>
<rss><channel>
<item><title>Federal Reserve Board publishes an announcement</title>
<link>https://www.federalreserve.gov/newsevents/pressreleases/monetary20261023a.htm</link>
<pubDate>Fri, 23 Oct 2026 14:00:00 GMT</pubDate></item>
<item><title>Untrusted market commentary injected into feed</title>
<link>https://example.com/market-news</link>
<pubDate>Fri, 23 Oct 2026 14:00:00 GMT</pubDate></item>
<item><title>Federal Reserve future dated item</title>
<link>https://www.federalreserve.gov/newsevents/pressreleases/future.htm</link>
<pubDate>Mon, 26 Oct 2026 14:00:00 GMT</pubDate></item>
<item><title>Federal Reserve item without a date</title>
<link>https://www.federalreserve.gov/newsevents/pressreleases/undated.htm</link></item>
</channel></rss>"""
ecb_rss = b"""<?xml version="1.0" encoding="utf-8"?>
<rss><channel><item><title>European Central Bank publishes a policy speech</title>
<link>https://www.ecb.europa.eu/press/key/date/2026/html/example.en.html</link>
<pubDate>Sat, 24 Oct 2026 12:00:00 GMT</pubDate></item>
</channel></rss>"""
# One publisher-controlled item per approved source is accepted; no
# cross-host links are admitted. An EIA entry is an energy publication,
# never presented as currency-specific macro news or WTI-price movement.
def rss_item_for_source(source):
    if source["id"] == "FED_PRESS":
        return fed_rss
    if source["id"] == "ECB_PRESS":
        return ecb_rss
    host = source["hosts"][0]
    return (
        '<rss><channel><item><title>Official research and policy update ' +
        source["id"] + '</title><link>https://' + host +
        '/news/test-' + source["id"].lower() + '.html</link>' +
        '<pubDate>Fri, 23 Oct 2026 14:00:00 GMT</pubDate></item></channel></rss>'
    ).encode("utf-8")

stories = officialrss.collect(rss_now, rss_item_for_source)
assert stories["status"] == "VERIFIED_OFFICIAL_RELEASES"
assert stories["source_count"] == 9
assert stories["source_failures"] == 0
assert len(stories["headlines"]) == 9
assert {x["source_id"] for x in stories["headlines"]} == {
    source["id"] for source in officialrss.RSS_SOURCES
}
assert sum(x["ccy"] == "ENERGY" for x in stories["headlines"]) == 1
assert stories["headlines"][0]["source_id"] == "ECB_PRESS"
assert all(x["quality"] == "OFFICIAL_RSS_DATED_LINK" for x in stories["headlines"])
assert all(x["interpretation"] == "NON_VERIFIED_NO_MARKET_IMPACT_CLAIM"
           for x in stories["headlines"])
assert stories["latest_published_at_utc"] == "2026-10-24T12:00:00Z"
assert stories["last_attempt_day_rome"] == "2026-10-25"

def partial_transport(source):
    if source["id"] == "FED_PRESS":
        raise TimeoutError("test network outage")
    return rss_item_for_source(source)

partial_headlines = officialrss.collect(rss_now, partial_transport)
assert partial_headlines["status"] == "PARTIAL_SOURCES"
assert partial_headlines["source_failures"] == 1
assert len(partial_headlines["headlines"]) == 8
assert any(x["status"] == "FETCH_OR_PARSE_FAILED"
           for x in partial_headlines["sources"])

failed = officialrss.collect(rss_now,
    lambda source: (_ for _ in ()).throw(TimeoutError("offline")))
assert failed["status"] == "SOURCES_UNAVAILABLE"
assert failed["headlines"] == []
assert failed["latest_published_at_utc"] is None
assert failed["source_failures"] == 9

old_rss = fed_rss.replace(b"23 Oct 2026", b"01 Oct 2026")
old = officialrss.collect(rss_now,
    lambda source: old_rss if source["id"] == "FED_PRESS"
    else b"<rss><channel /></rss>")
assert old["status"] == "VERIFIED_NO_RECENT_RELEASES"
assert old["headlines"] == []

# A single active publisher with 10 valid articles cannot monopolise the
# cross-country headline page. Keep newest two per source, at most 18 total.
spam = b"<rss><channel>" + b"".join(
    (b"<item><title>Federal Reserve long-form policy update %d</title>"
     b"<link>https://www.federalreserve.gov/news/policy%d.html</link>"
     b"<pubDate>Fri, 23 Oct 2026 14:00:00 GMT</pubDate></item>") % (i, i)
    for i in range(10)
) + b"</channel></rss>"
many = officialrss.collect(rss_now,
    lambda source: spam if source["id"] == "FED_PRESS"
    else rss_item_for_source(source))
assert len([x for x in many["headlines"] if x["source_id"] == "FED_PRESS"]) == 2
assert len(many["headlines"]) <= officialrss.MAX_ITEMS

# Verify strict host/scheme matching; a name in a path or subdomain is
# insufficient to establish original-publisher provenance.
source = officialrss.RSS_SOURCES[0]
assert officialrss.trustworthy_url("https://www.federalreserve.gov.evil.example/x",source) is None
assert officialrss.trustworthy_url("http://www.federalreserve.gov/x",source) is None
assert officialrss.trustworthy_url("https://fake.invalid/www.federalreserve.gov/x",source) is None
print("OFFICIAL_NEWS_RSS_SOURCE_DATE_AND_OUTAGE_FAIL_CLOSED_PASS")
