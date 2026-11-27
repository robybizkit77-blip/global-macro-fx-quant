import copy,unittest,calendar
from datetime import datetime,timezone,date,timedelta
from validation.macro.prepare_g8_native_liquidity_parity_v1 import CONFIG,prepare,load_us_m2_full
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
def fixture():
    m={};n={};feeds={}
    for (c,role),(ident,series,label,unit,f,status) in CONFIG.items():
        if f=="W":ds=[(date(2025,1,1)+timedelta(days=i*7)).isoformat() for i in range(60)]
        elif c=="AUD":ds=[f"{calendar.monthrange(2021+i//12,i%12+1)[1]:02d}/{i%12+1:02d}/{2021+i//12}" for i in range(60)]
        else:ds=[f"{2021+i//12}-{i%12+1:02d}"+("-01" if c=="CAD" else "") for i in range(60)]
        vs=[10000+i*10 for i in range(60)]
        def row(a,b):
            d=ds[a:b];v=vs[a:b];return dict(label=label,dates=d,values=v,last_date=d[-1],last_value=v[-1])
        n.setdefault(c,{})[role]=row(0,55)
        m.setdefault(c,[]).append(dict(row(10,60),id=ident,source_file=ident.removesuffix("_value")+".csv",unit=unit,frequency=f,current_vintage_provenance=dict(status=status,source_series_id=series,source_series_first_release_PIT_certified=False)))
        feeds[ident]=row(0,60)
    def load(c,ident,row,now):return dict(row,**feeds[ident])
    return m,n,load
class Tests(unittest.TestCase):
    def test_m2_full_window_before_2019(self):
        ds=[f"{2016+i//12}-{i%12+1:02d}" for i in range(130)]
        vs=[12000+i for i in range(len(ds))]
        row=dict(dates=ds[:128],values=vs[:128],last_date=ds[127],last_value=vs[127])
        def fetch(url):
            if "/series/" in url:return b"<html><title>M2 (M2SL)</title><body>Units: Billions of Dollars, Seasonally Adjusted Frequency: Monthly</body></html>",url
            return ("observation_date,M2SL\n"+"\n".join(f"{d}-01,{v}" for d,v in zip(ds,vs))).encode(),url
        result=load_us_m2_full(row,NOW,fetch)
        self.assertEqual(result["dates"][0],"2016-01")
        self.assertEqual(result["last_date"],"2026-10")
        self.assertEqual(len(result["dates"]),130)

    def test_six_full_windows_and_idempotence(self):
        m,n,f=fixture();old=copy.deepcopy(n);out,r=prepare(m,n,NOW,f)
        self.assertEqual([x["status"] for x in r["series"]],["READY"]*6)
        self.assertEqual(n,old)
        self.assertEqual([x["status"] for x in prepare(m,out,NOW,f)[1]["series"]],["NO_CHANGE"]*6)
    def test_reject_vintage_and_keep_other_lanes(self):
        m,n,f=fixture();m["USD"][0]["values"][0]+=1
        out,r=prepare(m,n,NOW,f)
        self.assertEqual([x["status"] for x in r["series"]],["WITHHELD"]+["READY"]*5)
        self.assertEqual(out["USD"],n["USD"])
if __name__=="__main__":unittest.main()
