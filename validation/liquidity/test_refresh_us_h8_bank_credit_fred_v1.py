#!/usr/bin/env python3
"""Offline US TOTBKCR H.8/FRED guards: weekly source, vintage, Core isolation."""
import csv
import io
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from validation.liquidity.refresh_us_h8_bank_credit_fred_v1 import (
    parse, emit_js, run, ANCHOR_DATE, ANCHOR_VALUE, existing_obs, DEST
)
DAY=date(2026,11,14)

def sample(*,reverse=False):
    dates=[date(2026,8,12)+timedelta(days=7*i) for i in range(14)]
    pairs=[(d.isoformat(),ANCHOR_VALUE+(i-4)*10) for i,d in enumerate(dates)]
    if reverse:pairs.reverse()
    buf=io.StringIO()
    w=csv.writer(buf)
    w.writerow(['observation_date','TOTBKCR'])
    w.writerows(pairs)
    return buf.getvalue()

class USH8SourceTest(unittest.TestCase):
    def test_source_identity_and_wednesday(self):
        x=parse(sample(),today=DAY)
        self.assertEqual(x['dates'][4],ANCHOR_DATE)
        self.assertEqual(x['latest_observation'],'2026-11-11')
        self.assertEqual(x['values'][0],ANCHOR_VALUE)

    def test_latest_first_csv_accepted(self):
        self.assertEqual(parse(sample(reverse=True),today=DAY)['latest_observation'],'2026-11-11')

    def test_wrong_series_key_withheld(self):
        with self.assertRaisesRegex(ValueError,'exact series/CSV key'):
            parse(sample().replace('TOTBKCR','TOTBKCRNSA'),today=DAY)

    def test_bad_weekday_and_week_gap(self):
        with self.assertRaisesRegex(ValueError,'Wednesday'):
            parse(sample().replace('2026-09-09','2026-09-08'),today=DAY)
        lines=sample().splitlines()
        gapped='\n'.join(row for row in lines if not any(x in row for x in ('2026-10-07','2026-10-14','2026-10-21')))+'\n'
        with self.assertRaisesRegex(ValueError,'weekly gap'):
            parse(gapped,today=DAY)

    def test_source_overlap_or_outlier_withheld(self):
        with self.assertRaisesRegex(ValueError,'diverges'):
            parse(sample().replace('19866.6568','24000'),today=DAY)
        with self.assertRaisesRegex(ValueError,'week-to-week stock jump'):
            parse(sample().replace(str(ANCHOR_VALUE+10),str(ANCHOR_VALUE+2300)),today=DAY)

    def test_source_older_than_35_days_not_current(self):
        with self.assertRaisesRegex(ValueError,'too old'):
            parse(sample(),today=date(2027,1,15))

    def test_future_date_or_duplicate_not_accepted(self):
        with self.assertRaisesRegex(ValueError,'source latest date'):
            parse(sample(),today=date(2026,10,1))
        with self.assertRaisesRegex(ValueError,'duplicate'):
            parse(sample()+f'2026-11-11,19956.6568\n',today=DAY)

    def test_render_and_no_unsafe_canonical_writes(self):
        p=parse(sample(),today=DAY)
        output=emit_js(p,DAY.isoformat())
        self.assertIn('"eligible_for_fx_core": false',output)
        self.assertIn('"first_release_pit_verified": false',output)
        self.assertIn('"eligible_for_backtest": false',output)
        self.assertEqual(existing_obs(output),(p['dates'],p['values']))
        with tempfile.TemporaryDirectory() as temp:
            f=Path(temp)/'input.csv'
            dest=Path(temp)/'fred-source.js'
            f.write_text(sample(),encoding='utf-8')
            r=run(dest,apply=True,fixture=f,today=DAY)
            self.assertEqual(r['write_state'],'RESEARCH_SIDECAR_ONLY')
            self.assertTrue(dest.exists())
            r=run(dest,apply=True,fixture=f,today=DAY)
            self.assertEqual(r['status'],'NO_CHANGE')
            self.assertEqual(r['write_state'],'NO_MUTATION')

if __name__=='__main__':unittest.main()
