import unittest
from datetime import datetime,timezone
from validation.macro.prepare_nzd_rbnz_m15_v1 import parse,prepare,CONFIG
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
import io
from openpyxl import Workbook
from validation.macro.prepare_nzd_rbnz_m15_v1 import HEAD,KEYS
DATA=[('Dec 2025',[2.42,2.39,2.81,3.56,2.56,3.04,5.14,4.78]),('Mar 2026',[2.60,2.59,2.73,3.21,2.71,3.19,5.18,4.92]),('Jun 2026',[3.68,2.87,2.72,2.94,2.81,3.10,5.50,5.25]),('Sept 2026',[2.99,2.55,2.48,2.51,2.82,3.02,5.22,4.89]),('Dec 2026',[3.06,2.57,2.39,2.48,2.77,2.95,5.25,4.96])]
def workbook(data=DATA,*,bad_header=False):
    wb=Workbook();ws=wb.active;ws.title="Sheet1";ws.append(("wrong",)+HEAD[1:] if bad_header else HEAD)
    for d,values in data:
        month,year=d.split();period=year+"-"+{"Dec":"12-31","Mar":"03-31","Jun":"06-30","Sept":"09-30"}[month]
        for (stat,horizon),v in zip(KEYS,values):
            ws.append([period,stat,horizon,"All","All",300,v,.1,v-.2,v+.2,.03,0,0,v,0,"BES aggregate"])
    f=io.BytesIO();wb.save(f);wb.close();return f.getvalue()
RAW=workbook()
def fixture():
    ds=['2025-12','2026-03','2026-06','2026-09']
    return {'NZD':[dict(id=k,source_file='NZ_RBNZ_M15_BUSINESS_EXPECTATIONS_recent.csv',dates=ds.copy(),values=[x[1][i] for x in DATA[:-1]],last_date=ds[-1],last_value=DATA[-2][1][i]) for k,i in CONFIG.items()]}
class Tests(unittest.TestCase):
    def test_release_reference_and_repeat(self):
        obs,release=parse(RAW,NOW)
        self.assertEqual(release,'2026-11-26')
        self.assertEqual(obs['2026-12'],DATA[-1][1])
        out,r=prepare(fixture(),now=NOW,fetcher=lambda _:RAW)
        self.assertEqual([x['status'] for x in r['series']],['READY']*8)
        self.assertEqual([x['status'] for x in prepare(out,now=NOW,fetcher=lambda _:RAW)[1]['series']],['NO_CHANGE']*8)
    def test_future_release_or_mismatch_keeps_prior(self):
        x=fixture()
        for raw in (workbook(bad_header=True),workbook(DATA[:-2]+[('Sept 2026',[7.99]+DATA[-2][1][1:]),DATA[-1]])):
            out,r=prepare(x,now=NOW,fetcher=lambda _:raw)
            self.assertEqual(out,x)
            self.assertEqual([i['status'] for i in r['series']],['WITHHELD']*8)
if __name__=="__main__":unittest.main()
