"""Offline contracts for the optional G8 semaforo source recovery."""
import csv
from datetime import date
from io import StringIO
import json
import io
from zipfile import ZipFile
import unittest
from validation.macro import collect_g8_semaphore_gaps_v1 as mod

NOW=date(2026,11,23)

def fixture(key,frequency="M",end=(2026,9),n=24):
    end_idx=end[0]*(12 if frequency=="M" else 4)+end[1]-1
    out=StringIO()
    writer=csv.writer(out)
    writer.writerow(["observation_date",key])
    for i in range(n):
        t=end_idx-(n-i-1)
        year,q=divmod(t,12 if frequency=="M" else 4)
        if frequency=="M":stamp=f"{year:04d}-{q+1:02d}-01"
        else:stamp=f"{year:04d}-{q*3+1:02d}-01"
        writer.writerow([stamp,100+i*.5])
    return out.getvalue().encode()

class G8SemaphoreSources(unittest.TestCase):
    def test_registry_targets_exactly_eight_gaps(self):
        self.assertEqual(len(mod.REGISTRY),8)
        self.assertEqual(len({(s["ccy"],s["area"]) for s in mod.REGISTRY}),8)
        self.assertTrue(all(s["source_page"].startswith("https://") for s in mod.REGISTRY))
        self.assertTrue(all(s["method"] in {"fred","eurostat","statcan"} for s in mod.REGISTRY))

    def test_fred_parses_fixed_series_header_and_periods(self):
        raw=fixture("PRMNTO01AUQ657S","Q",(2026,2))
        obs=mod.parse_fred(raw,"PRMNTO01AUQ657S","Q",NOW)
        self.assertEqual(obs[-1][0],"2026-Q2")
        item,status=mod.candidate(next(s for s in mod.REGISTRY if s["ccy"]=="AUD"),obs,NOW)
        self.assertEqual(status["status"],"READY_DESCRIPTIVE_REVISED")
        self.assertEqual(item["metric_kind"],"points")
        self.assertEqual(item["dates"],["2026-Q1","2026-Q2"])
        self.assertFalse("first_seen_at" in item)

    def test_stale_official_feed_does_not_generate_signal(self):
        spec=next(s for s in mod.REGISTRY if s["ccy"]=="JPY")
        rows=mod.parse_fred(fixture(spec["key"],"M",(2023,11)),spec["key"],"M",NOW)
        item,status=mod.candidate(spec,rows,NOW)
        self.assertIsNone(item)
        self.assertEqual(status["status"],"WITHHELD_STALE")

    def test_bad_identity_gap_and_future_are_blocked(self):
        key="PRMNTO01NZQ657S"
        with self.assertRaisesRegex(ValueError,"source ID"):
            mod.parse_fred(fixture("OTHER","Q",(2026,2)),key,"Q",NOW)
        rows=mod.parse_fred(fixture(key,"Q",(2026,2)),key,"Q",NOW)
        with self.assertRaisesRegex(ValueError,"quarterly gap"):
            mod.contiguous_last_two(rows[:-2]+[rows[-1]],"Q")
        future=mod.parse_fred(fixture(key,"Q",(2027,1)),key,"Q",NOW)
        self.assertTrue(all(mod.period_end(x[0])<=NOW for x in future))
        # A malformed series cannot become a fresh input simply by adding a date.
        with self.assertRaises((ValueError,OverflowError)):
            mod.parse_fred(b"DATE,PRMNTO01NZQ657S\nbogus,100",key,"Q",NOW)

    def test_eurostat_unique_json_stat_cell(self):
        ids=["freq","geo","indic_bt","cpa2_1","s_adj","unit","time"]
        allowed=["M","EA21","BPRM_DW","CPA_F41001","SCA","I21"]
        time=[f"2025-{m:02d}" for m in range(1,13)]+[f"2026-{m:02d}" for m in range(1,10)]
        dims={key:{"category":{"index":{value:0}}} for key,value in zip(ids,allowed)}
        dims["time"]={"category":{"index":{name:i for i,name in enumerate(time)}}}
        raw=json.dumps({"class":"dataset","id":ids,"size":[1]*6+[len(time)],
                        "dimension":dims,"value":{str(i):100+i for i in range(len(time))}}).encode()
        obs=mod.parse_eurostat(raw,NOW)
        self.assertEqual(obs[-1],("2026-09",120.0))
        dims["unit"]["category"]["index"]={"EUR":0}
        with self.assertRaisesRegex(ValueError,"missing/ambiguous"):
            mod.parse_eurostat(json.dumps({"class":"dataset","id":ids,"size":[1]*6+[len(time)],
              "dimension":dims,"value":{str(i):100+i for i in range(len(time))}}).encode(),NOW)

    def test_statcan_exact_manufacturing_sa_total(self):
        bio=io.BytesIO()
        header=["REF_DATE","GEO","Principal statistics","Seasonal adjustment",
                "North American Industry Classification System (NAICS)","UOM",
                "SCALAR_FACTOR","VALUE"]
        rows=[]
        for mm in range(1,13):
            rows.append([f"2025-{mm:02d}","Canada",
                "Sales of goods manufactured (shipments)","Seasonally adjusted",
                "Manufacturing [31-33]","Dollars","thousands",100000+mm])
        for mm in range(1,10):
            rows.append([f"2026-{mm:02d}","Canada",
                "Sales of goods manufactured (shipments)","Seasonally adjusted",
                "Manufacturing [31-33]","Dollars","thousands",102000+mm])
        rows.append(["2026-09","Canada",
          "Sales of goods manufactured (shipments)","Unadjusted",
          "Manufacturing [31-33]","Dollars","thousands",999999999])
        with ZipFile(bio,"w") as z:
            buf=StringIO();writer=csv.writer(buf);writer.writerow(header);writer.writerows(rows)
            z.writestr("16100047.csv",buf.getvalue())
        observations=mod.parse_statcan(bio.getvalue(),NOW)
        self.assertEqual(observations[-1],("2026-09",102009))
        self.assertEqual(len(observations),21)
        spec=next(x for x in mod.REGISTRY if x["ccy"]=="CAD")
        item,stat=mod.candidate(spec,observations,NOW)
        self.assertEqual(stat["status"],"READY_DESCRIPTIVE_REVISED")
        self.assertEqual(item["dates"],["2026-08","2026-09"])

    def test_collect_transparently_withholds_failed_sources(self):
        def fail(_):raise OSError("issuer blocked")
        out=mod.collect(NOW,fetcher=fail)
        self.assertEqual(len(out["series"]),0)
        self.assertEqual(len(out["audit"]),8)
        self.assertTrue(all(x["status"]=="WITHHELD_FETCH_OR_VALIDATION" for x in out["audit"].values()))
        self.assertNotIn("status","PASS")

if __name__=="__main__":unittest.main()
