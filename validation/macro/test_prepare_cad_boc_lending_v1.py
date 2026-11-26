import unittest,json
from datetime import datetime,timezone
from validation.macro.prepare_cad_boc_lending_v1 import CONFIG,prepare_row,prepare
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
def fixture(ident,wrong=False,gap=False,offset=0):
    code,title,unit=CONFIG[ident]
    dates=[f"{2024+i//12}-{i%12+1:02d}-01" for i in range(34)]
    vs=[(4 if unit=="Percent per annum" else 900000)+i*.01 for i in range(34)]
    row=dict(id=ident,source_file=ident.removesuffix("_value")+".csv",unit=unit,frequency="M",dates=dates[:-1],values=vs[:-1],last_date=dates[-2],last_value=vs[-2])
    data={"seriesDetail":{code:{"label":("wrong" if wrong else title+" total"),"description":""}},"observations":[{"d":d,code:{"v":str(v+offset)}} for i,(d,v) in enumerate(zip(dates,vs)) if not gap or i!=10]}
    return row,lambda url:json.dumps(data).encode()
class Tests(unittest.TestCase):
    def test_each_source(self):
        for ident in CONFIG:
            row,fetch=fixture(ident)
            self.assertEqual(prepare_row(row,ident,NOW,fetch)["status"],"READY")
            self.assertEqual(prepare_row(row,ident,NOW,fetch)["status"],"NO_CHANGE")
    def test_fail_closed(self):
        for ident in CONFIG:
            for kw in ({"wrong":True},{"gap":True},{"offset":100000}):
                row,fetch=fixture(ident,**kw)
                with self.assertRaises(ValueError):prepare_row(row,ident,NOW,fetch)
if __name__=="__main__":unittest.main()
