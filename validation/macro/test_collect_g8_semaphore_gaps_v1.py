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
        self.assertEqual(len(mod.REGISTRY),42)
        self.assertEqual(len({(s["ccy"],s["area"]) for s in mod.REGISTRY}),42)
        self.assertTrue(all(s["source_page"].startswith("https://") for s in mod.REGISTRY))
        self.assertTrue(all(s["method"] in {"fred","eurostat","eurostat_services","eurostat_industry","eurostat_esi","eurostat_retail","eurostat_house_price","statcan","ons","ons_industry","boe_mortgage","statsnz_house","statcan_services","biznz","abs_services","abs_demand","rba_credit","statcan_detail","boj_credit","rbnz_credit"} for s in mod.REGISTRY))

    def test_wave3_exact_id_frequency_and_direction(self):
        expected={"GBP_leading":"GBRLOLITOAASTSAM","JPY_jobs":"LRUNTTTTJPM156S","JPY_industry":"JPNPRMNTO01GPSAM","JPY_demand":"SLRTTO01JPQ657S","CHF_house":"QCHR368BIS","CHF_industry":"PRMNTO01CHQ657S","CHF_demand":"SLRTTO01CHQ657S","AUD_jobs":"LRUNTTTTAUM156S","AUD_leading":"AUSLOLITOAASTSAM","NZD_demand":"SLRTTO01NZQ657S"}
        for code,key in expected.items():
            ccy,area=code.split("_")
            spec=next(s for s in mod.REGISTRY if s["ccy"]==ccy and s["area"]==area)
            self.assertEqual(spec["key"],key)
            self.assertEqual(spec["source_page"],mod.FRED.replace("/graph/fredgraph.csv?id=","/series/")+key)
            self.assertEqual(spec.get("up_good",True),area!="jobs")
            freq=spec["frequency"]
            rows=mod.parse_fred(fixture(key,freq,(2026,9 if freq=="M" else 2)),key,freq,NOW)
            item,status=mod.candidate(spec,rows,NOW)
            self.assertEqual(status["status"],"READY_DESCRIPTIVE_REVISED")
            self.assertEqual(item["up_good"],area!="jobs")

    def test_boj_credit_exact_yoy_column(self):
        raw="<table><tr><td>Name</td><td>Other</td><td>Loans and Discounts/Total of major and regional banks/percent changes in average amounts outstanding from previous year</td></tr><tr><td>Series code</td><td>OTHER</td><td>MD13'FAAPOBAL1@</td></tr><tr><td>Unit</td><td>yen</td><td>%</td></tr>"
        for y in (2025,2026):
            for m in range(1,11):
                raw+=f"<tr><td>{y}/{m:02d}</td><td>9999</td><td>{m/10}</td></tr>"
        raw+="</table>"
        self.assertEqual(mod.parse_boj_credit(raw.encode(),NOW)[-2:],[("2026-09",.9),("2026-10",1.)])
        with self.assertRaises(ValueError):
            mod.parse_boj_credit(raw.replace("MD13'FAAPOBAL1@","WRONG").encode(),NOW)

    def test_rbnz_credit_break_adjusted_business_row(self):
        raw="""<h1>Sector lending (C5)</h1><p>Annual growth rates have been break-adjusted</p><table>
        <tr><th></th><th>Sept 2024</th><th>Sept 2025</th><th>May 2026</th><th>Jun 2026</th><th>Jul 2026</th><th>Aug 2026</th><th>Sept 2026</th></tr>
        <tr><th>Business ($m)</th></tr><tr><td>Total</td><td>100</td></tr>
        <tr><th>Annual growth rate (%)</th></tr><tr><td>Business [3]</td><td>2</td><td>3.7</td><td>4.9</td><td>4.6</td><td>4.4</td><td>4.1</td><td>5.3</td></tr></table>"""
        self.assertEqual(mod.parse_rbnz_credit(raw.encode(),NOW)[-2:],[("2026-08",4.1),("2026-09",5.3)])
        with self.assertRaises(ValueError):
            mod.parse_rbnz_credit(raw.replace("break-adjusted","unadjusted").encode(),NOW)

    def test_fred_parses_fixed_series_header_and_periods(self):
        raw=fixture("PRMNTO01AUQ657S","Q",(2026,2))
        obs=mod.parse_fred(raw,"PRMNTO01AUQ657S","Q",NOW)
        self.assertEqual(obs[-1][0],"2026-Q2")
        item,status=mod.candidate(next(s for s in mod.REGISTRY if s["ccy"]=="AUD" and s["area"]=="industry"),obs,NOW)
        self.assertEqual(status["status"],"READY_DESCRIPTIVE_REVISED")
        self.assertEqual(item["metric_kind"],"points")
        self.assertEqual(item["dates"],["2026-Q1","2026-Q2"])
        self.assertFalse("first_seen_at" in item)

    def test_stale_official_feed_does_not_generate_signal(self):
        spec=next(s for s in mod.REGISTRY if s["ccy"]=="JPY" and s["area"]=="house")
        rows=mod.parse_fred(fixture(spec["key"],"Q",(2023,4)),spec["key"],"Q",NOW)
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
        allowed=["M","EA21","BPRM_DW","CPA_F41001_X_410014","SCA","I21"]
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

    def test_eurostat_services_EA21_survey_exact_selection_and_periods(self):
        dates=[f"2025-{i:02d}" for i in range(1,13)]+[f"2026-{i:02d}" for i in range(1,11)]
        ids=["freq","s_adj","indic","geo","time"]
        dimensions={
           "freq":{"category":{"index":{"M":0}}},
           "s_adj":{"category":{"index":{"SA":0}}},
           "indic":{"category":{"index":{"BS-SCI-BAL":0}}},
           "geo":{"category":{"index":{"EA21":0}}},
           "time":{"category":{"index":{day:i for i,day in enumerate(dates)}}}
        }
        payload={"class":"dataset","id":ids,"size":[1,1,1,1,len(dates)],
                 "dimension":dimensions,
                 "value":{str(i):i*.4-5 for i in range(len(dates))}}
        raw=json.dumps(payload).encode()
        obs=mod.parse_eurostat_services(raw,date(2026,11,24))
        self.assertEqual(obs[-2:],[("2026-09",3.0),("2026-10",3.4000000000000004)])
        spec=next(s for s in mod.REGISTRY if s["ccy"]=="EUR" and s["area"]=="services")
        item,status=mod.candidate(spec,obs,date(2026,11,24))
        self.assertEqual(status["status"],"READY_DESCRIPTIVE_REVISED")
        self.assertEqual(item["source_series_id"],"TEIBS020_BS-SCI-BAL_SA_EA21")
        self.assertEqual(item["dates"],["2026-09","2026-10"])
        dimensions["geo"]["category"]["index"]={"EA20":0}
        with self.assertRaisesRegex(ValueError,"selector changed"):
            mod.parse_eurostat_services(json.dumps(payload).encode(),date(2026,11,24))
        dimensions["geo"]["category"]["index"]={"EA21":0}
        dimensions["indic"]["category"]["index"]={"BS-SCI-BAL":0,"BS-ICI-BAL":1}
        with self.assertRaisesRegex(ValueError,"selector changed"):
            mod.parse_eurostat_services(json.dumps(payload).encode(),date(2026,11,24))

    def test_eurostat_multiple_official_domains_exact_semantics(self):
        for method in ("eurostat_industry","eurostat_esi","eurostat_retail"):
            dataset, selectors=mod.EUROSTAT_EXTRA[method]
            ids=list(selectors)+["time"]
            times=[f"2025-{m:02d}" for m in range(1,13)]+[f"2026-{m:02d}" for m in range(1,11)]
            dims={k:{"category":{"index":{v:0}}} for k,v in selectors.items()}
            dims["time"]={"category":{"index":{t:i for i,t in enumerate(times)}}}
            values={str(i):105+i for i in range(len(times))}
            payload={"class":"dataset","id":ids,"size":[1]*len(selectors)+[len(times)],
                     "dimension":dims,"value":values}
            observations=mod.parse_euro_extra(json.dumps(payload).encode(),NOW,method)
            self.assertEqual(observations[-2:],[("2026-09",125),("2026-10",126)])
            # Source dimensions are required to be *one exact selection*.
            k=next(k for k in selectors if k!="freq")
            dims[k]["category"]["index"]={"wrong":0}
            with self.assertRaisesRegex(ValueError,"selector changed"):
                mod.parse_euro_extra(json.dumps(payload).encode(),NOW,method)
        self.assertTrue(mod.euro_extra_url("eurostat_industry").startswith("https://ec.europa.eu/eurostat/"))

    def test_eurostat_house_price_quarterly_exact_annual_rate(self):
        method="eurostat_house_price"
        dataset, selectors=mod.EUROSTAT_EXTRA[method]
        self.assertEqual(dataset,"prc_hpi_q")
        self.assertEqual(selectors,{"freq":"Q","geo":"EA21","purchase":"TOTAL","unit":"RCH_A"})
        times=[f"{y}-Q{q}" for y in range(2020,2027) for q in range(1,5)]
        ids=list(selectors)+["time"]
        dims={k:{"category":{"index":{v:0}}} for k,v in selectors.items()}
        dims["time"]={"category":{"index":{t:i for i,t in enumerate(times)}}}
        payload={"class":"dataset","id":ids,"size":[1]*len(selectors)+[len(times)],
                 "dimension":dims,"value":{str(i):i/10 for i in range(len(times))}}
        obs=mod.parse_euro_extra(json.dumps(payload).encode(),NOW,method)
        self.assertEqual(obs[-1][0],"2026-Q3")
        spec=next(x for x in mod.REGISTRY if x["ccy"]=="EUR" and x["area"]=="house")
        self.assertEqual(spec["kind"],"points")
        self.assertEqual(spec["frequency"],"Q")
        dims["unit"]["category"]["index"]={"I15_Q":0}
        with self.assertRaisesRegex(ValueError,"selector changed"):
            mod.parse_euro_extra(json.dumps(payload).encode(),NOW,method)

    def test_new_fred_registry_has_no_implicit_sign_error(self):
        expected={"house":"PERMIT","industry":"INDPRO","leading":"UMCSENT",
                  "demand":"PCEC96","credit":"DRTSCILM"}
        records={x["area"]:x for x in mod.REGISTRY if x["ccy"]=="USD" and x["area"] in expected}
        self.assertEqual({a:r["key"] for a,r in records.items()},expected)
        self.assertFalse(records["credit"]["up_good"],"Tightening must be adverse when rising")
        for a,r in records.items():
            self.assertTrue(r["source_page"].endswith("/"+r["key"]))
            self.assertGreaterEqual(r["max_age_days"],100)

    def test_stats_nz_new_dwellings_sa_series_and_release_identity(self):
        html='<html><h2>New dwellings consented, monthly</h2><table><tr><th>Category</th><th>Actual</th><th>Seasonally adjusted</th><th>Trend</th></tr>'
        for i in range(1,11):
            html+=f'<tr><td>2026-{i:02d}-01</td><td>3500</td><td>{3000+i*20}</td><td>3100</td></tr>'
        html+='</table></html>'
        out=mod.parse_statsnz_house(html.encode(),date(2026,11,24))
        self.assertEqual(out[-2:],[("2026-09",3180.0),("2026-10",3200.0)])
        self.assertTrue(mod.statsnz_house_url(date(2026,11,24),2).endswith("september-2026/"))
        with self.assertRaisesRegex(ValueError,"identity"):
            mod.parse_statsnz_house(html.replace("New dwellings consented","Other").encode(),NOW)
        with self.assertRaisesRegex(ValueError,"identity"):
            mod.parse_statsnz_house(html.replace("Seasonally adjusted","not adjusted").encode(),NOW)

    def test_boe_mortgage_exact_official_identifier(self):
        html="<html><h1>Monthly number of total sterling approvals for house purchase</h1><p>LPMVTVX</p>"
        html+="<table><tr><th>Date</th><th>LPMVTVX</th></tr>"
        for year in (2025,2026):
            for month in range(1,13 if year==2025 else 10):
                name=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][month-1]
                html+=f"<tr><td>28 {name} {str(year)[-2:]}</td><td>{55000+month*120}</td></tr>"
        html+="</table></html>"
        out=mod.parse_boe_mortgage(html.encode(),NOW)
        self.assertEqual(out[-1],("2026-09",56080))
        with self.assertRaisesRegex(ValueError,"identity"):
            mod.parse_boe_mortgage(html.replace("LPMVTVX","WRONG").encode(),NOW)
        self.assertIn("SeriesCodes=LPMVTVX",mod.boe_mortgage_url(NOW))

    def test_ons_industry_k222_monthly_only(self):
        html='<html><h1>IOP: B-E: PRODUCTION: CVMSA</h1><p>Series ID: K222</p><table>'
        for year in (2025,2026):
            for month in range(1,13 if year==2025 else 10):
                key=["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"][month-1]
                html+=f"<tr><td>{year} {key}</td><td>{100+month/10:.1f}</td></tr>"
        html+='</table></html>'
        out=mod.parse_ons_industry(html.encode(),NOW)
        self.assertEqual(out[-1],("2026-09",100.9))
        with self.assertRaisesRegex(ValueError,"identity"):
            mod.parse_ons_industry(html.replace("K222","NOTK222").encode(),NOW)

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
        spec=next(x for x in mod.REGISTRY if x["ccy"]=="CAD" and x["area"]=="industry")
        item,stat=mod.candidate(spec,observations,NOW)
        self.assertEqual(stat["status"],"READY_DESCRIPTIVE_REVISED")
        self.assertEqual(item["dates"],["2026-08","2026-09"])

    def test_ons_services_exact_index_months_and_identity(self):
        html='<html><body><h1>IoS: Services: Index-1dp</h1><p>Series ID: S2KU</p><table>'
        for year in (2025,2026):
            for month in range(1,13 if year==2025 else 10):
                txt=['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'][month-1]
                html+=f'<tr><td>{year} {txt}</td><td>{100+month*0.2:.1f}</td></tr>'
        html+='</table></body></html>'
        obs=mod.parse_ons_services(html.encode(),NOW)
        self.assertEqual(obs[-1],("2026-09",101.8))
        with self.assertRaisesRegex(ValueError,"ONS total services"):
            mod.parse_ons_services(html.replace("S2KU","OTHER").encode(),NOW)

    def test_statcan_services_real_gdp_explicit_aggregate(self):
        bio=io.BytesIO()
        header=["REF_DATE","GEO","North American Industry Classification System (NAICS)",
                "Prices","Seasonal adjustment","VALUE"]
        rows=[]
        for year in (2025,2026):
            for month in range(1,13 if year==2025 else 10):
                rows.append([f"{year}-{month:02d}","Canada",
                 "Services-producing industries [T003]","Chained (2017) dollars",
                 "Seasonally adjusted at annual rates",round(1_760_000+month*100+year-2025,2)])
        rows.append(["2026-09","Canada","Goods-producing industries [T002]",
          "Chained (2017) dollars","Seasonally adjusted at annual rates",999999999])
        with ZipFile(bio,"w") as z:
            b=StringIO();w=csv.writer(b);w.writerow(header);w.writerows(rows)
            z.writestr("36100434.csv",b.getvalue())
        obs=mod.parse_statcan_services(bio.getvalue(),NOW)
        self.assertEqual(len(obs),21)
        self.assertEqual(obs[-1][0],"2026-09")
        spec=next(x for x in mod.REGISTRY if x["ccy"]=="CAD" and x["area"]=="services")
        item,status=mod.candidate(spec,obs,NOW)
        self.assertEqual(status["status"],"READY_DESCRIPTIVE_REVISED")
        self.assertEqual(item["area"],"services")

    def test_businessnz_national_PSI_expansion_vs_momentum(self):
        fake="""<html><h1>Performance of Services Index</h1><h2>PSI Time Series Table</h2>
        <table><thead><tr><th>National Indicies</th><th>Aug 2026</th><th>Sep 2026</th><th>Oct 2026</th></tr></thead>
        <tbody><tr><th>BNZ – BusinessNZ PSI</th><td>51.0</td><td>50.9</td><td>51.7</td></tr>
        <tr><th>Activity/Sales</th><td>49.3</td><td>50.4</td><td>52.6</td></tr></tbody></table></html>"""
        obs=mod.parse_businessnz_psi(fake.encode(),date(2026,11,24))
        self.assertEqual(obs,[("2026-08",51),("2026-09",50.9),("2026-10",51.7)])
        spec=next(x for x in mod.REGISTRY if x["ccy"]=="NZD" and x["area"]=="services")
        item,status=mod.candidate(spec,obs,date(2026,11,24))
        self.assertEqual(status["status"],"READY_DESCRIPTIVE_REVISED")
        self.assertEqual(item["diffusion_threshold"],50)
        self.assertEqual(item["dates"],["2026-09","2026-10"])
        with self.assertRaisesRegex(ValueError,"source identity"):
            mod.parse_businessnz_psi(fake.replace("PSI Time Series Table","wrong table").encode(),NOW)
        with self.assertRaisesRegex(ValueError,"index"):
            mod.parse_businessnz_psi(fake.replace("51.7","127.0").encode(),date(2026,11,24))

    def test_services_proxies_require_fresh_quarterly_dates(self):
        for ccy in ("CHF",):
            spec=next(x for x in mod.REGISTRY if x["ccy"]==ccy and x["area"]=="services")
            self.assertEqual(spec["frequency"],"Q")
            self.assertIn("proxy",spec["name"])
            raw=fixture(spec["key"],"Q",(2026,2))
            obs=mod.parse_fred(raw,spec["key"],"Q",NOW)
            item,status=mod.candidate(spec,obs,NOW)
            self.assertEqual(status["status"],"READY_DESCRIPTIVE_REVISED")
            self.assertEqual(item["dates"],["2026-Q1","2026-Q2"])

    def test_abs_household_services_spending_nominal_monthly_proxy(self):
        title="Household spending on services, current price, seasonally adjusted estimate"
        html='<html><button aria-label="'+title+'.csv"></button><table><thead><tr><th>Month</th><th>Monthly (%)</th><th>Through the year (%)</th></tr></thead>'
        for year in (2025,2026):
            for month in range(1,13 if year==2025 else 11):
                name=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][month-1]
                value=-0.5 if year==2026 and month==9 else 1.1 if year==2026 and month==10 else 0.4
                html+=f'<tr><td>{name}-{year}</td><td>{value}</td><td>6.4</td></tr>'
        html+='</table></html>'
        obs=mod.parse_abs_services(html.encode(),date(2026,11,24))
        self.assertEqual(obs[-2:],[("2026-09",-0.5),("2026-10",1.1)])
        spec=next(x for x in mod.REGISTRY if x["ccy"]=="AUD" and x["area"]=="services")
        self.assertIn("proxy",spec["name"])
        self.assertIn("nominale",spec["name"])
        item,status=mod.candidate(spec,obs,date(2026,11,24))
        self.assertEqual(status["status"],"READY_DESCRIPTIVE_REVISED")
        self.assertEqual(item["metric_kind"],"points")
        self.assertEqual(item["dates"],["2026-09","2026-10"])
        with self.assertRaisesRegex(ValueError,"unique exact chart"):
            mod.parse_abs_services(html.replace(title,"Different chart").encode(),date(2026,11,24))

    def test_businessnz_manual_official_snapshot_is_dated_and_cannot_be_current_forever(self):
        spec=next(s for s in mod.REGISTRY if s["ccy"]=="NZD" and s["area"]=="services")
        item,status=mod.curated_official_businessnz(spec,date(2026,11,24))
        self.assertEqual(item["values"],[50.9,51.7])
        self.assertEqual(item["quality"],"SOURCE_VERIFIED_MANUAL_NONPIT")
        self.assertEqual(status["status"],"READY_MANUAL_VERIFIED_NOT_AUTOMATIC")
        self.assertEqual(item["source_page"],"https://businessnz.org.nz/psi/pre-election-drinks")
        self.assertIsNone(mod.curated_official_businessnz(spec,date(2027,4,1))[0])
        with self.assertRaisesRegex(ValueError,"verification time"):
            mod.curated_official_businessnz(spec,date(2026,11,23))

    def test_issuer_unavailable_keeps_only_expiring_verified_manual_snapshot(self):
        def fail(_):raise OSError("http 403 issuer blocked")
        out=mod.collect(date(2026,11,24),fetcher=fail)
        self.assertEqual(len(out["series"]),3)
        self.assertEqual({(x["ccy"],x["area"]) for x in out["series"]},
                         {("NZD","house"),("NZD","services"),("NZD","credit")})
        self.assertEqual(out["audit"]["NZD_house"]["status"],"READY_MANUAL_VERIFIED_NOT_AUTOMATIC")
        self.assertEqual(out["audit"]["NZD_house"]["automatic_fetch"],"BLOCKED_OR_UNVALIDATED")
        self.assertEqual(out["audit"]["NZD_services"]["status"],"READY_MANUAL_VERIFIED_NOT_AUTOMATIC")
        self.assertEqual(out["audit"]["NZD_services"]["automatic_fetch"],"BLOCKED_OR_UNVALIDATED")

    def test_rbnz_credit_snapshot_is_verified_and_expires(self):
        spec=next(s for s in mod.REGISTRY if s["ccy"]=="NZD" and s["area"]=="credit")
        item,st=mod.curated_rbnz_credit(spec,date(2026,11,24))
        self.assertEqual(item["values"],[4.1,5.3])
        self.assertEqual(st["status"],"READY_MANUAL_VERIFIED_NOT_AUTOMATIC")
        self.assertEqual(item["quality"],"SOURCE_VERIFIED_MANUAL_NONPIT")
        self.assertIsNone(mod.curated_rbnz_credit(spec,date(2026,12,8))[0])
        with self.assertRaises(ValueError):mod.curated_rbnz_credit(spec,NOW)

    def test_stats_nz_house_official_snapshot_expiry_and_provenance(self):
        spec=next(x for x in mod.REGISTRY if x["ccy"]=="NZD" and x["area"]=="house")
        item,status=mod.curated_statsnz_house(spec,date(2026,11,24))
        self.assertEqual(item["values"],[3495,3218])
        self.assertEqual(item["dates"],["2026-08","2026-09"])
        self.assertEqual(item["quality"],"SOURCE_VERIFIED_MANUAL_NONPIT")
        self.assertEqual(status["status"],"READY_MANUAL_VERIFIED_NOT_AUTOMATIC")
        self.assertEqual(item["source_page"],
         "https://www.stats.govt.nz/information-releases/building-consents-issued-september-2026/")
        self.assertIsNone(mod.curated_statsnz_house(spec,date(2027,4,1))[0])
        with self.assertRaisesRegex(ValueError,"impossible dates"):
            mod.curated_statsnz_house(spec,date(2026,11,23))

    def test_abs_nominal_total_demand_not_services_or_real_volumes(self):
        title="Household spending, current price, seasonally adjusted estimate"
        data='<html><button aria-label="'+title+'.csv"></button><table>'
        for yr in [2025,2026]:
            for m in range(1,13 if yr==2025 else 10):
                mon=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][m-1]
                data+=f"<tr><td>{mon}-{yr}</td><td>{m*.1:.1f}</td><td>3.5</td></tr>"
        data+='</table></html>'
        obs=mod.parse_abs_demand(data.encode(),date(2026,11,24))
        self.assertEqual(obs[-2:],[("2026-08",0.8),("2026-09",0.9)])
        with self.assertRaisesRegex(ValueError,"unique exact chart"):
            mod.parse_abs_services(data.encode(),date(2026,11,24))

    def test_rba_housing_business_credit_monthly_growth_not_stock(self):
        page=mod.rba_release_url(date(2026,11,24),2)
        self.assertEqual(page,"https://www.rba.gov.au/statistics/frequency/fin-agg/2026/fin-agg-0926.html")
        raw="""<html><title>Financial Aggregates September 2026</title>
        <p>Monthly and Year-ended changes</p><table>
        <tr><th>Category</th><th>Aug 26</th><th>Sep 26</th><th>Sep 25</th><th>Sep 26</th></tr>
        <tr><th>Total credit</th><td>0.6</td><td>0.6</td><td>7.2</td><td>8.4</td></tr>
        <tr><th>– Housing</th><td>0.4</td><td>0.4</td><td>6.3</td><td>7.0</td></tr>
        <tr><th>– Business</th><td>0.9</td><td>0.9</td><td>9.4</td><td>11.3</td></tr>
        </table></html>""".encode()
        for sector,pct in [("RBA_HOUSING_CREDIT_GROWTH_MM",.4),
                           ("RBA_BUSINESS_CREDIT_GROWTH_MM",.9)]:
            obs=mod.parse_rba_aggregates(raw,date(2026,11,24),sector,page)
            self.assertEqual(obs,[("2026-08",pct),("2026-09",pct)])
        with self.assertRaisesRegex(ValueError,"subcategory"):
            mod.parse_rba_aggregates(raw.replace(b"Business",b"Other"),date(2026,11,24),
             "RBA_BUSINESS_CREDIT_GROWTH_MM",page)

    def test_statcan_three_issuer_exact_selector_contracts(self):
        for key,payload in mod.STATCAN_DETAIL.items():
            dates=[f"2025-{m:02d}" for m in range(1,13)]+[f"2026-{m:02d}" for m in range(1,11)]
            header=["REF_DATE","GEO",payload["category"],payload["other"],
                    "UOM","SCALAR_FACTOR","VECTOR","VALUE"]
            rows=[[dt,"Canada",payload["value"],payload["selection"],
                   payload["unit"],payload["scale"],payload.get("vector","vTEST"),100+i] for i,dt in enumerate(dates)]
            rows.append(["2026-10","Canada",payload["value"],"Other category",
                         payload["unit"],payload["scale"],payload.get("vector","vTEST"),999999])
            bio=io.BytesIO()
            with ZipFile(bio,"w") as z:
                out=StringIO();writer=csv.writer(out);writer.writerow(header);writer.writerows(rows)
                z.writestr(payload["file"],out.getvalue())
            obs=mod.parse_statcan_detail(bio.getvalue(),date(2026,11,24),key)
            self.assertEqual(obs[-1],("2026-10",121.0))
            spec=next(x for x in mod.REGISTRY if x["key"]==key)
            item,st=mod.candidate(spec,obs,date(2026,11,24))
            self.assertEqual(st["status"],"READY_DESCRIPTIVE_REVISED")
            self.assertEqual(item["dates"],["2026-09","2026-10"])
            with self.assertRaisesRegex(ValueError,"Unknown StatCan"):
                mod.parse_statcan_detail(bio.getvalue(),date(2026,11,24),"WRONG")
            z2=io.BytesIO()
            with ZipFile(z2,"w") as z:
                out=StringIO();w=csv.writer(out);w.writerow(header)
                w.writerows([[d,"Canada",payload["value"],payload["selection"],
                           payload["unit"],"thousands",payload.get("vector","vTEST"),100+i] for i,d in enumerate(dates)])
                z.writestr(payload["file"],out.getvalue())
            with self.assertRaisesRegex(ValueError,"unit/scale"):
                mod.parse_statcan_detail(z2.getvalue(),date(2026,11,24),key)

    def test_collect_transparently_withholds_failed_sources(self):
        def fail(_):raise OSError("issuer blocked")
        out=mod.collect(NOW,fetcher=fail)
        self.assertEqual(len(out["series"]),0)
        self.assertEqual(len(out["audit"]),42)
        self.assertTrue(all(x["status"]=="WITHHELD_FETCH_OR_VALIDATION" for x in out["audit"].values()))
        self.assertNotIn("status","PASS")

if __name__=="__main__":unittest.main()
