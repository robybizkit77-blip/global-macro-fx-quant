import unittest,io
from datetime import datetime,timezone
from openpyxl import Workbook
from validation.macro.prepare_jpy_boj_reserve_average_v1 import CONFIG,prepare_row
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
def fixture():
    w=Workbook();s=w.active;s.title="Average amounts outstanding";s.append(["Unit: 100 million yen"]);s.append(["Date",None,None,None,None,None,"Reserve\nBalances"])
    dates=[f"{2023+i//12}-{i%12+1:02}" for i in range(46)];vs=[3_800_000+1000*i for i in range(46)]
    for d,v in zip(dates,vs):s.append([datetime.strptime(d,"%Y-%m"),None,None,None,None,None,v])
    w.create_sheet("Amounts at end of period")
    b=io.BytesIO();w.save(b)
    ident=next(iter(CONFIG));row=dict(id=ident,source_file=ident.removesuffix("_value")+".csv",frequency="M",unit="100 million yen",dates=dates[:-2],values=vs[:-2],last_date=dates[-3],last_value=vs[-3])
    return row,b.getvalue()
class Tests(unittest.TestCase):
    def test_refresh_and_idempotence(self):
        row,raw=fixture();self.assertEqual(prepare_row(row,NOW,raw)["status"],"READY");self.assertEqual(row["last_date"],"2026-10")
        self.assertEqual(prepare_row(row,NOW,raw)["status"],"NO_CHANGE")
    def test_wrong_history_rejected(self):
        row,raw=fixture();row["values"][0]*=1.2
        with self.assertRaises(ValueError):prepare_row(row,NOW,raw)
if __name__=="__main__":unittest.main()
