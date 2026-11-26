import json,unittest
from datetime import datetime,timezone
from validation.macro.prepare_chf_seco_index_v1 import ID,META,CSV,prepare_row,prepare
NOW=datetime(2026,11,26,tzinfo=timezone.utc)
def fixture(wrong=False,ambiguous=False,gap=False):
    ds=[f"{2018+i//4}-{1+3*(i%4):02d}-01" for i in range(36)]
    vals=[-30+i*.1 for i in range(36)];sd=[1+i*.01 for i in range(36)]
    labels=[d+"T00:00:00Z" for d in ds[:-1]]
    row=dict(id=ID,unit="",frequency="",source_file="CH_SECO_CONSUMER_SENTIMENT_LEAD_history.csv",dates=labels+labels,values=(vals[:-1] if ambiguous else sd[:-1])+vals[:-1],last_date=labels[-1],last_value=vals[-2])
    meta={"title":{"en":"Consumer sentiment index"},"dim_order":["type","structure","seas_adj"],"units":{"type":{"index":{"en":"Index"},"sd":{"en":"Standard deviation"}}},"labels":{"structure":{"ks_i63_index_q":{"en":"6.3 Consumer sentiment index"}},"seas_adj":{"csa":{"en":"wrong" if wrong else "Seasonally and calendar adjusted"}}}}
    raw="structure,type,seas_adj,date,value\n"+"\n".join(f"ks_i63_index_q,{k},{a},{d},{v}" for k,a,vs in (("index","csa",vals),("sd","na",sd)) for i,(d,v) in enumerate(zip(ds,vs)) if not gap or i!=10)
    return row,lambda u:((json.dumps(meta) if u==META else raw).encode(),u)
class Tests(unittest.TestCase):
    def test_legacy_repair_idempotent(self):
        row,fetch=fixture()
        self.assertEqual(prepare_row(row,NOW,fetch)["status"],"READY")
        self.assertEqual(row["last_date"],"2026-10-01T00:00:00Z")
        self.assertEqual(len(row["dates"]),36)
        self.assertEqual(prepare_row(row,NOW,fetch)["status"],"NO_CHANGE")
    def test_bad_metadata_ambiguous_and_gap(self):
        for kwargs in ({"wrong":True},{"ambiguous":True},{"gap":True}):
            row,fetch=fixture(**kwargs);original={"CHF":[row]}
            out,r=prepare(original,now=NOW,fetcher=fetch)
            self.assertEqual(out,original);self.assertEqual(r["series"][0]["status"],"WITHHELD")
if __name__=="__main__":unittest.main()
