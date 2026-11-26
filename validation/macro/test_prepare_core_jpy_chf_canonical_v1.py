import unittest
from unittest.mock import patch
from datetime import datetime,timezone
from validation.macro.prepare_core_jpy_chf_canonical_v1 import CONFIG,prepare_row
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
class Tests(unittest.TestCase):
    def fixture(self,ident):
        ccy,url,_,code=CONFIG[ident];dates=[f"{2023+i//12}-{i%12+1:02}" for i in range(46)];vs=[round(0.1+i/10,1) for i in range(46)]
        row=dict(id=ident,source_file=ident.removesuffix("_value")+".csv",unit="Percent YoY",frequency="M",dates=dates[:-2],values=vs[:-2],last_date=dates[-3],last_value=vs[-3])
        return row,(ccy,url,lambda raw,now:list(zip(dates,vs)),code)
    def test_both_sources(self):
        for ident in CONFIG:
            row,spec=self.fixture(ident)
            with patch.dict(CONFIG,{ident:spec}):
                self.assertEqual(prepare_row(row,ident,NOW,lambda _:b"fixture")["status"],"READY")
                self.assertEqual(row["last_date"],"2026-10")
                self.assertEqual(prepare_row(row,ident,NOW,lambda _:b"fixture")["status"],"NO_CHANGE")
    def test_wrong_history(self):
        ident=next(iter(CONFIG));row,spec=self.fixture(ident);row["values"][0]+=1
        with patch.dict(CONFIG,{ident:spec}):
            with self.assertRaises(ValueError):prepare_row(row,ident,NOW,lambda _:b"fixture")
if __name__=="__main__":unittest.main()
