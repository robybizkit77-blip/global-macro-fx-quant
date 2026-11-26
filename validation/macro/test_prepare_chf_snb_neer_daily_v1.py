import json,unittest
from datetime import datetime,timezone,timedelta
from validation.macro.prepare_chf_snb_neer_daily_v1 import CONFIG,prepare_row
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
def fixture():
    dates=[(NOW.date()-timedelta(days=90-i)).isoformat() for i in range(45)]
    vs=[200+i/100 for i in range(45)]
    ident,code=next(iter(CONFIG.items()))
    row=dict(id=ident,source_file=ident.removesuffix("_value")+".csv",frequency="D",unit="Index, Dec 2000=100",dates=dates[:-2],values=vs[:-2],last_date=dates[-3],last_value=vs[-3])
    source=dict(timeseries=[dict(metadata=dict(key=code,frequency="P1D_L",unit="December 2000 = 100",scale=""),values=[dict(date=d,value=v) for d,v in zip(dates,vs)])])
    return row,source
class Tests(unittest.TestCase):
    def test_refresh_idempotent(self):
        r,s=fixture();fetch=lambda _:json.dumps(s).encode()
        self.assertEqual(prepare_row(r,NOW,fetch)["status"],"READY")
        self.assertEqual(prepare_row(r,NOW,fetch)["status"],"NO_CHANGE")
    def test_wrong_series_rejected(self):
        r,s=fixture();s["timeseries"][0]["metadata"]["key"]="other"
        with self.assertRaises(ValueError):prepare_row(r,NOW,lambda _:json.dumps(s).encode())
    def test_wrong_history_rejected(self):
        r,s=fixture();s["timeseries"][0]["values"][0]["value"]+=1
        with self.assertRaises(ValueError):prepare_row(r,NOW,lambda _:json.dumps(s).encode())
if __name__=="__main__":unittest.main()
