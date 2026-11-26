import unittest
from datetime import datetime,timezone
from validation.macro.prepare_nzd_rbnz_m15_v1 import parse,prepare,CONFIG
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
HEADER='<h1>Business Expectations Survey (M15)</h1><p>Released:</p><p>24 November 2026</p><table><tr><th></th><th colspan="4">Annual CPI growth (%)</th><th colspan="2">Annual Wage Growth (%)</th><th colspan="2">Unemployment Rate (%)</th></tr><tr>'+''.join('<th>'+x+'</th>' for x in ('Date','1 year ahead','2 years ahead','5 years ahead','10 years ahead','1 year ahead','2 years ahead','1 year ahead','2 years ahead'))+'</tr>'
DATA=[('Dec 2025',[2.42,2.39,2.81,3.56,2.56,3.04,5.14,4.78]),('Mar 2026',[2.60,2.59,2.73,3.21,2.71,3.19,5.18,4.92]),('Jun 2026',[3.68,2.87,2.72,2.94,2.81,3.10,5.50,5.25]),('Sept 2026',[2.99,2.55,2.48,2.51,2.82,3.02,5.22,4.89]),('Dec 2026',[3.06,2.57,2.39,2.48,2.77,2.95,5.25,4.96])]
RAW=(HEADER+''.join('<tr><td>'+d+'</td>'+''.join('<td>'+str(v)+'</td>' for v in vs)+'</tr>' for d,vs in DATA)+'</table>').encode()
def fixture():
    ds=['2025-12','2026-03','2026-06','2026-09']
    return {'NZD':[dict(id=k,source_file='NZ_RBNZ_M15_BUSINESS_EXPECTATIONS_recent.csv',dates=ds.copy(),values=[x[1][i] for x in DATA[:-1]],last_date=ds[-1],last_value=DATA[-2][1][i]) for k,i in CONFIG.items()]}
class Tests(unittest.TestCase):
    def test_release_reference_and_repeat(self):
        obs,release=parse(RAW,NOW)
        self.assertEqual(release,'2026-11-24')
        self.assertEqual(obs['2026-12'],DATA[-1][1])
        out,r=prepare(fixture(),now=NOW,fetcher=lambda _:RAW)
        self.assertEqual([x['status'] for x in r['series']],['READY']*8)
        self.assertEqual([x['status'] for x in prepare(out,now=NOW,fetcher=lambda _:RAW)[1]['series']],['NO_CHANGE']*8)
    def test_future_release_or_mismatch_keeps_prior(self):
        x=fixture()
        for raw in (RAW.replace(b'24 November',b'27 November'),RAW.replace(b'2.99',b'7.99')):
            out,r=prepare(x,now=NOW,fetcher=lambda _:raw)
            self.assertEqual(out,x)
            self.assertEqual([i['status'] for i in r['series']],['WITHHELD']*8)
if __name__=="__main__":unittest.main()
