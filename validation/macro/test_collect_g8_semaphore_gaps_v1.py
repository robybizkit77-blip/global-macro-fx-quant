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
    def test_rba_d1_history_and_release_identity(self):
        out=StringIO()
        writer=csv.writer(out)
        writer.writerows([
            ["Title","Credit; Housing; Monthly growth","Credit; Non-financial Business; Monthly growth","Credit; Housing; Year-ended growth","Credit; Business including select financial businesses; Monthly growth"],
            ["Units","Per cent","Per cent","Per cent","Per cent"],
            ["Frequency","Monthly","Monthly","Monthly","Monthly"],
            ["Series ID","HOUSING","DGFACBNFM","ANNUAL","DGFACBNWM"],
        ])
        for i in range(36):
            year,m=divmod(2026*12+8-35+i,12)
            writer.writerow([f"{year}-{m+1:02d}-01",0.4,0.9,7.0,0.9])
        raw=out.getvalue().encode()
        for key,value in [("RBA_HOUSING_CREDIT_GROWTH_MM",0.4),("RBA_BUSINESS_CREDIT_GROWTH_MM",0.9)]:
            reference=[("2026-08",value),("2026-09",value)]
            obs=mod.parse_rba_d1(raw,NOW,key,reference)
            self.assertEqual(len(obs),36)
            self.assertEqual(obs[-2:],reference)
            with self.assertRaises(ValueError):
                mod.parse_rba_d1(raw,NOW,key,[("2026-08",9.0),("2026-09",9.0)])
            with self.assertRaises(ValueError):
                mod.parse_rba_d1(raw.replace(b"Monthly growth",b"Annual growth"),NOW,key,reference)

        with self.assertRaises(ValueError):
            mod.parse_rba_d1(raw.replace(b"DGFACBNFM",b"UNKNOWN"),NOW,
                "RBA_BUSINESS_CREDIT_GROWTH_MM",[("2026-08",0.9),("2026-09",0.9)])

    def test_anz_own_activity_release_summary_proxy(self):
        raw=b'''<h1>ANZ Business Outlook</h1>
        <h2>October 2026</h2><p>Business confidence rose 1 point to +53.
        Expected own activity eased 2 points to +46. Reported past activity rose to +15.</p>
        <h2>September 2026</h2><p>Business confidence eased to +52.
        Expected own activity was steady at +48. Reported past activity fell to +11.</p>'''
        self.assertEqual(mod.parse_anz_outlook(raw,NOW),[("2026-09",48.0),("2026-10",46.0)])
        with self.assertRaises(ValueError):
            mod.parse_anz_outlook(raw.replace(b"September 2026",b"August 2026"),NOW)
        with self.assertRaises(ValueError):
            mod.parse_anz_outlook(raw.replace(b"Expected own activity",b"Reported past activity"),NOW)
        with self.assertRaises(ValueError):
            mod.parse_anz_outlook(raw,date(2027,3,1))

    def test_nzd_bis_housing_proxy_identity_depth_freshness(self):
        spec=next(x for x in mod.REGISTRY if x["ccy"]=="NZD" and x["area"]=="house")
        # Use bounded realistic annual changes with a separate exact series ID.
        out=StringIO()
        writer=csv.writer(out);writer.writerow(["observation_date","QNZR368BIS"])
        for i in range(16):
            y,q=divmod(2026*4+1-15+i,4)
            writer.writerow([f"{y}-{q*3+1:02d}-01",-5+i*.25])
        raw=out.getvalue().encode()
        def exact(url):
            self.assertEqual(url,mod.FRED+"QNZR368BIS");return raw
        item,status=mod.collect_nzd_bis_housing(spec,NOW,exact)
        self.assertEqual(item["frequency"],"Q")
        self.assertEqual(item["source_series_id"],"QNZR368BIS")
        self.assertEqual(item["history"]["observations"],12)
        self.assertEqual(status["status"],"READY_DESCRIPTIVE_REVISED")
        self.assertIsNone(mod.collect_nzd_bis_housing(spec,date(2027,3,1),exact)[0])
        with self.assertRaises(ValueError):
            mod.collect_nzd_bis_housing(spec,NOW,lambda _:raw.replace(b"QNZR368BIS",b"WRONG"))

    def test_prefer_current_psi_rejects_older_automatic_observation(self):
        spec=next(x for x in mod.REGISTRY if x["ccy"]=="NZD" and x["area"]=="services")
        now=date(2026,11,24)
        old,old_status=mod.candidate(spec,[("2026-08",51.0),("2026-09",50.9)],now)
        item,status=mod.prefer_current_psi(spec,now,old,old_status)
        self.assertEqual(item["dates"],["2026-09","2026-10"])
        self.assertEqual(item["values"],[50.9,51.7])
        self.assertEqual(status["status"],"READY_MANUAL_VERIFIED_NOT_AUTOMATIC")
        self.assertEqual(status["automatic_last_observation"],"2026-09")
        same,same_status=mod.candidate(spec,[("2026-09",50.9),("2026-10",51.7)],now)
        self.assertEqual(mod.prefer_current_psi(spec,now,same,same_status),(same,same_status))

    def test_ons_kac3_wage_identity_and_months(self):
        rows="".join(f"<tr><td>2025 {m}</td><td>{3+i/10:.1f}</td></tr>" for i,m in enumerate(["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]))
        raw=("<h1>AWE: Whole Economy Year on Year Three Month Average Growth (%): Seasonally Adjusted Total Pay Excluding Arrears</h1><p>Series ID: KAC3</p><table>"+rows+"</table>").encode()
        obs=mod.parse_ons_wage(raw,NOW)
        self.assertEqual(len(obs),12)
        self.assertEqual(obs[-1],("2025-12",4.1))
        with self.assertRaises(ValueError):
            mod.parse_ons_wage(raw.replace(b"KAC3",b"KAC6"),NOW)
        with self.assertRaises(ValueError):
            mod.parse_ons_wage(raw.replace(b"Whole Economy",b"Private Sector"),NOW)

    def test_can_wage_wds_coordinate_and_exact_annual_rates(self):
        meta={"productId":mod.CAN_WAGE_PID,"cubeTitleEn":"Employee wages by industry, monthly, unadjusted for seasonality",
              "dimension":[{"dimensionNameEn":name,"dimensionPositionId":i+1,"member":[{"memberNameEn":value,"memberId":i+1},{"memberNameEn":"Other","memberId":99}]} for i,(name,value) in enumerate(mod.CAN_WAGE_MEMBERS.items())]}
        coord=mod.can_wage_coordinate(meta)
        self.assertEqual(coord,"1.2.3.4.5.6.0.0.0.0")
        obj={"productId":mod.CAN_WAGE_PID,"coordinate":coord,
             "vectorDataPoint":[{"refPer":f"{y}-{m:02d}-01","value":30*(1.04**(y-2023)),"scalarFactorCode":0} for y in (2023,2024,2025) for m in range(1,13)]}
        obs=mod.parse_can_wage_wds(obj,coord,NOW)
        self.assertEqual(len(obs),24)
        self.assertAlmostEqual(obs[-1][1],4.0)
        with self.assertRaises(ValueError):mod.parse_can_wage_wds(obj,"9.2.3.4.5.6.0.0.0.0",NOW)
        meta["dimension"][0]["member"][0]["memberNameEn"]="Ontario"
        with self.assertRaises(ValueError):mod.can_wage_coordinate(meta)

    def test_nz_wage_manual_snapshot_expiry(self):
        obs,page=mod.curated_nz_wage(date(2026,11,25))
        self.assertEqual(len(obs),12)
        self.assertEqual(obs[-2:],[("2026-Q2",2.0),("2026-Q3",2.1)])
        self.assertTrue(page.endswith("september-2026-quarter/"))
        with self.assertRaises(ValueError):mod.curated_nz_wage(date(2027,2,4))
        with self.assertRaises(ValueError):mod.curated_nz_wage(date(2026,11,24))

    def test_ch_annual_wage_context_not_quarterly(self):
        item=mod.ch_wage_annual_context(date(2026,11,25))
        self.assertEqual(item["frequency"],"A")
        self.assertEqual(item["values"],[1.7,1.8,1.8])
        self.assertEqual(item["scope"],"ANNUAL_ACTUAL_NOT_QUARTERLY")
        with self.assertRaises(ValueError):mod.ch_wage_annual_context(date(2027,4,30))

    def test_external_context_exact_real_exports_and_stale_guard(self):
        self.assertEqual(set(mod.EXPORT_KEYS),{"USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD"})
        method="eurostat_exports_real"
        _,selectors=mod.EUROSTAT_EXTRA[method]
        periods=[f"{y}-Q{q}" for y in (2023,2024,2025) for q in range(1,5)]+["2026-Q1","2026-Q2"]
        dims={k:{"category":{"index":{v:0}}} for k,v in selectors.items()}
        dims["time"]={"category":{"index":{p:i for i,p in enumerate(periods)}}}
        payload={"class":"dataset","id":list(selectors)+["time"],"size":[1]*len(selectors)+[len(periods)],"dimension":dims,"value":{str(i):(-1 if i==12 else 2.5) for i in range(len(periods))}}
        def fetcher(url):
            if url==mod.euro_extra_url(method):return mod.json.dumps(payload).encode()
            key=url.split("=")[-1]
            return ("observation_date,"+key+"\n"+"".join(f"{p[:4]}-{(int(p[-1])-1)*3+1:02d}-01,2.5\n" for p in periods)).encode()
        out=mod.collect_external_context(date(2026,11,25),fetcher)
        self.assertEqual(len(out["series"]),8)
        self.assertTrue(all(x["history"]["observations"]==12 and x["unit"]=="% a/a reale" for x in out["series"]))
        self.assertEqual(out["audit"]["EUR"]["last_observation"],"2026-Q2")
        self.assertEqual(len(mod.collect_external_context(date(2027,3,1),fetcher)["series"]),0)
        payload["dimension"]["unit"]["category"]["index"]={"CP_MEUR":0}
        rejected=mod.collect_external_context(date(2026,11,25),fetcher)
        self.assertEqual(rejected["audit"]["EUR"]["status"],"WITHHELD_FETCH_OR_VALIDATION")

    def test_registry_targets_exactly_eight_gaps(self):
        self.assertEqual(len(mod.REGISTRY),43)
        self.assertEqual(len({(s["ccy"],s["area"]) for s in mod.REGISTRY}),43)
        self.assertTrue(all(s["source_page"].startswith("https://") for s in mod.REGISTRY))
        self.assertTrue(all(s["method"] in {"fred","eurostat","eurostat_services","eurostat_industry","eurostat_esi","eurostat_retail","eurostat_house_price","statcan","ons","ons_industry","boe_mortgage","statsnz_house","statcan_services","biznz","abs_services","abs_demand","rba_credit","statcan_detail","boj_credit","rbnz_credit","snb_credit"} for s in mod.REGISTRY))

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

    def test_contiguous_history_preserves_latest_pair_and_single_vintage(self):
        for freq,n,limit,end in (("M",50,36,(2026,9)),("Q",24,12,(2026,2))):
            spec=next(s for s in mod.REGISTRY if s["method"]=="fred" and s["frequency"]==freq)
            obs=mod.parse_fred(fixture(spec["key"],freq,end,n),spec["key"],freq,NOW)
            item,status=mod.candidate(spec,obs,NOW)
            h=item["history"]
            self.assertEqual(h["observations"],limit)
            self.assertEqual(h["source_series_id"],spec["key"])
            self.assertEqual(h["dates"],[p for p,v in obs[-limit:]])
            self.assertEqual(h["values"][-2:],item["values"])
            self.assertEqual(h["dates"][-2:],item["dates"])
            self.assertEqual(h["quality"],"SINGLE_SOURCE_REVISED_VINTAGE_NOT_PIT")
            self.assertEqual(status["history_observations"],limit)
            short=obs[:-5]+obs[-4:]
            h=mod.contiguous_history(short,freq,NOW)
            self.assertEqual(h["observations"],4)
            with self.assertRaises(ValueError):
                mod.contiguous_history(obs+[obs[-1]],freq,NOW)
            with self.assertRaises(ValueError):
                mod.contiguous_history(obs[:-2]+[obs[-1]],freq,NOW)
            with self.assertRaises(ValueError):
                mod.contiguous_history(obs[:-1]+[(obs[-1][0],float("nan"))],freq,NOW)

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

    def test_nzd_credit_proxy_exact_attributed_pair(self):
        html=b"<h2>Private Sector Credit in New Zealand increased to 630847 NZD Million in September from 624663 NZD Million in August of 2026. source: <a>Reserve Bank of New Zealand</a></h2>"
        self.assertEqual(mod.parse_nzd_credit_proxy(html,date(2026,11,24)),[("2026-08",624663),("2026-09",630847)])
        with self.assertRaises(ValueError):mod.parse_nzd_credit_proxy(html.replace(b"Reserve Bank of New Zealand",b"Other issuer"),date(2026,11,24))
        with self.assertRaises(ValueError):mod.parse_nzd_credit_proxy(html.replace(b"in August",b"in July"),date(2026,11,24))
        with self.assertRaises(ValueError):mod.parse_nzd_credit_proxy(html,date(2026,8,31))

    def test_statsnz_zip_exact_series(self):
        bio=io.BytesIO()
        with ZipFile(bio,"w") as z:
            z.writestr("consents.csv","Series_reference,Period,Data_value,UNITS,MAGNTUDE,Suppressed\nBLDM.SFTZ1100A1S,2026.08,3495,Number,0,\nBLDM.SFTZ1100A1S,2026.09,3218,Number,0,\nBLDM.FAKE,2026.10,9999,Number,0,\n")
        self.assertEqual(mod.parse_statsnz_house_zip(bio.getvalue(),date(2026,11,24)),[("2026-08",3495),("2026-09",3218)])
        self.assertIn("September-2026/Download-data/building-consents-issued-september-2026.zip",mod.statsnz_house_zip_url(date(2026,11,24),2))

    def test_bnz_copublisher_psi(self):
        html="""<h3>BNZ Services Landscape (PSI)</h3><p>BNZ Research - BusinessNZ - 16.11.2026</p>
        <p>According to the BNZ – BusinessNZ Performance of Services Index (PSI), activity grew.
        The PSI for October was 51.7 (where a reading above 50.0 indicates expansion).
        This was up 0.8 points from 50.9 in September.</p>
        <p>BNZ Research - BusinessNZ - 19.10.2026</p>
        <p>Performance of Services Index (PSI). The PSI for September was 50.8.
        This was down from 51.0 in August.</p>"""
        self.assertEqual(mod.parse_bnz_psi(html.encode(),date(2026,11,24)),[("2026-09",50.9),("2026-10",51.7)])
        self.assertEqual(mod.parse_bnz_psi(html.replace("BNZ Research - BusinessNZ - 16.11.2026","NZ Research - BusinessNZ - 16.11.2026").encode(),date(2026,11,24)),[("2026-09",50.9),("2026-10",51.7)])
        self.assertEqual(mod.parse_bnz_psi(html.encode(),date(2026,11,1)),[("2026-08",51.0),("2026-09",50.8)])
        with self.assertRaises(ValueError):mod.parse_bnz_psi(html.replace("Performance of Services Index (PSI)","Manufacturing Index (PMI)").encode(),date(2026,11,24))

    def test_snb_exact_domestic_loan_utilisation(self):
        raw='CubeId;bakredinausbm\nPublishingDate;2026-11-23 09:00\n\nDate;D0;D1;D2;D3;Value\n'
        for y in (2025,2026):
            for m in range(1,11):
                raw+=f"{y}-{m:02d};AV1;I;T1;F;{1400000+m*1000}\n"
                raw+=f"{y}-{m:02d};AV1;I;T1;B;9999999\n"
        out=mod.parse_snb_credit(raw.encode(),date(2026,11,24))
        self.assertEqual(out[-2:],[("2026-09",1409000),("2026-10",1410000)])
        meta={"cubeId":"bakredinausbm","dimensions":[
          {"id":k,"dimensionItems":[{"id":c,"name":n}]} for k,c,n in
          [("D0","AV1","Banks in Switzerland"),("D1","I","Domestic"),("D2","T1","Total loans"),("D3","F","Utilisation")]]}
        mod.validate_snb_credit_metadata(json.dumps(meta).encode())
        meta["dimensions"][-1]["dimensionItems"][0]["name"]="Credit lines"
        with self.assertRaises(ValueError):mod.validate_snb_credit_metadata(json.dumps(meta).encode())
        with self.assertRaises(ValueError):mod.parse_snb_credit(raw.replace("bakredinausbm","wrong").encode(),date(2026,11,24))

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
        self.assertEqual(len(out["audit"]),43)
        self.assertTrue(all(x["status"]=="WITHHELD_FETCH_OR_VALIDATION" for x in out["audit"].values()))
        self.assertNotIn("status","PASS")

    def test_core_recovery_identity_and_history(self):
        months=["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
        rows=[]
        for i in range(24):
            y,m=divmod(2026*12+9-23+i,12)
            rows.append(f"<tr><td>{y} {months[m]}</td><td>{2+i/100}</td></tr>")
        raw=("<h1>CPI 12mth: Excluding Energy, food, alcoholic beverages &amp; tobacco 2015=100</h1><p>Series ID: DKO8</p><table>"+"".join(rows)+"</table>").encode()
        data=mod.collect_inflation_context(NOW,fred_fetcher=lambda _:fixture("CPILFESL",end=(2026,10)),ons_fetcher=lambda _:raw)
        self.assertEqual(len(data["series"]),2)
        for item in data["series"]:
            self.assertEqual(item["dates"],["2026-09","2026-10"])
            self.assertEqual(item["history"]["observations"],24)
        self.assertRaises(ValueError,mod.parse_ons_core,raw.replace(b"DKO8",b"DKC6"),NOW)
        bad=mod.collect_inflation_context(NOW,fred_fetcher=lambda _:fixture("WRONG"),ons_fetcher=lambda _:raw.replace(b"DKO8",b"DKC6"))
        self.assertEqual(bad["series"],[])
        # October 2025 absent: October 2026 index still valid, annual rate not.
        gap=fixture("CPILFESL",end=(2026,10))
        gap=b"\n".join(line for line in gap.splitlines() if not line.startswith(b"2025-10-"))
        partial=mod.collect_inflation_context(NOW,fred_fetcher=lambda _:gap,ons_fetcher=lambda _:raw)
        self.assertEqual(partial["audit"]["USD"]["latest_index_period"],"2026-10")
        self.assertEqual(partial["audit"]["USD"]["latest_yoy_period"],"2026-09")
        self.assertEqual(partial["audit"]["USD"]["annual_status"],"SOURCE_BASE_PERIOD_MISSING")
        self.assertNotIn("2025-10",partial["series"][0]["exact_lag_history"]["dates"])

    def test_eurostat_core_identity(self):
        selectors={"freq":"M","geo":"EA21","unit":"RCH_A","coicop18":"TOT_X_NRG_FOOD"}
        dates=[f"2025-{m:02d}" for m in range(1,13)]+[f"2026-{m:02d}" for m in range(1,11)]
        dimensions={k:{"category":{"index":{v:0}}} for k,v in selectors.items()}
        dimensions["time"]={"category":{"index":{p:i for i,p in enumerate(dates)}}}
        obj={"class":"dataset","id":list(selectors)+["time"],"size":[1]*4+[len(dates)],
             "dimension":dimensions,"value":{str(i):2+i/100 for i in range(len(dates))}}
        encode=lambda:json.dumps(obj).encode()
        item,status=mod.collect_eur_core(NOW,fetcher=lambda _:encode())
        self.assertEqual(item["source_series_id"],mod.EUR_CORE_KEY)
        self.assertEqual(item["dates"],["2026-09","2026-10"])
        self.assertEqual(status["history_observations"],22)
        obj["dimension"]["coicop18"]["category"]["index"]={"TOTAL":0}
        self.assertIsNone(mod.collect_eur_core(NOW,fetcher=lambda _:encode())[0])

    def test_cad_core_exact_labels_and_independent_validation(self):
        def archive(invalid=False):
            out=StringIO();w=csv.writer(out)
            w.writerow(["REF_DATE","GEO","Alternative measures","UOM","SCALAR_FACTOR","VALUE","VECTOR"])
            for i in range(24):
                y,m=divmod(2026*12+9-23+i,12)
                for j,label in enumerate(mod.CAD_CORE_LABELS.values()):
                    w.writerow([f"{y}-{m+1:02d}","Canada",label,"Index" if invalid and j==1 else "Percent","units",2+i/100,f"v{j+1}"])
                w.writerow([f"{y}-{m+1:02d}","Canada","CPI-trim (index)","Index","units",130,"v9"])
            buf=io.BytesIO()
            with ZipFile(buf,"w") as z:z.writestr("18100256.csv",out.getvalue())
            return buf.getvalue()
        items,audit=mod.collect_cad_core(NOW,fetcher=archive)
        self.assertEqual(len(items),2)
        self.assertTrue(all(x["dates"]==["2026-09","2026-10"] for x in items))
        items,audit=mod.collect_cad_core(NOW,fetcher=lambda:archive(True))
        self.assertEqual(len(items),1)
        self.assertEqual(audit["STATCAN_18100256_TRIM_YOY"]["status"],"WITHHELD_FETCH_OR_VALIDATION")

    def test_japan_and_abs_core_exact_identity(self):
        rows=[["類・品目","総合","生鮮食品を除く総合"],["Group/Item","All items","All items, less fresh food"],
              ["類・品目符号(Group/Item code)","0001","0161"],["Serial"],["Weight"],["Weight ratio"]]
        months=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        table="<table><tr><th></th><th>All groups CPI (%)</th><th>Trimmed mean (%)</th></tr>"
        for i in range(20):
            y,m=divmod(2026*12+9-19+i,12)
            rows.append([f"{y}{m+1:02d}","4.9",str(1+i/10)])
            table+=f"<tr><td>{months[m]}-{y%100:02d}</td><td>4.9</td><td>{1+i/10}</td></tr>"
        table+="</table>"
        out=StringIO();csv.writer(out).writerows(rows)
        jp=out.getvalue().encode("cp932");au=table.encode()
        items,audit=mod.collect_asia_core(NOW,fetcher=lambda u:jp if u==mod.JP_CORE_URL else au)
        self.assertEqual(len(items),2)
        self.assertTrue(all(x["dates"]==["2026-09","2026-10"] for x in items))
        self.assertRaises(ValueError,mod.parse_jp_core,jp.replace(b"0161",b"0178"),NOW)
        self.assertRaises(ValueError,mod.parse_abs_core,au.replace(b"Trimmed mean (%)",b"Weighted median (%)"),NOW)

    def test_ch_nz_core_contracts(self):
        from openpyxl import Workbook
        book=Workbook();ws=book.active;ws.title="VAR_m-12"
        ws.append(["Landesindex der Konsumentenpreise",None,None,None,None,"Veränderungsrate gegenüber Vorjahresmonat in %"])
        ws.append(["Warenkorbstruktur 2025"])
        ws.append([None])
        months=[f"{y:04d}-{m:02d}" for y,m in [divmod(2026*12+9-19+i,12) for i in range(20)]]
        months=[f"{p[:4]}-{int(p[5:])+1:02d}" for p in months]
        ws.append(["Code","PosNo"]+[None]*11+months)
        ws.append(["1170_103","103"]+[None]*10+["Core inflation 1"]+[.2+i/10 for i in range(20)])
        buf=io.BytesIO();book.save(buf)
        obs=mod.parse_ch_core(buf.getvalue(),NOW)
        self.assertEqual(obs[-1][0],"2026-10")
        rows=[["","Consumers price index (CPI)","Factor model","Sectoral factor model","Tradable inflation","Non-tradable inflation"],
              ["Date","(Index)","(q/q%)","(y/y%)","(y/y%)","(y/y%)","(Index)","(y/y%)","(Index)","(y/y%)"]]
        for p,v in [("Dec 2025",2.7),("Mar 2026",2.7),("Jun 2026",2.8),("Sept 2026",2.8)]:
            rows.append([p,"100","1","3","3",str(v),"100","1","100","3"])
        page=("<table>"+"".join("<tr>"+"".join("<td>"+v+"</td>" for v in row)+"</tr>" for row in rows)+"</table>").encode()
        self.assertEqual(mod.parse_nz_core_page(page,NOW)[-1],("2026-Q3",2.8))
        self.assertRaises(ValueError,mod.parse_nz_core_page,page.replace(b"Sectoral factor model",b"Other model"),NOW)

    def test_cad_lfs_contract(self):
        names=list(mod.CAD_LFS_MEMBERS.items())
        meta={"productId":mod.CAD_LFS_PID,"cubeTitleEn":"Labour force characteristics, monthly, seasonally adjusted and trend-cycle",
            "dimension":[{"dimensionNameEn":k,"dimensionPositionId":i+1,"member":[{"memberNameEn":v,"memberId":1}]} for i,(k,v) in enumerate(names)]}
        coord=mod.cad_lfs_coordinate(meta)
        obj={"productId":mod.CAD_LFS_PID,"coordinate":coord,"vectorDataPoint":[]}
        for i in range(24):
            y,m=divmod(2026*12+9-23+i,12)
            obj["vectorDataPoint"].append({"refPer":f"{y}-{m+1:02d}-01","value":6+i/100,"scalarFactorCode":0})
        item,status=mod.collect_cad_lfs(NOW,wds=lambda method,payload:meta if method=="getCubeMetadata" else obj)
        self.assertEqual(item["dates"][-1],"2026-10")
        self.assertFalse(item["up_good"])
        self.assertEqual(status["history_observations"],24)
        obj["coordinate"]="wrong"
        self.assertIsNone(mod.collect_cad_lfs(NOW,wds=lambda method,payload:meta if method=="getCubeMetadata" else obj)[0])

if __name__=="__main__":unittest.main()
