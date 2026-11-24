#!/usr/bin/env python3
"""Offline US TOTBKCR H.8/FRED guards: weekly source, vintage, Core isolation."""
import csv
import io
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from validation.liquidity.refresh_us_h8_bank_credit_fred_v1 import (
    parse, parse_sloos, parse_m2, emit_js, run, ANCHOR_DATE, ANCHOR_VALUE, existing_obs, existing_payload
)
DAY=date(2026,11,14)
SLOOS_SAMPLE=("observation_date,DRTSCILM\n2026-01-01,5.3\n2026-04-01,8.1\n"
              "2026-07-01,0.0\n2026-10-01,1.7\n")

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
        self.assertEqual(x['values'][4],ANCHOR_VALUE)

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

    def test_sloos_series_and_period_guards(self):
        self.assertEqual(parse_sloos(SLOOS_SAMPLE,today=DAY)['observations'][-2:],
                         [['2026-07-01',0],['2026-10-01',1.7]])
        for invalid,reason in [
            (SLOOS_SAMPLE.replace('DRTSCILM','DRTSCIS'),'exact series'),
            (SLOOS_SAMPLE.replace('2026-07-01','2026-07-02'),'invalid survey period'),
            (SLOOS_SAMPLE.replace('2026-07-01,0.0','2026-07-01,NaN'),'outside range'),
            (SLOOS_SAMPLE+'2027-01-01,2.0\n','invalid survey period'),
            (SLOOS_SAMPLE.replace('2026-07-01,0.0\n',''),'quarterly ordering or gap'),
        ]:
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):
                parse_sloos(invalid,today=DAY)

    def test_each_source_can_update_and_preserve_other_data(self):
        with tempfile.TemporaryDirectory() as temp:
            h8=Path(temp)/'h8.csv'
            sloos=Path(temp)/'sloos.csv'
            dest=Path(temp)/'research.js'
            h8.write_text(sample(),encoding='utf-8')
            run(dest,apply=True,fixture=h8,today=DAY)
            original=existing_payload(dest.read_text(encoding='utf-8'))

            sloos.write_text(SLOOS_SAMPLE,encoding='utf-8')
            inputs={'apply':True,'fixture':h8,'sloos_fixture':sloos,'today':DAY}
            r=run(dest,**inputs)
            self.assertEqual(r['sloos'],{'status':'VERIFIED','latest_survey_period':'2026-10-01'})
            self.assertEqual(r['write_state'],'RESEARCH_SIDECAR_ONLY')
            self.assertEqual(run(dest,**inputs)['status'],'NO_CHANGE')

            h8.write_text('invalid weekly source',encoding='utf-8')
            sloos.write_text(SLOOS_SAMPLE+'2027-01-01,2.0\n',encoding='utf-8')
            r=run(dest,**{**inputs,'today':date(2027,2,5)})
            self.assertTrue(r['h8']['status'].startswith('WITHHELD'))
            current=existing_payload(dest.read_text(encoding='utf-8'))
            self.assertEqual(current['values'],original['values'])
            self.assertEqual(current['last_checked_rome'],original['last_checked_rome'])
            self.assertEqual(current['lending_standards']['observations'][-1],['2027-01-01',2])

            h8.write_text(sample().replace(str(ANCHOR_VALUE+90),str(ANCHOR_VALUE+95)),encoding='utf-8')
            sloos.write_text('invalid quarterly source',encoding='utf-8')
            r=run(dest,**inputs)
            self.assertEqual(r['sloos']['retained_survey_period'],'2027-01-01')
            self.assertEqual(r['write_state'],'RESEARCH_SIDECAR_ONLY')
            current=existing_payload(dest.read_text(encoding='utf-8'))
            self.assertEqual(current['values'][-1],ANCHOR_VALUE+95)
            self.assertEqual(current['lending_standards']['observations'][-1],['2027-01-01',2])


    def test_m2_identity_overlap_continuity_and_isolated_refresh(self):
        rows=["observation_date,M2SL"]
        for i in range(21):
            y,m=divmod(2025*12+i,12)
            rows.append(f"{y:04d}-{m+1:02d}-01,{23342.8+(i-19)*75}")
        raw="\n".join(rows)+"\n"
        x=parse_m2(raw,today=DAY)
        self.assertEqual(x["latest_observation"],"2026-09")
        self.assertEqual(x["values"][-1],23417.8)
        for bad in (raw.replace("M2SL","M2NS"),raw.replace("2026-08-01,23342.8","2026-08-01,33342.8"),
                    raw.replace("2026-08-01","2026-07-01"),raw+"2026-11-01,24000\n"):
            with self.assertRaises(ValueError):parse_m2(bad,today=DAY)
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/"research.js";h8=Path(temp)/"h8.csv";m2=Path(temp)/"m2.csv"
            h8.write_text(sample());m2.write_text(raw)
            run(dest,apply=True,fixture=h8,today=DAY)
            before=existing_payload(dest.read_text())
            h8.write_text("invalid weekly source")
            args={"apply":True,"fixture":h8,"m2_fixture":m2,"today":DAY}
            r=run(dest,**args)
            self.assertEqual(r["m2"]["status"],"VERIFIED")
            self.assertTrue(r["h8"]["status"].startswith("WITHHELD"))
            after=existing_payload(dest.read_text())
            self.assertEqual(after["values"],before["values"])
            self.assertEqual(after["money_stock"],x)
            h8.write_text(sample())
            self.assertEqual(run(dest,**args)["status"],"NO_CHANGE")
            m2.write_text("invalid M2")
            self.assertEqual(run(dest,**args)["m2"]["retained_observation"],"2026-09")

if __name__=='__main__':unittest.main()
