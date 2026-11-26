import copy,unittest
from datetime import datetime,timezone
from validation.macro.prepare_nzd_rbnz_employment_sfm_v1 import CONFIG,reconcile
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
class TestNZRBNZ(unittest.TestCase):
    def test_revision_guards(self):
        for ident,(_,code,_,_,_,unit,med,mx) in CONFIG.items():
            ds=[f"{2019+i//4}-{3*(i%4+1):02d}" for i in range(28)]
            row=dict(id=ident,unit=unit,frequency="Q",source_file=ident.removesuffix("_value")+".csv",dates=ds,values=[2.]*28,last_date=ds[-1],last_value=2.)
            old=copy.deepcopy(row);obs={d:2. for d in ds};obs["2026-03"]=2.1
            self.assertEqual(reconcile(row,obs,"2026-11-04",b"test",NOW)["status"],"READY")
            self.assertEqual(reconcile(row,obs,"2026-11-04",b"test",NOW)["status"],"NO_CHANGE")
            bad=dict(obs);bad[ds[0]]=2+mx+1
            with self.assertRaises(ValueError):reconcile(old,bad,"2026-11-04",b"test",NOW)
            with self.assertRaises(ValueError):reconcile(old,{d:2. for d in ds[1:]},"2026-11-04",b"test",NOW)
if __name__=="__main__":unittest.main()
