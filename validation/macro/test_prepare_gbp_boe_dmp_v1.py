import unittest,io
from datetime import datetime,timezone
from openpyxl import Workbook
from validation.macro.prepare_gbp_boe_dmp_v1 import CONFIG,observations,prepare_row,discover
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
def fixture():
    w=Workbook();w.remove(w.active)
    for key,(tab,*cols) in CONFIG.items():
        if tab not in w:w.create_sheet(tab)
        s=w[tab]
        for c in cols:
            s.cell(1,c,"High" if c==5 and len(cols)==2 else "Very high" if len(cols)==2 else "Expected" if key.endswith("Expected") else "Realised")
            if len(cols)==1:s.cell(2,c,"Single month")
        for i in range(46):
            d=datetime(2023+i//12,i%12+1,1)
            s.cell(3+i,1,d)
            for c in cols:s.cell(3+i,c,20 if len(cols)==2 else i/10)
    return w
class Tests(unittest.TestCase):
    def test_all_seven_and_idempotence(self):
        w=fixture()
        for key in CONFIG:
            obs=observations(w,key,"2026-10")
            ds=sorted(obs)[:-3];dates=[datetime.strptime(d,"%Y-%m").strftime("%b-%y") for d in ds];vs=[obs[d] for d in ds]
            row=dict(id=key,source_file="UK_BOE_DMP_LEAD_INDICATORS_history.csv",dates=dates,values=vs,last_date=dates[-1],last_value=vs[-1])
            self.assertEqual(prepare_row(row,key,obs,"2026-10","url","hash",NOW)["status"],"READY")
            self.assertEqual(prepare_row(row,key,obs,"2026-10","url","hash",NOW)["status"],"NO_CHANGE")
            broken=obs.copy();broken[ds[0]]+=5
            with self.assertRaises(ValueError):prepare_row(row,key,broken,"2026-10","url","hash",NOW)
    def test_discovery(self):
        b=io.BytesIO();fixture().save(b)
        def fetch(url):
            if url.endswith(".xlsx"):return b.getvalue(),url
            return b'<a href="/oct.xlsx">Monthly aggregate-level data October 2026</a>',url
        w,url,period,digest=discover(NOW,fetch);self.assertEqual(period,"2026-10");w.close()
if __name__=="__main__":unittest.main()
