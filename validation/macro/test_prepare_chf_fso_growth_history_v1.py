import copy,unittest
from datetime import datetime,timezone
from validation.macro.prepare_chf_fso_growth_history_v1 import CONFIG,discover,reconcile
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
class TestFSOGrowth(unittest.TestCase):
    def test_discovery(self):
        seed,title,code,*_=CONFIG["CH_RETAIL_REAL_history_value"]
        def fetch(url):
            suffix='<p>available in a newer version</p><a href="/en/asset/36970302">'+title+'</a>' if url.endswith(str(seed)) else ''
            return ('<h1>'+title+'</h1><p>'+code+'</p>'+suffix).encode()
        self.assertEqual(discover(seed,title,code,fetch)[0],36970302)
    def test_revisions_and_identity(self):
        ident="CH_PRODUCTION_history_value"
        ds=[f"{2022+i//12}-{1+i%12:02d}" for i in range(48)]
        row=dict(id=ident,unit="Index 2021=100",frequency="M",source_file="CH_PRODUCTION_history.csv",dates=ds,values=[100.0]*48,last_date=ds[-1],last_value=100.)
        obs={d:100.05 for d in ds};obs["2026-01"]=101.
        original=copy.deepcopy(row)
        self.assertEqual(reconcile(row,obs,NOW,37030901,"source",b"test")["status"],"READY")
        self.assertEqual(row["last_date"],"2026-01")
        self.assertEqual(reconcile(row,obs,NOW,37030901,"source",b"test")["status"],"NO_CHANGE")
        with self.assertRaises(ValueError):reconcile(original,{d:105. for d in ds},NOW,37030901,"source",b"test")
        with self.assertRaises(ValueError):reconcile(original,{d:100. for d in ds[1:]},NOW,37030901,"source",b"test")
if __name__=="__main__":unittest.main()
