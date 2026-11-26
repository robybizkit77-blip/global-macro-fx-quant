import unittest,copy
from datetime import datetime,timezone
from validation.macro.prepare_jpy_meti_growth_v1 import reconcile,period
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
class TestMETI(unittest.TestCase):
    def test_period(self):
        self.assertEqual(period("202609"),"2026-09")
        self.assertIsNone(period("202613"))
    def test_identity_and_idempotence(self):
        ident="JP_IIP_history_value"
        ds=[f"{2022+i//12}-{i%12+1:02}" for i in range(48)]
        row=dict(id=ident,unit="Index 2020=100",frequency="M",source_file="JP_IIP_history.csv",dates=ds,values=[100.]*48,last_date=ds[-1],last_value=100.)
        old=copy.deepcopy(row);obs={d:100. for d in ds};obs["2026-01"]=101.
        self.assertEqual(reconcile(row,obs,NOW,b"test")["status"],"READY")
        self.assertEqual(row["last_date"],"2026-01")
        self.assertEqual(reconcile(row,obs,NOW,b"test")["status"],"NO_CHANGE")
        bad=dict(obs);bad[ds[0]]=100.1
        with self.assertRaises(ValueError):reconcile(old,bad,NOW,b"test")
        with self.assertRaises(ValueError):reconcile(old,{d:100. for d in ds[1:]},NOW,b"test")
if __name__=="__main__":unittest.main()
