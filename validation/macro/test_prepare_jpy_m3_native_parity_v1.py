import unittest,copy
from datetime import datetime,timezone
from validation.macro.prepare_jpy_m3_native_parity_v1 import prepare,IDENT
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
def fixture():
    ds=[f"{2024+i//12}-{1+i%12:02d}" for i in range(34)]
    vs=[100+i for i in range(34)]
    def series(d,v):return {"label":"M3","dates":d,"values":v,"last_date":d[-1],"last_value":v[-1]}
    old=series(ds[:32],vs[:32]);old.update(id=IDENT,unit="100 million yen",frequency="M",source_file="JP_M3_SA_history.csv")
    new=series(ds,vs);new["values"][30]+=1
    return {"JPY":[old],"EUR":[]},{"JPY":{"money":new}}
class M3ParityTests(unittest.TestCase):
    def test_reuse_and_idempotence(self):
        old,native=fixture();saved=copy.deepcopy(native)
        out,r=prepare(old,native,NOW)
        self.assertEqual(r["after"],"2026-10")
        self.assertEqual(r["revised_months"],["2026-07"])
        self.assertEqual(out["EUR"],old["EUR"])
        self.assertEqual(native,saved)
        self.assertEqual(prepare(out,native,NOW)[1]["status"],"NO_CHANGE")
    def test_old_revision_is_withheld(self):
        old,native=fixture();native["JPY"]["money"]["values"][5]+=1
        with self.assertRaisesRegex(ValueError,"older M3 revision"):prepare(old,native,NOW)
    def test_future_and_regression(self):
        old,native=fixture()
        with self.assertRaises(ValueError):prepare(old,native,datetime(2026,10,1,tzinfo=timezone.utc))
        native["JPY"]["money"]["dates"][4]="2024-01"
        with self.assertRaises(ValueError):prepare(old,native,NOW)
if __name__=="__main__":unittest.main()
