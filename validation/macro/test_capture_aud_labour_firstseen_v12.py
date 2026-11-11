"""Offline ABS October 2026 issuer-gated first observation regression."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from validation.macro import capture_aud_labour_official_firstseen_v12 as aud

UTC=timezone.utc
BEFORE=datetime(2026,11,18,18,tzinfo=UTC)
AFTER=aud.RELEASE + timedelta(minutes=10)
SEEN=AFTER + timedelta(seconds=15)
HTML=b"""<html><head><title>Labour Force, Australia, October 2026</title></head>
<body><h1>Labour Force, Australia</h1>
<p>Reference period</p><p>October 2026</p><p>Released</p><p>19/11/2026</p>
<h2>Key statistics</h2><p>In seasonally adjusted terms, in October 2026:</p>
<ul><li>the employment-to-population ratio increased 0.1ppt to 63.5%.</li>
<li>the unemployment rate increased 0.2ppt to 4.9%.</li></ul>
<h2>In trend terms</h2><p>the unemployment rate remained at 4.4%.</p>
<p>September 2026 previous figure was 4.7%.</p>
</body></html>"""


def fetch(url, host):
    assert url==aud.URL and host==aud.HOST
    return HTML,url


class AudIssuerFirstSeenTests(unittest.TestCase):
    def test_exact_source_metadata_and_utc_release_clock(self):
        self.assertEqual(aud.RELEASE,datetime(2026,11,19,0,30,tzinfo=UTC))
        self.assertEqual(aud.parse_abs(HTML),4.9)

    def test_pre_release_cannot_fetch_even_if_url_is_available(self):
        calls=[]
        def forbidden(*args):
            calls.append(args)
            raise AssertionError("no official HTTP before scheduled release")
        rows,r=aud.capture([],BEFORE,forbidden)
        self.assertEqual(rows,[])
        self.assertEqual(calls,[])
        self.assertEqual(r["state"],"BEFORE_RELEASE_NO_HTTP")

    def test_exact_october_sa_not_september_nor_trend_nor_release_stub(self):
        variants=(
            HTML.replace(b"October 2026",b"September 2026"),
            HTML.replace(b"19/11/2026",b"15/10/2026"),
            HTML.replace(b"In seasonally adjusted terms",b"In trend terms"),
            HTML.replace(b"unemployment rate increased 0.2ppt to 4.9%",
                         b"underemployment rate increased 0.2ppt to 4.9%"),
            HTML.replace(b"the unemployment rate increased 0.2ppt to 4.9%",
                         b"the unemployment rate not yet published"),
        )
        for variant in variants:
            with self.subTest(variant=variant[:120]),self.assertRaises(aud.Pending):
                aud.parse_abs(variant)
        self.assertEqual(
            aud.parse_abs(HTML.replace(b"increased 0.2ppt to",b"decreased 0.1ppt to")),
            4.9)
        self.assertEqual(
            aud.parse_abs(HTML.replace(b"increased 0.2ppt to",b"remained at")),
            4.9)

    def test_post_release_success_sha_archive_and_duplicate_no_network(self):
        rows,r=aud.capture([],AFTER,fetch,observed_clock=lambda:SEEN)
        self.assertEqual(r["new_actuals"],1)
        self.assertEqual(rows[0]["actual_percent"],4.9)
        self.assertEqual(rows[0]["observed_at_utc"],"2026-11-19T00:40:15Z")
        self.assertEqual(rows[0]["official_scheduled_release_utc"],"2026-11-19T00:30:00Z")
        self.assertEqual(rows[0]["metric_unit"],"PCT_LEVEL_SA")
        self.assertIsNone(rows[0]["survey_consensus_percent"])
        self.assertFalse(rows[0]["first_publisher_delivery_PIT_verified"])
        self.assertFalse(rows[0]["eligible_for_Core_Beta_Forward"])
        self.assertTrue(aud.validate(rows))
        def no_fetch(*args):raise AssertionError("archived release never repolled")
        again,receipt=aud.capture(rows,AFTER+timedelta(minutes=20),no_fetch)
        self.assertEqual(rows,again)
        self.assertEqual(receipt["state"],"ALREADY_ARCHIVED_NO_HTTP")

    def test_invalid_archive_or_source_cannot_be_published(self):
        rows,_=aud.capture([],AFTER,fetch,observed_clock=lambda:SEEN)
        for edit in (
            lambda r:r[0].update(actual_percent=8.1),
            lambda r:r[0].update(FX_signal="AUDUSD_LONG"),
            lambda r:r[0].update(first_publisher_delivery_PIT_verified=True),
            lambda r:r[0].update(metric_unit="PCT_MOM"),
        ):
            bad=copy.deepcopy(rows)
            edit(bad)
            with self.subTest(edit=str(edit)),self.assertRaises(ValueError):
                aud.validate(bad)
        with self.assertRaises(ValueError):
            aud.validate(rows+rows)
        with self.assertRaisesRegex(ValueError,"source"):
            aud.capture([],AFTER,lambda url,host:(HTML,"https://example.com/foo"),
                        observed_clock=lambda:SEEN)

    def test_missing_publisher_actual_never_becomes_zero(self):
        rows,r=aud.capture([],AFTER,
            lambda url,host:(HTML.replace(b"4.9%",b"not released"),url))
        self.assertEqual(rows,[])
        self.assertEqual(r["state"],"TARGET_ISSUER_RELEASE_NOT_YET_OBSERVED")
        late,c=aud.capture([],aud.RELEASE+timedelta(days=8),
                           lambda *args:(_ for _ in ()).throw(AssertionError("late")))
        self.assertEqual(late,[])
        self.assertEqual(c["state"],"OUTSIDE_FIRST_OBSERVATION_WINDOW_NO_HTTP")

    def test_run_writes_only_event_ledger_not_live_or_fx(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"actuals.jsonl"
            r=aud.run(path,AFTER,fetch,lambda:SEEN)
            self.assertEqual(r["new_actuals"],1)
            rows=[__import__("json").loads(x) for x in path.read_text().splitlines()]
            self.assertEqual(len(rows),1)
            self.assertTrue(aud.validate(rows))
            self.assertEqual(aud.run(path,AFTER+timedelta(minutes=30),
                                    lambda *args:(_ for _ in ()).throw(AssertionError("duplicate"))
                                    )["new_actuals"],0)


if __name__=="__main__":
    unittest.main()
