#!/usr/bin/env python3
"""Source Watch publisher regression tests; no network dependencies."""
import json
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from build_desk_source_alerts import SCHEMA, build, make_item, parse_rss, parse_bbc_rss, run

NOW = datetime(2026, 10, 18, 8, 0, tzinfo=timezone.utc)
BASE = {"schema": SCHEMA, "generated_at_utc": None, "state": "EMPTY", "history": [],
        "policy": {"source": "CHATGPT_SCHEDULED_DESK_ALERT", "max_history": 100, "deduplicate_by": "event_id"}}


def record(title="Iran Guards say tankers hit mines in Hormuz", when=None):
    return {"title": title, "source": "Reuters",
            "url": "https://news.google.com/rss/articles/fixture",
            "observed": when or NOW - timedelta(hours=1)}


class SourceWatchTests(unittest.TestCase):
    def test_reported_claim_is_not_marked_independently_confirmed(self):
        item = make_item(record(), NOW)
        self.assertEqual(item["category"], "GEOPOLITICS")
        self.assertFalse(item["independently_confirmed"])
        self.assertIn("non è confermato indipendentemente", item["summary"])
        self.assertEqual(item["related_pairs"], [])

    def test_stale_and_unrelated_are_withheld(self):
        self.assertIsNone(make_item(record(when=NOW - timedelta(hours=31)), NOW))
        self.assertIsNone(make_item(record(title="Cultural exhibition opens in Rome"), NOW))

    def test_deduplication_preserves_history_and_policy(self):
        first, count = build(BASE, [record()], NOW)
        self.assertEqual(count, 1)
        second, count_again = build(first, [record()], NOW + timedelta(minutes=10))
        self.assertEqual(count_again, 0)
        self.assertEqual(second, first)
        self.assertEqual(first["policy"]["max_history"], 100)
        self.assertEqual(first["policy"]["deduplicate_by"], "event_id")
        self.assertEqual(first["policy"]["source"], "INDEPENDENT_REUTERS_AP_NEWS_RSS")

    def test_unrelated_geopolitics_and_generic_sanctions_are_withheld(self):
        self.assertIsNone(make_item(record(title="Sanctions and embargoes"), NOW))
        self.assertIsNone(make_item(record(title="Diplomats attacked in the occupied West Bank, and other developments"), NOW))
        self.assertIsNotNone(make_item(record(title="Iran's Guards say two tankers hit mines in Strait of Hormuz"), NOW))

    def test_removes_only_previous_generated_false_positives(self):
        valid = make_item(record(), NOW)
        spurious = {"event_id": "SRC-old", "headline": "Sanctions and embargoes",
                    "verification_level": "PUBLISHER_ATTRIBUTED_ONLY"}
        external = {"event_id": "EXTERNAL-1", "headline": "Una notizia verificata da un altro processo"}
        data = {**BASE, "history": [spurious, external, valid]}
        updated, count = build(data, [record()], NOW)
        self.assertEqual(count, 0)
        self.assertEqual(len(updated["history"]), 2)
        self.assertIn(external, updated["history"])
        self.assertIn(valid, updated["history"])

    def test_invalid_existing_contract_fails_closed(self):
        with self.assertRaises(ValueError):
            build({"history": []}, [record()], NOW)

    def test_reuters_rss_parsed_unknown_source_rejected(self):
        xml = b'''<rss><channel>
        <item><title>Bank of Canada raises interest rates - Reuters</title>
        <link>https://news.google.com/rss/articles/test</link>
        <pubDate>Sat, 17 Oct 2026 21:00:00 GMT</pubDate>
        <source url="https://www.reuters.com">Reuters</source></item>
        <item><title>Fed says inflation - Unknown Publisher</title>
        <link>https://news.google.com/rss/articles/test2</link>
        <pubDate>Sat, 17 Oct 2026 21:00:00 GMT</pubDate>
        <source>Unknown Publisher</source></item>
        </channel></rss>'''
        rows = parse_rss(xml)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Bank of Canada raises interest rates")
        self.assertEqual(make_item(rows[0], NOW)["currencies"], ["CAD"])

    def test_bbc_direct_rss_preserves_attribution_and_rejects_offsite_links(self):
        xml = b'''<rss><channel>
          <item><title>Bank of England holds interest rates</title>
            <link>https://www.bbc.com/news/articles/c123</link>
            <pubDate>Sun, 18 Oct 2026 07:00:00 GMT</pubDate></item>
          <item><title>Fed announces rate cut</title>
            <link>https://www.bbc.com.evil.example/news/abcd</link>
            <pubDate>Sun, 18 Oct 2026 07:00:00 GMT</pubDate></item>
          <item><title>ECB inflation outlook</title>
            <link>http://www.bbc.co.uk/news/articles/c99</link>
            <pubDate>Sun, 18 Oct 2026 07:00:00 GMT</pubDate></item>
        </channel></rss>'''
        items = parse_bbc_rss(xml)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source"], "BBC News")
        attributed = make_item(items[0], NOW)
        self.assertEqual(attributed["verification_level"], "PUBLISHER_ATTRIBUTED_ONLY")
        self.assertEqual(attributed["source_label"], "BBC News · notizia attribuita")
        self.assertFalse(attributed["independently_confirmed"])

    def test_bbc_backup_used_only_when_all_google_searches_fail(self):
        bbc_xml = b'''<rss><channel><item><title>Bank of England holds interest rates</title>
            <link>https://www.bbc.co.uk/news/articles/c123</link>
            <pubDate>Sun, 18 Oct 2026 07:00:00 GMT</pubDate></item></channel></rss>'''
        with tempfile.TemporaryDirectory() as directory:
            previous = Path(directory) / "previous.json"
            output = Path(directory) / "output.json"
            previous.write_text(json.dumps(BASE), encoding="utf-8")
            with patch("build_desk_source_alerts.get_xml") as fetch, patch(
                "build_desk_source_alerts.datetime"
            ) as clock:
                clock.now.return_value = NOW
                fetch.side_effect = lambda url: (
                    bbc_xml if url.startswith("https://feeds.bbci.co.uk/")
                    else (_ for _ in ()).throw(urllib.error.URLError("Google RSS 503"))
                )
                run(output, previous)
                updated = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(updated["history"][0]["source_label"], "BBC News · notizia attribuita")
                self.assertEqual(updated["policy"]["source"], "REUTERS_AP_NEWS_WITH_BBC_OFFICIAL_RSS_FALLBACK")
                self.assertEqual(fetch.call_count, 5)

    def test_total_outage_keeps_previous_file_and_does_not_write_output(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = Path(directory) / "previous.json"
            output = Path(directory) / "output.json"
            original = json.dumps(BASE, sort_keys=True)
            previous.write_text(original, encoding="utf-8")
            with patch("build_desk_source_alerts.get_xml", side_effect=urllib.error.URLError("503")):
                with self.assertRaisesRegex(RuntimeError, "do not replace Desk feed"):
                    run(output, previous)
            self.assertFalse(output.exists())
            self.assertEqual(previous.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
