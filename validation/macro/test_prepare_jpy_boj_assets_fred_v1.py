import unittest
from datetime import datetime,timezone
from validation.macro.prepare_jpy_boj_assets_fred_v1 import ID,CODE,prepare_row,prepare
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
def fixture(wrong=False,gap=False,offset=0,future=False):
    ds=[f"{2024+i//12}-{i%12+1:02d}" for i in range(35)]
    vs=[70+i*.01 for i in range(35)]
    row=dict(id=ID,unit="100 million yen",frequency="M",source_file="JP_BOJ_TOTAL_ASSETS_history.csv",dates=ds[:31],values=vs[:31],last_date=ds[30],last_value=vs[30])
    meta=f"<html><title>{'wrong' if wrong else 'Bank of Japan: Total Assets for Japan'} ({CODE})</title><body>Bank of Japan Units: 100 million yen, Not Seasonally Adjusted Frequency: Monthly</body></html>".encode()
    raw=("observation_date,"+CODE+"\n"+"\n".join(f"{d}-01,{v+offset}" for i,(d,v) in enumerate(zip(ds,vs)) if (future or i<34) and (not gap or i!=5))).encode()
    return row,lambda u:(meta if "/series/" in u else raw,u)
class Tests(unittest.TestCase):
    def test_full_overlap_and_idempotence(self):
        row,fetch=fixture()
        self.assertEqual(prepare_row(row,NOW,fetch)["status"],"READY")
        self.assertEqual(row["last_date"],"2026-10")
        self.assertEqual(prepare_row(row,NOW,fetch)["status"],"NO_CHANGE")
    def test_fail_closed(self):
        for args in ({"wrong":True},{"gap":True},{"offset":1},{"future":True}):
            row,fetch=fixture(**args)
            original={"JPY":[row],"USD":[]}
            out,receipt=prepare(original,now=NOW,fetcher=fetch)
            self.assertEqual(out,original)
            self.assertEqual(receipt["series"][0]["status"],"WITHHELD")
if __name__=="__main__":unittest.main()
