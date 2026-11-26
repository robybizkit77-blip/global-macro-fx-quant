import json,unittest
from datetime import datetime,timezone
from validation.macro.prepare_jpy_tankan_actual_v1 import CONFIG,prepare_row
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
def fixture(ident,wrong=False,gap=False,offset=0):
    code,title,style=CONFIG[ident];qs=[2018*4+i for i in range(35)]
    ds=[f"{q//4}-Q{q%4+1}" if style=="Q" else f"{q//4}/{(q%4+1)*3:02d}" for q in qs]
    vs=[-12+i for i in range(35)]
    row=dict(id=ident,unit="% points" if style=="Q" else "",frequency="Q" if style=="Q" else "",source_file="JP_TANKAN_LENDING_ATTITUDE_history.csv" if style=="Q" else "JP_BOJ_TANKAN_LEAD_INDICATORS_history.csv",dates=ds[:-1],values=vs[:-1],last_date=ds[-2],last_value=vs[-2])
    dates=[int(f"{q//4}{q%4+1:02d}") for q in qs];values=[v+offset for v in vs]
    if gap:values[10]=None
    data={"STATUS":200,"RESULTSET":[{"SERIES_CODE":code,"UNIT":"% points","FREQUENCY":"QUARTERLY","NAME_OF_TIME_SERIES":title if not wrong else title.replace("Actual result","Forecast"),"VALUES":{"SURVEY_DATES":dates,"VALUES":values}}]}
    return row,lambda url:json.dumps(data).encode()
class Tests(unittest.TestCase):
    def test_valid_idempotent(self):
        for ident in CONFIG:
            row,f=fixture(ident);self.assertEqual(prepare_row(row,ident,NOW,f)["status"],"READY");self.assertEqual(prepare_row(row,ident,NOW,f)["status"],"NO_CHANGE")
    def test_fail_closed(self):
        for ident in CONFIG:
            for kw in ({"wrong":True},{"gap":True},{"offset":5}):
                row,f=fixture(ident,**kw)
                with self.assertRaises(ValueError):prepare_row(row,ident,NOW,f)
if __name__=="__main__":unittest.main()
