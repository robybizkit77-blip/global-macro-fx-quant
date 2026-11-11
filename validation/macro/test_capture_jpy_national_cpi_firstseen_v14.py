"""Offline Japan CPI October 2026 source/clock/semantic safety tests."""
from __future__ import annotations

import copy
from datetime import datetime,timedelta,timezone
import tempfile
from pathlib import Path
import unittest

from validation.macro import capture_jpy_national_cpi_firstseen_v14 as jp

UTC=timezone.utc
BEFORE=jp.RELEASE-timedelta(minutes=5)
AFTER=jp.RELEASE+timedelta(minutes=3)
SEEN=AFTER+timedelta(seconds=19)
HTML="""<html><head><title>全国 消費者物価指数</title></head><body>
<h1>2025年基準 消費者物価指数 全国 2026年（令和8年）10月分（2026年11月20日公表）</h1>
<h2>≪ポイント≫</h2>
<p>（1） 総合指数は2025年を100として102.2 前年同月比は2.1%の上昇</p>
<p>（2） 生鮮食品を除く総合指数は102.3 前年同月比は2.3％の上昇</p>
<p>（3） 生鮮食品及びエネルギーを除く総合指数は102.8 前年同月比は2.6%の上昇</p>
<p>東京都区部 2026年10月速報 前年同月比は9.9％の上昇</p>
<p>2026年9月 前年同月比1.7%の上昇</p>
</body></html>""".encode("utf-8")

def fetch(url,host):
    assert (url,host)==(jp.URL,jp.HOST)
    return HTML,url

class JapanNationalCpiTests(unittest.TestCase):
    def test_verified_date_and_three_components(self):
        self.assertEqual(jp.RELEASE,datetime(2026,11,19,23,30,tzinfo=UTC))
        got=jp.parse_japan(HTML)
        self.assertEqual(got,{
            "JP_CPI_OCT26_HEADLINE_YOY_NSA":2.1,
            "JP_CPI_OCT26_CORE_EX_FRESH_FOOD_YOY_NSA":2.3,
            "JP_CPI_OCT26_EX_FRESH_ENERGY_YOY_NSA":2.6})
        self.assertNotIn(9.9,got.values())

    def test_not_before_release(self):
        calls=[]
        def never(*args):
            calls.append(args)
            raise AssertionError("no fetch before official 20 November Japan time")
        rows,r=jp.capture([],BEFORE,never)
        self.assertEqual((rows,calls),([],[]))
        self.assertEqual(r["state"],"BEFORE_RELEASE_NO_HTTP")

    def test_rolling_page_prior_month_and_tokyo_fail_closed(self):
        variants=[
            HTML.replace("10月分".encode(), "9月分".encode()),
            HTML.replace("11月20日公表".encode(), "10月23日公表".encode()),
            HTML.replace("全国".encode(),"東京都区部".encode()),
            HTML.replace("生鮮食品を除く総合指数".encode(),"エネルギーを除く総合指数".encode()),
            HTML.replace("2025年基準".encode(),"2020年基準".encode()),
            HTML.replace("前年同月比は2.3％の上昇".encode(),"前年比は未公表".encode()),
        ]
        for sample in variants:
            with self.subTest(sample=sample[:120]),self.assertRaises(jp.Pending):
                jp.parse_japan(sample)

    def test_negative_values_not_conflated_with_index_levels(self):
        sample=HTML.replace("前年同月比は2.3％の上昇".encode(),
                            "前年同月比は0.4％の下落".encode())
        got=jp.parse_japan(sample)
        self.assertEqual(got["JP_CPI_OCT26_CORE_EX_FRESH_FOOD_YOY_NSA"],-0.4)

    def test_hash_archive_clock_and_no_fx_claim(self):
        rows,r=jp.capture([],AFTER,fetch,observed_clock=lambda:SEEN)
        self.assertEqual(r["new_actuals"],1)
        self.assertEqual(rows[0]["observed_at_utc"],"2026-11-19T23:33:19Z")
        self.assertTrue(jp.validate(rows))
        self.assertFalse(rows[0]["eligible_for_Core_Beta_Forward"])
        self.assertIsNone(rows[0]["survey_consensus_percent"])
        more,r2=jp.capture(rows,AFTER+timedelta(hours=2),
                           lambda *_:(_ for _ in ()).throw(AssertionError("duplicate")))
        self.assertEqual(more,rows)
        self.assertEqual(r2["state"],"ALREADY_ARCHIVED_NO_HTTP")

    def test_archive_tampering_or_changed_host_rejected(self):
        rows,_=jp.capture([],AFTER,fetch,observed_clock=lambda:SEEN)
        for mutate in (
            lambda r:r[0]["metrics_percent"].update(JP_CPI_OCT26_HEADLINE_YOY_NSA=9.9),
            lambda r:r[0].update(first_publisher_delivery_PIT_verified=True),
            lambda r:r[0].update(FX_signal="USDJPY_SHORT"),
        ):
            wrong=copy.deepcopy(rows);mutate(wrong)
            with self.assertRaises(ValueError):jp.validate(wrong)
        with self.assertRaises(ValueError):jp.validate(rows*2)
        with self.assertRaisesRegex(ValueError,"endpoint"):
            jp.capture([],AFTER,lambda u,h:(HTML,"https://fake.example/"),
                       observed_clock=lambda:SEEN)

    def test_missing_core_is_not_a_zero_release(self):
        raw=HTML.replace("前年同月比は2.3％の上昇".encode(),"データ未公表".encode())
        rows,r=jp.capture([],AFTER,lambda u,h:(raw,u))
        self.assertEqual(rows,[])
        self.assertEqual(r["state"],"OFFICIAL_NATIONAL_OCT_CPI_NOT_YET_OBSERVED")
        expired,report=jp.capture([],jp.RELEASE+timedelta(days=8),
            lambda *_:(_ for _ in ()).throw(AssertionError("outside window")))
        self.assertEqual(expired,[])
        self.assertEqual(report["state"],"OUTSIDE_FIRST_OBSERVATION_WINDOW_NO_HTTP")

    def test_run_appends_once_and_does_not_touch_operational_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"japan.jsonl"
            self.assertEqual(jp.run(path,AFTER,fetch,lambda:SEEN)["new_actuals"],1)
            self.assertEqual(jp.run(path,AFTER+timedelta(minutes=4),
                 lambda *_:(_ for _ in ()).throw(AssertionError("no fetch")))["new_actuals"],0)
            self.assertEqual(len(path.read_text().splitlines()),1)

if __name__=="__main__":unittest.main()
