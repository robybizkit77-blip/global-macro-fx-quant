import unittest
from datetime import datetime,timezone
from validation.macro.prepare_gbp_ons_paye_v1 import CONFIG,prepare_row
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
def fixture():
    dates=[f"{2023+i//12}-{i%12+1:02}" for i in range(46)]
    values=[30_000_000+i*100 for i in range(46)]
    data=["Figure 1: payrolled employees,","Payrolled employees,","Unit,Payrolled employees","Date,Payrolled employees,Flash estimate"]
    data[1]='"Payrolled employees, seasonally adjusted, UK, July 2014 to October 2026",'
    data+= [f"{d},{v},{v if i==44 else ''}" if i<45 else f"{d},,{v}" for i,(d,v) in enumerate(zip(dates,values))]
    ident=next(iter(CONFIG));row=dict(id=ident,source_file=ident.removesuffix("_value")+".csv",unit="persons",frequency="M",dates=dates[:43],values=values[:43],last_date=dates[42],last_value=values[42])
    return row,("\n".join(data)+"\n").encode()
class Tests(unittest.TestCase):
    def test_flash_excluded_and_idempotent(self):
        row,raw=fixture()
        r=prepare_row(row,NOW,raw,"url");self.assertEqual(r["status"],"READY")
        self.assertEqual(row["last_date"],"2026-09")
        self.assertEqual(r["flash"]["period"],"2026-10")
        self.assertEqual(prepare_row(row,NOW,raw,"url")["status"],"NO_CHANGE")
    def test_wrong_scope_rejected(self):
        row,raw=fixture()
        with self.assertRaises(ValueError):prepare_row(row,NOW,raw.replace(b"seasonally adjusted",b"not seasonally adjusted"),"url")
if __name__=="__main__":unittest.main()
