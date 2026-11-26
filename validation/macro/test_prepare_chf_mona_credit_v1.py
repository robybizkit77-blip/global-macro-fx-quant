import unittest,json,copy
from datetime import datetime,timezone
from validation.macro.prepare_chf_mona_credit_v1 import CONFIG,prepare_row
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
class TestMONA(unittest.TestCase):
    def test_scale_and_identity(self):
        for ident,(cube,key,unit,dims) in CONFIG.items():
            ds=[f"{2022+i//12}-{i%12+1:02d}" for i in range(48)]
            row=dict(id=ident,unit=unit,frequency="M",source_file=ident.removesuffix("_value")+".csv",dates=ds,values=[100.]*48,last_date=ds[-1],last_value=100.)
            data={"timeseries":[{"metadata":{"key":"BSTA@"+cube.removeprefix("BSTA.")+"{"+key+"}","frequency":"P1M","scale":"3","unit":"CHF"},"values":[{"date":d,"value":100000} for d in ds]+[{"date":"2026-01","value":101000}]}]}
            fetch=lambda url:json.dumps(data).encode()
            old=copy.deepcopy(row)
            self.assertEqual(prepare_row(row,ident,NOW,fetch)["status"],"READY")
            self.assertEqual(row["last_value"],101.)
            self.assertEqual(prepare_row(row,ident,NOW,fetch)["status"],"NO_CHANGE")
            data["timeseries"][0]["metadata"]["scale"]="6"
            with self.assertRaises(ValueError):prepare_row(old,ident,NOW,fetch)
            data["timeseries"][0]["metadata"]["scale"]="3"
            data["timeseries"][0]["values"][0]["value"]=101000
            with self.assertRaises(ValueError):prepare_row(old,ident,NOW,fetch)
if __name__=="__main__":unittest.main()
