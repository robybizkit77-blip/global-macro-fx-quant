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
import news_reaction_evidence_v1 as proof
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
# Regression: BoJ uses issuer-specific policy release titles. The official
# headline must be watched as a CB event, without inferring a decision or bias.
boj_source = next(x for x in officialrss.RSS_SOURCES if x["id"] == "BOJ_NEWS")
for title, expected_topic in (
    ("Statement on Monetary Policy", "CB_POLICY"),
    ("Change in the Guideline for Money Market Operations", "CB_POLICY"),
    ("(Reference) Change in the Guideline for Money Market Operations (September 2026 MPM)", "CB_POLICY"),
    ("Outlook for Economic Activity and Prices (October 2026, The Bank's View)", "MACRO_EXPECTATIONS"),
):
    ctx = officialrss.desk_context(title, boj_source)
    assert ctx["operational_relevance"] == "MONITOR", (title, ctx)
    assert ctx["topic"] == expected_topic, (title, ctx)
    assert ctx["analysis_basis"] == "SOURCE_HEADLINE_ONLY", ctx
    assert ctx["market_direction"] == "NOT_DETERMINED", ctx
    assert ctx["market_reaction"] == "NOT_MEASURED", ctx

# The same words on another publisher's feed are not silently designated BoJ.
assert officialrss.desk_context(
    "Change in the Guideline for Money Market Operations",
    next(x for x in officialrss.RSS_SOURCES if x["id"] == "FED_PRESS"),
)["topic"] == "INSTITUTIONAL"

boj_future_fixture = b"""<?xml version="1.0" encoding="utf-8"?>
<rss><channel><item><title>Statement on Monetary Policy</title>
<link>https://www.boj.or.jp/en/mopo/mpmdeci/state_2026/test-fixture.pdf</link>
<pubDate>Fri, 30 Oct 2026 03:30:00 GMT</pubDate></item></channel></rss>"""
future_items = officialrss.extract_items(
    boj_future_fixture, boj_source, at("2026-10-30T04:00:00+00:00"))
assert len(future_items) == 1, future_items
assert future_items[0]["desk_context"]["topic"] == "CB_POLICY"
assert future_items[0]["desk_context"]["market_direction"] == "NOT_DETERMINED"
assert future_items[0]["quality"] == "OFFICIAL_RSS_DATED_LINK"
assert officialrss.extract_items(
    boj_future_fixture.replace(b"www.boj.or.jp", b"example.com"),
    boj_source, at("2026-10-30T04:00:00+00:00")) == []
print("BOJ_OFFICIAL_RSS_POLICY_TITLE_CLASSIFICATION_PASS")

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


# Headline-only desk interpretation: useful questions, never an inferred
# monetary stance, actual/consensus surprise, observed WTI or FX reaction.
cases = [
    ("ECB_PRESS", "ECB Consumer Expectations Survey results - September 2026",
     "MONITOR", "MACRO_EXPECTATIONS"),
    ("BOC_PRESS", "Bank of Canada releases the Business Outlook Survey",
     "MONITOR", "MACRO_EXPECTATIONS"),
    ("EIA_ENERGY", "U.S. refineries have been running at high rates",
     "MONITOR", "ENERGY_FUNDAMENTALS"),
    ("EIA_ENERGY", "Hybrid sales rise after tax credit expiration",
     "CONTEXT", "ENERGY_STRUCTURE"),
    ("FED_PRESS", "Federal Reserve Board terminates an enforcement action",
     "CONTEXT", "INSTITUTIONAL"),
    ("ECB_PRESS", "Interview with a member of the Executive Board",
     "REVIEW", "CB_COMMUNICATION"),
    ("BOE_NEWS", "Regulators simplify Senior Managers regime",
     "CONTEXT", "INSTITUTIONAL"),
    ("RBA_PRESS", "Monetary Policy Decision - October 2026",
     "MONITOR", "CB_POLICY"),
    ("BOC_PRESS", "Interest rate decision",
     "MONITOR", "CB_POLICY"),
]
source_lookup = {x["id"]: x for x in officialrss.RSS_SOURCES}
for source_id, title, expected_tier, expected_topic in cases:
    context = officialrss.desk_context(title, source_lookup[source_id])
    assert (context["operational_relevance"], context["topic"]) == (
        expected_tier, expected_topic), (source_id, title, context)
    assert context["analysis_basis"] == "SOURCE_HEADLINE_ONLY"
    assert context["market_direction"] == "NOT_DETERMINED"
    assert context["market_reaction"] == "NOT_MEASURED"
    assert context["why_watch"] and context["verify_next"]
# In particular, EIA's 'high rates' is refinery utilisation, not a policy hike.
assert officialrss.desk_context(
    "Refineries operating at very high rates", source_lookup["EIA_ENERGY"]
)["topic"] == "ENERGY_FUNDAMENTALS"

assert all("desk_context" in x and x["desk_context"]["analysis_basis"] ==
           "SOURCE_HEADLINE_ONLY" for x in stories["headlines"])
print("NEWS_HEADLINE_RELEVANCE_CONTEXT_NO_UNVERIFIED_DIRECTION_PASS")


# News Pulse must not claim a release caused a daily OIS, yield or FX move.
published_at = "2026-10-23T10:00:00Z"
headline = {"ccy": "GBP", "published_at_utc": published_at}
ois_sample = {"currencies": {"GBP": {
    "as_of": "2026-10-23",
    "source": "Bank of England · estimated sterling OIS yield curves",
    "operational_status": "GREEN_OFFICIAL", "quality": "OFFICIAL_CERTIFIED",
    "horizons": {"6m": {"rate": 4.5, "change_1d_bp": -12}},
}}}
rates_sample = {"GBP": {
    "date": "2026-10-23", "2Y": 4.75,
    "quality": "FULL_CURRENT_OFFICIAL",
    "source": "Bank of England 2Y official daily curve", "chg2_bp": -15,
}}
audit = proof.assess(headline, ois_sample, rates_sample,
                     now=at("2026-10-25T17:00:00+00:00"))
assert audit["status"] == "NOT_VERIFIABLE_INTRADAY"
assert audit["ois_or_futures"]["status"] == "DAILY_CONTEXT_ONLY"
assert audit["ois_or_futures"]["relative_to_release_day"] == "SAME_CALENDAR_DATE_DAILY_ONLY"
assert audit["ois_or_futures"]["event_window_proof"] is False
assert audit["yield_2y"]["yield_2y_pct"] == 4.75
assert audit["yield_2y"]["event_window_proof"] is False
assert audit["fx"]["status"] == "NO_CERTIFIED_EVENT_WINDOW"
assert audit["market_reaction"] == "NOT_MEASURED"
assert audit["direction"] == "NOT_DETERMINED"
assert audit["causal_attribution"] == "NOT_ESTABLISHED"
# An unexpected future-dated market snapshot cannot be accepted as context.
future_ois = json.loads(json.dumps(ois_sample))
future_ois["currencies"]["GBP"]["as_of"] = "2026-10-27"
assert proof.assess(headline, future_ois, rates_sample,
                    now=at("2026-10-25T17:00:00Z"))["ois_or_futures"]["status"] == "NOT_VALIDATED_DAILY_CONTEXT"
future_rates = json.loads(json.dumps(rates_sample))
future_rates["GBP"]["date"] = "2026-10-27"
assert proof.assess(headline, ois_sample, future_rates,
                    now=at("2026-10-25T17:00:00Z"))["yield_2y"]["status"] == "NOT_VALIDATED_DAILY_CONTEXT"

# Existing daily numbers can be *before* or *after* a release date but do
# not prove the event reaction even when their calendar date is later.
for released, expected in [
    ("2026-10-24T12:00:00Z", "PRIOR_CALENDAR_DATE"),
    ("2026-10-20T12:00:00Z", "LATER_CALENDAR_DATE"),
]:
    a = proof.assess({"ccy": "GBP", "published_at_utc": released},
                     ois_sample, rates_sample,
                     now=at("2026-10-25T17:00:00Z"))
    assert a["status"] == "NOT_VERIFIABLE_INTRADAY"
    assert a["ois_or_futures"]["relative_to_release_day"] == expected
    assert a["yield_2y"]["relative_to_release_day"] == expected

# Withheld OIS, malformed/estimated daily rates or non-finite values must
# not appear as certified daily context or as news-reaction evidence.
bad_ois = json.loads(json.dumps(ois_sample))
bad_ois["currencies"]["GBP"]["operational_status"] = "WITHHELD"
assert proof.assess(headline, bad_ois, rates_sample)["ois_or_futures"]["status"] == "NOT_VALIDATED_DAILY_CONTEXT"
bad_rates = json.loads(json.dumps(rates_sample))
bad_rates["GBP"]["quality"] = "MANUAL_UNVERIFIED"
assert proof.assess(headline, ois_sample, bad_rates)["yield_2y"]["status"] == "NOT_VALIDATED_DAILY_CONTEXT"
bad_rates = json.loads(json.dumps(rates_sample))
bad_rates["GBP"]["2Y"] = float("inf")
assert proof.assess(headline, ois_sample, bad_rates)["yield_2y"]["status"] == "NOT_VALIDATED_DAILY_CONTEXT"
for bad_timestamp in ["invalid", "2026-10-26T12:00:00Z", "2026-10-23T12:00:00"]:
    failed = proof.assess({"ccy": "GBP", "published_at_utc": bad_timestamp},
                          ois_sample, rates_sample,
                          now=at("2026-10-25T17:00:00Z"))
    assert failed["status"] == "INVALID_EVENT_TIMESTAMP"

energy = proof.assess({"ccy": "ENERGY", "published_at_utc": published_at},
                      ois_sample, rates_sample)
assert energy["status"] == "NOT_VERIFIABLE_INTRADAY"
assert energy["wti"]["status"] == "NO_CERTIFIED_EVENT_WINDOW"
assert "ois_or_futures" not in energy and "yield_2y" not in energy
assert "energy_supply_context" in energy

all_proof = proof.annotate({"headlines": [
    headline, {"ccy": "ENERGY", "published_at_utc": published_at}
]}, ois_sample, rates_sample, now=at("2026-10-25T17:00:00Z"))
assert all_proof["reaction_proof_contract"]["verified_event_reactions"] == 0
assert len(all_proof["headlines"]) == 2
assert all(x["reaction_evidence"]["market_reaction"] == "NOT_MEASURED"
           for x in all_proof["headlines"])
print("NEWS_REACTION_EVENT_WINDOW_FAIL_CLOSED_PASS")


# A GitHub 'success' with a dropped pending 07:17 Calendar schedule cannot
# trigger its linked early VIX recovery; keep every pending source check.
# This is a workflow-contract test, not a mock claim of actual scheduling.
calendar_workflow = (Path(__file__).resolve().parents[1] /
    ".github/workflows/calendar-news-operational-refresh-v1.yml").read_text(encoding="utf-8")
vix_workflow = (Path(__file__).resolve().parents[1] /
    ".github/workflows/vix-persistent-apply-v1.yml").read_text(encoding="utf-8")
assert "queue: max" in calendar_workflow
assert "cancel-in-progress: false" in calendar_workflow
assert "calendar-news-validation-pr-{0}" in calendar_workflow
assert calendar_workflow.count("    - cron:") == 2
assert "    - cron: '17 4 * * 1-5'" in calendar_workflow
assert "    - cron: '17 6 * * *'" in calendar_workflow
assert "workflows: ['Calendar News Operational Refresh V1']" in vix_workflow
assert "github.event.workflow_run.event == 'schedule'" in vix_workflow
assert "github.event.workflow_run.conclusion == 'success'" in vix_workflow
print("CALENDAR_EARLY_VIX_BACKUP_NO_DROPPED_PENDING_RUNS_PASS")
