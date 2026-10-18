#!/usr/bin/env python3
"""Source Watch publisher regression tests; no network dependencies."""
import unittest
from datetime import datetime, timedelta, timezone
from build_desk_source_alerts import SCHEMA, build, make_item, parse_rss

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
        self.assertEqual(first["policy"], BASE["policy"])

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


if __name__ == "__main__":
    unittest.main()
