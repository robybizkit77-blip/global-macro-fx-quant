import unittest
from datetime import date
from validation.macro.prepare_final_liquidity_contracts_v1 import ecb_candidate,gbp_candidate
from validation.liquidity.probe_ecb_eur_bls_actual_v1 import quarter_label
TODAY=date(2026,11,27)
def row(obs):
    ds=[quarter_label(q) for q in sorted(obs)];vs=[obs[q] for q in sorted(obs)]
    return dict(dates=ds,values=vs,last_date=ds[-1],last_value=vs[-1])
class Tests(unittest.TestCase):
    def test_ecb_shift_and_repeat(self):
        end=2026*4+3;records={q:float(q%17) for q in range(end-42,end+1)}
        old=row({q:v for q,v in records.items() if q<end})
        out=ecb_candidate(old,records,TODAY)
        self.assertEqual(out["last_date"],"2026-Q3")
        self.assertEqual(out["last_value"],records[end])
        self.assertEqual(ecb_candidate(out,records,TODAY),out)
    def test_ecb_reject_wrong_vintage(self):
        end=2026*4+3;records={q:float(q%17) for q in range(end-42,end+1)}
        old=row({q:v+1 for q,v in records.items() if q<end})
        with self.assertRaises(ValueError):ecb_candidate(old,records,TODAY)
    def test_boe_retain_prefix_and_reject_bad_overlap(self):
        end=2026*4+2;obs={q:float(q%17) for q in range(end-40,end+1)}
        old=row({q:v for q,v in obs.items() if q<end})
        report=row({q:v for q,v in obs.items() if q>=end-5})
        report.update(series_id="BOE_CCS_CORPORATE_AVAILABILITY_ACTUAL",positive_means="increased_availability",latest_observation=report["last_date"],source_url="official")
        out=gbp_candidate(old,report,TODAY)
        self.assertEqual(out["dates"][0],old["dates"][0])
        self.assertEqual(out["last_date"],"2026-Q3")
        self.assertEqual(gbp_candidate(out,report,TODAY),out)
        report["values"][0]+=1
        with self.assertRaises(ValueError):gbp_candidate(old,report,TODAY)
if __name__=="__main__":unittest.main()
