import unittest
from datetime import datetime,timezone
from validation.macro.prepare_aud_twi_v1 import CONFIG,prepare_row,prepare
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
def fixture():
    dates=[datetime(2023+i//12,i%12+1,28).strftime("%d-%b-%Y") for i in range(46)]
    vs=[60+i/10 for i in range(46)]
    ident=next(iter(CONFIG));row=dict(id=ident,source_file=ident.removesuffix("_value")+".csv",frequency="M",unit="Index",dates=dates[:-2],values=vs[:-2],last_date=dates[-3],last_value=vs[-3])
    raw=("Title,Trade-weighted Index May 1970 = 100\nDescription,Australian Dollar Trade-weighted Index\nFrequency,Monthly\nUnits,Index\nSeries ID,FXRTWI\n"+"\n".join(f"{d},{v}" for d,v in zip(dates,vs))).encode()
    return row,raw
class Tests(unittest.TestCase):
    def test_refresh_and_no_change(self):
        row,raw=fixture()
        self.assertEqual(prepare_row(row,NOW,raw)["status"],"READY")
        self.assertEqual(prepare_row(row,NOW,raw)["status"],"NO_CHANGE")
    def test_wrong_definition_keeps_original(self):
        row,raw=fixture();out,r=prepare({"AUD":[row]},now=NOW,fetcher=lambda url:raw.replace(b"May 1970",b"June 1970"))
        self.assertEqual(r["series"][0]["status"],"WITHHELD");self.assertEqual(out["AUD"][0],row)
if __name__=="__main__":unittest.main()
