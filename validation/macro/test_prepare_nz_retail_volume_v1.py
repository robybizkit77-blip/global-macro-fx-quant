import csv,io,unittest
from datetime import datetime,timezone
from urllib.error import HTTPError
from zipfile import ZipFile
from validation.macro.prepare_nz_retail_volume_v1 import ID,CODE,META,prepare_row,archive_url
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
def fixture(wrong=False,gap=False):
    ds=[f"{2018+i//4}-{3+3*(i%4):02d}" for i in range(35)];vs=[26000+i for i in range(34)]+[26488]
    row=dict(id=ID,source_file="NZ_RETAIL_VOLUME_Q_history.csv",unit="NZD million, deflated Sep 2010 quarter prices, SA",frequency="Q",dates=ds[:-1],values=vs[:-1],last_date=ds[-2],last_value=vs[-2])
    f=io.StringIO();w=csv.DictWriter(f,fieldnames=["Series_reference","Period","Data_value",*META]);w.writeheader()
    for i,(d,v) in enumerate(zip(ds,vs)):
        if gap and i==10:continue
        m=dict(META)
        if wrong:m["Series_title_4"]="Unadjusted"
        w.writerow(dict(Series_reference=CODE,Period=d,Data_value=v,**m))
    z=io.BytesIO()
    with ZipFile(z,"w") as a:a.writestr("data.csv",f.getvalue())
    return row,lambda url:(z.getvalue(),url)
class Tests(unittest.TestCase):
    def test_valid_idempotent(self):
        row,fetch=fixture();self.assertEqual(prepare_row(row,NOW,fetch)["status"],"READY");self.assertEqual(row["last_date"],"2026-09");self.assertEqual(prepare_row(row,NOW,fetch)["status"],"NO_CHANGE")
    def test_bad_definition_gap(self):
        for kw in ({"wrong":True},{"gap":True}):
            row,fetch=fixture(**kw)
            with self.assertRaises(ValueError):prepare_row(row,NOW,fetch)
    def test_fallback_404_only(self):
        row,fetch=fixture()
        def delayed(url):
            if "December-2026" in url:raise HTTPError(url,404,"not released",None,None)
            return fetch(url)
        self.assertEqual(prepare_row(row,datetime(2027,1,5,tzinfo=timezone.utc),delayed)["after"],"2026-09")
if __name__=="__main__":unittest.main()
