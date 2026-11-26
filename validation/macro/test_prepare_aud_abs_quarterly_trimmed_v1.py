import unittest,copy
from datetime import datetime,timezone
from validation.macro.prepare_aud_abs_quarterly_trimmed_v1 import ID,reconcile
class TestABSQuarterly(unittest.TestCase):
    def test_revisions(self):
        now=datetime(2026,11,26,tzinfo=timezone.utc);ds=[f"{2019+i//4}-{3*(i%4+1):02}" for i in range(28)]
        row=dict(id=ID,unit="percent YoY SA",frequency="Q",source_file="AU_CPI_TRIMMED_MEAN_Q_YOY_history.csv",dates=ds,values=[3.]*28,last_date=ds[-1],last_value=3.)
        old=copy.deepcopy(row);obs={d:3. for d in ds};obs["2026-03"]=3.2
        self.assertEqual(reconcile(row,obs,"official",b"x",now)["status"],"READY")
        self.assertEqual(reconcile(row,obs,"official",b"x",now)["status"],"NO_CHANGE")
        bad=dict(obs);bad[ds[0]]=4
        with self.assertRaises(ValueError):reconcile(old,bad,"official",b"x",now)
        with self.assertRaises(ValueError):reconcile(old,{d:3. for d in ds[1:]},"official",b"x",now)
if __name__=="__main__":unittest.main()
