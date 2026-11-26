import copy,json,unittest
from datetime import datetime,timezone
from validation.macro.prepare_native_liquidity_macro_parity_v1 import CONFIG,prepare
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
def fixture():
    m={};n={}
    for (c,k),(ident,series,label,unit,status) in CONFIG.items():
        dates=[f"{2024+i//12}-{i%12+1:02d}"+("-01" if c=="CAD" else "") for i in range(34)]
        values=[1000+i for i in range(34)]
        n[c]={k:dict(label=label,dates=dates[:30],values=values[:30],last_date=dates[29],last_value=values[29]),"credit_dir":"IN AUMENTO"}
        m[c]=[dict(id=ident,label=label,source_file=ident.removesuffix("_value")+".csv",unit=unit,frequency="M",dates=dates,values=values,last_date=dates[-1],last_value=values[-1],current_vintage_provenance=dict(status=status,source_series_id=series,source_series_first_release_PIT_certified=False))]
    return m,n
def fetch(url):
    code="V41552801"
    return json.dumps({"seriesDetail":{code:{"label":"M2++ (gross) (Seasonally adjusted)","description":""}},"observations":[{"d":f"{2024+i//12}-{i%12+1:02d}-01",code:{"v":str(1000+i)}} for i in range(34)]}).encode()
class ParityTests(unittest.TestCase):
    def test_two_lanes_and_idempotence(self):
        m,n=fixture();old=copy.deepcopy(n);out,receipt=prepare(m,n,NOW,fetch)
        self.assertEqual([x["status"] for x in receipt["series"]],["READY","READY"])
        self.assertEqual(n,old)
        self.assertEqual(out["JPY"]["credit_dir"],n["JPY"]["credit_dir"])
        self.assertEqual([x["status"] for x in prepare(m,out,NOW,fetch)[1]["series"]],["NO_CHANGE","NO_CHANGE"])
    def test_reject_mismatch_and_source_vintage(self):
        m,n=fixture();m["JPY"][0]["values"][2]+=2;m["CAD"][0]["values"][2]+=2
        out,r=prepare(m,n,NOW,fetch)
        self.assertEqual([x["status"] for x in r["series"]],["WITHHELD","WITHHELD"])
        self.assertEqual(out,n)
    def test_money_revisions_use_full_official_window(self):
        m,n=fixture();n["CAD"]["money"]["values"][0]-=2
        out,r=prepare(m,n,NOW,fetch)
        self.assertEqual(out["CAD"]["money"]["values"][0],1000)
        self.assertEqual(r["series"][1]["revised_months"],1)
if __name__=="__main__":unittest.main()
