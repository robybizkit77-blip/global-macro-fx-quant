import copy,unittest
from datetime import datetime,timezone,date,timedelta
from validation.macro.prepare_eur_native_liquidity_parity_v1 import CONFIG,prepare
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
def fixture():
    macro={"EUR":[]};native={"EUR":{"current_note":"old narrative"},"USD":{}}
    feeds={}
    for role,(ident,key,label) in CONFIG.items():
        daily=role=="liquidity"
        ds=[(date(2026,8,1)+timedelta(days=i)).isoformat() if daily else f"{2021+i//12}-{i%12+1:02d}" for i in range(110 if daily else 70)]
        vs=[(2100000 if daily else 17500000 if role=="money" else 5400000)+100*i for i in range(len(ds))]
        def row(start,end,suffix):
            d=[x+suffix for x in ds[start:end]];v=vs[start:end]
            return dict(label=label,dates=d,values=v,last_date=d[-1],last_value=v[-1])
        native["EUR"][role]=row(0,len(ds)-5,"T00:00:00.000Z" if daily else "")
        macro["EUR"].append(dict(row(10,len(ds),"T00:00:00Z" if daily else ""),id=ident,source_file=ident.removesuffix("_value")+".csv",current_vintage_provenance=dict(status="ECB_CURRENT_REVISED_HISTORY_NOT_PIT",source_series_id=key,source_series_first_release_PIT_certified=False)))
        feeds[key]="KEY,TIME_PERIOD,OBS_VALUE,UNIT_MULT\n"+"\n".join(f"{key},{d},{v},6" for d,v in zip(ds,vs))
    def fetch(url):return next(v for k,v in feeds.items() if k.split(".",1)[1] in url)
    return macro,native,fetch
class Tests(unittest.TestCase):
    def test_three_full_histories_and_idempotence(self):
        m,n,f=fixture();old=copy.deepcopy(n);out,r=prepare(m,n,NOW,f)
        self.assertEqual([x["status"] for x in r["series"]],["READY"]*3)
        self.assertEqual(n,old)
        self.assertEqual(out["EUR"]["current_note"],n["EUR"]["current_note"])
        self.assertEqual([x["status"] for x in prepare(m,out,NOW,f)[1]["series"]],["NO_CHANGE"]*3)
    def test_mismatch_and_other_lanes_continue(self):
        m,n,f=fixture();m["EUR"][0]["values"][0]+=1
        out,r=prepare(m,n,NOW,f)
        self.assertEqual([x["status"] for x in r["series"]],["WITHHELD","READY","READY"])
        self.assertEqual(out["EUR"]["liquidity"],n["EUR"]["liquidity"])
if __name__=="__main__":unittest.main()
