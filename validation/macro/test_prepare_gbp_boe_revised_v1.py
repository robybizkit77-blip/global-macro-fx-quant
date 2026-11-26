import calendar,unittest
from datetime import date,datetime,timezone,timedelta
from validation.macro.prepare_gbp_boe_revised_v1 import CONFIG,prepare_row,prepare
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
def fixture(ident):
    code,unit,f,lo,hi,_,_,fmt=CONFIG[ident]
    if f=="W":ds=[date(2025,1,1)+timedelta(weeks=i) for i in range(80)]
    else:ds=[date(2022+i//12,i%12+1,calendar.monthrange(2022+i//12,i%12+1)[1]) for i in range(58)]
    vs=[(lo+hi)/2+i*.0001 for i in range(len(ds))]
    d=[x.strftime(fmt) for x in ds[:-3]];v=vs[:-3]
    row=dict(id=ident,unit=unit,frequency=f,source_file=ident.removesuffix("_value")+".csv",dates=d,values=v,last_date=d[-1],last_value=v[-1])
    raw=("DATE,"+code+"\n"+"\n".join(f"{x.strftime('%d %b %Y')},{y}" for x,y in zip(ds,vs))).encode()
    return row,raw
class Tests(unittest.TestCase):
    def test_five_sources_and_idempotence(self):
        for ident in CONFIG:
            row,raw=fixture(ident)
            self.assertEqual(prepare_row(row,ident,NOW,lambda u:raw)["status"],"READY")
            self.assertEqual(prepare_row(row,ident,NOW,lambda u:raw)["status"],"NO_CHANGE")
    def test_bad_source_keeps_prior(self):
        ids=list(CONFIG);rows=[fixture(i)[0] for i in ids]
        def fetch(url):
            i=next(i for i in ids if CONFIG[i][0] in url)
            return b"HTML" if i==ids[0] else fixture(i)[1]
        out,r=prepare({"GBP":rows},now=NOW,fetcher=fetch)
        self.assertEqual([x["status"] for x in r["series"]],["WITHHELD"]+["READY"]*(len(ids)-1))
        self.assertEqual(out["GBP"][0],rows[0])
if __name__=="__main__":unittest.main()
