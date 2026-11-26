import json,unittest
from datetime import datetime,timezone
from validation.macro.prepare_chf_snb_balance_mortgage_v1 import CONFIG,prepare_row,prepare
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
def fixture(ident):
    cube,key,unit,_=CONFIG[ident]
    dates=[f"{2023+i//12}-{i%12+1:02}" for i in range(45)]
    vs=[400000+i if cube=="snbbipo" else 1+i/100 for i in range(45)]
    row=dict(id=ident,source_file=ident.removesuffix("_value")+".csv",unit=unit,frequency="M",dates=dates[:-2],values=vs[:-2],last_date=dates[-3],last_value=vs[-3])
    data=dict(timeseries=[dict(metadata=dict(key="EPB@SNB."+cube+"{"+key+"}",frequency="P1M",scale="",unit="In CHF millions" if cube=="snbbipo" else None),values=[dict(date=d,value=v) for d,v in zip(dates,vs)])])
    return row,data
class Tests(unittest.TestCase):
    def test_three_rows(self):
        for ident in CONFIG:
            row,data=fixture(ident);fetch=lambda _:json.dumps(data).encode()
            self.assertEqual(prepare_row(row,ident,NOW,fetch)["status"],"READY")
            self.assertEqual(prepare_row(row,ident,NOW,fetch)["status"],"NO_CHANGE")
    def test_wrong_history(self):
        ident=next(iter(CONFIG));row,data=fixture(ident);data["timeseries"][0]["values"][0]["value"]+=100
        with self.assertRaises(ValueError):prepare_row(row,ident,NOW,lambda _:json.dumps(data).encode())
    def test_wrong_identity(self):
        ident=next(iter(CONFIG));row,data=fixture(ident);data["timeseries"][0]["metadata"]["key"]="other"
        with self.assertRaises(ValueError):prepare_row(row,ident,NOW,lambda _:json.dumps(data).encode())
if __name__=="__main__":unittest.main()
