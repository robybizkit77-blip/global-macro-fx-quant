import unittest
from unittest.mock import patch
from datetime import datetime,timezone
from validation.macro.prepare_jpy_employment_lfs_v1 import CONFIG,prepare_row
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
def fixture():
    ident=next(iter(CONFIG));dates=[f"{2023+i//12}-{i%12+1:02}" for i in range(45)];vs=[6700+i for i in range(45)]
    row=dict(id=ident,source_file=ident.removesuffix("_value")+".csv",unit="10k persons",frequency="M",dates=dates[:-2],values=vs[:-2],last_date=dates[-3],last_value=vs[-3])
    return row,{"SA":dict(zip(dates,vs)),"NSA":dict(zip(dates,[v+50 for v in vs]))}
class Tests(unittest.TestCase):
    def test_sa_only(self):
        row,data=fixture()
        with patch("validation.macro.prepare_jpy_employment_lfs_v1.parse",return_value=data):
            self.assertEqual(prepare_row(row,NOW,b"fixture")["status"],"READY")
            self.assertEqual(row["last_date"],"2026-09")
            self.assertEqual(row["last_value"],6744)
            self.assertEqual(prepare_row(row,NOW,b"fixture")["status"],"NO_CHANGE")
    def test_wrong_history(self):
        row,data=fixture();row["values"][0]+=1
        with patch("validation.macro.prepare_jpy_employment_lfs_v1.parse",return_value=data):
            with self.assertRaises(ValueError):prepare_row(row,NOW,b"fixture")
if __name__=="__main__":unittest.main()
