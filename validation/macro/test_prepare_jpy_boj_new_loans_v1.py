import json,unittest
from datetime import datetime,timezone
from validation.macro.prepare_jpy_boj_new_loans_v1 import CONFIG,prepare_row
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
def fixture():
    ident,code=next(iter(CONFIG.items()));dates=[f"{2023+i//12}-{i%12+1:02}" for i in range(45)];vs=[round(.5+i/100,3) for i in range(45)]
    row=dict(id=ident,source_file=ident.removesuffix("_value")+".csv",unit="Percent per annum",frequency="M",dates=dates[:-2],values=vs[:-2],last_date=dates[-3],last_value=vs[-3])
    data={"STATUS":200,"RESULTSET":[{"SERIES_CODE":code,"UNIT":"Percent per annum","FREQUENCY":"MONTHLY","NAME_OF_TIME_SERIES":"New Loans and Discounts/Total/Domestically Licensed Banks","VALUES":{"SURVEY_DATES":[d.replace("-","") for d in dates],"VALUES":vs}}]}
    return row,data
class Tests(unittest.TestCase):
    def test_refresh_and_idempotence(self):
        row,data=fixture();f=lambda _:json.dumps(data).encode()
        self.assertEqual(prepare_row(row,NOW,f)["status"],"READY")
        self.assertEqual(prepare_row(row,NOW,f)["status"],"NO_CHANGE")
    def test_wrong_scope(self):
        row,data=fixture();data["RESULTSET"][0]["NAME_OF_TIME_SERIES"]="Outstanding loans"
        with self.assertRaises(ValueError):prepare_row(row,NOW,lambda _:json.dumps(data).encode())
    def test_wrong_history(self):
        row,data=fixture();data["RESULTSET"][0]["VALUES"]["VALUES"][0]+=1
        with self.assertRaises(ValueError):prepare_row(row,NOW,lambda _:json.dumps(data).encode())
if __name__=="__main__":unittest.main()
