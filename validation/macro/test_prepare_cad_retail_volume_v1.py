import unittest
from datetime import datetime,timezone
from validation.macro.prepare_cad_retail_volume_v1 import ID,prepare_row
NOW=datetime(2026,12,1,tzinfo=timezone.utc)
def fixture(measure="Retail sales in chained 2017 dollars",gap=False):
    ds=[f"{2024+i//12}-{i%12+1:02d}" for i in range(34)]
    vs=[60000+i for i in range(34)]
    row=dict(id=ID,source_file="CA_RETAIL_VOLUME_history.csv",unit="million chained 2017 CAD SA",frequency="M",dates=ds[:-1],values=vs[:-1],last_date=ds[-2],last_value=vs[-2])
    raw="REF_DATE,GEO,UOM,SCALAR_FACTOR,VECTOR,VALUE,Sales, price and volume,North American Industry Classification System\n"
    # Quote the dimension header because it contains a comma.
    raw='REF_DATE,GEO,UOM,SCALAR_FACTOR,VECTOR,VALUE,"Sales, price and volume",North American Industry Classification System\n'
    raw+="\n".join(f"{d},Canada,Dollars,Millions,v1,{v},{measure},Retail trade [44-45]" for i,(d,v) in enumerate(zip(ds,vs)) if not gap or i!=10)
    return row,raw
class Tests(unittest.TestCase):
    def test_valid_and_idempotent(self):
        row,raw=fixture();self.assertEqual(prepare_row(row,NOW,raw)["status"],"READY");self.assertEqual(prepare_row(row,NOW,raw)["status"],"NO_CHANGE")
    def test_reject_unchained_and_gap(self):
        for kw in ({"measure":"Retail sales at 2017 constant prices (Unchained Laspeyres Index)"},{"gap":True}):
            row,raw=fixture(**kw)
            with self.assertRaises(ValueError):prepare_row(row,NOW,raw)
if __name__=="__main__":unittest.main()
