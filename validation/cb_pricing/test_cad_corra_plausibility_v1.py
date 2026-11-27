import copy,json,unittest
from pathlib import Path
from validation.cb_pricing.cad_corra_plausibility_v1 import settlement,validate_changes,TENORS
from validation.cb_pricing.restore_cad_corra_incident_v1 import restore,BAD
F=json.loads(Path("validation/cb_pricing/CAD_CORRA_LAST_GOOD_2026-11-25.json").read_text())
class TestCADCORRA(unittest.TestCase):
    def test_bad_settlements(self):
        for x in (386,862,964,float("nan"),True):
            with self.assertRaises(ValueError): settlement(x)
        self.assertEqual(settlement(97.015),97.015)
    def test_previous_good(self):
        r=F["OIS_DATA"]
        validate_changes(r["provenance"]["observations"],{t:r["horizons"][t]["change_1d_bp"] for t in TENORS},{t:r["horizons"][t]["change_1w_bp"] for t in TENORS})
    def test_incident_scope_and_idempotence(self):
        c=copy.deepcopy(F["OIS_DATA"])
        c["as_of"]="2026-11-26"
        for t,v in zip(TENORS,BAD): c["horizons"][t]["rate"]=v
        o={"currencies":{"CAD":c,"USD":{"keep":1}}}
        op={"currencies":{"CAD":copy.deepcopy(c),"USD":{"keep":2}}}
        n={"CAD":{"rate":c["policy_rate"],"market_pricing":{"as_of":"2026-11-26",**{"h"+t:v for t,v in zip(TENORS,BAD)}},"keep":3},"USD":{"keep":4}}
        self.assertTrue(restore(o,n,op,F))
        self.assertEqual(o["currencies"]["CAD"]["as_of"],"2026-11-25")
        self.assertEqual((o["currencies"]["USD"],op["currencies"]["USD"],n["CAD"]["keep"],n["USD"]),({"keep":1},{"keep":2},3,{"keep":4}))
        self.assertFalse(restore(o,n,op,F))
