"""EUR daily 2Y/10Y old-history quarantine and safe G8 feed continuity."""
import copy
from datetime import date, timedelta
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

from validation import build_rates_candidate_from_audit as m


class EURDailyRatesHistorySourceGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live=json.loads(m.DEFAULT_CURRENT.read_text(encoding="utf-8"))

    @staticmethod
    def next_date(row):
        return (date.fromisoformat(row['date'])+timedelta(days=1)).isoformat()

    def test_real_known_official_tail_accepted_on_both_source_versions(self):
        row=self.live['EUR']
        r=m.eur_daily_append_source_gate(row,self.next_date(row))
        self.assertEqual(r['source_clean_tail_from'],'2026-10-13')
        self.assertEqual(r['history_status'],row['history_status'])
        self.assertEqual(r['historical_legacy_basis_quarantined'],
                         row['history_status']==m.EUR_LEGACY_STATUS)
        self.assertFalse(r['historical_first_release_pit_certified'])
        self.assertGreaterEqual(r['weekly_ref'],'2026-10-16')

    def test_legacy_provenance_cannot_be_silently_upgraded(self):
        src=copy.deepcopy(self.live['EUR'])
        src['history_status']='FULL_ECB_SAME_BASIS_2Y_10Y_RESEARCH_CANDIDATE_ONLY'
        with self.assertRaisesRegex(ValueError,"not approved"):
            m.eur_daily_append_source_gate(src,self.next_date(src))
        src['history_status']=m.EUR_LEGACY_STATUS
        src['history2_quality']='COMPLETE_SOURCE_VERIFIED'
        with self.assertRaisesRegex(ValueError,"quarantine label changed"):
            m.eur_daily_append_source_gate(src,self.next_date(src))

    def test_known_official_2y_or_10y_date_value_tampering_blocks_eur_only(self):
        for key in ['history2','history10']:
            with self.subTest(key=key):
                src=copy.deepcopy(self.live['EUR'])
                idx=src[key]['dates'].index('2026-10-15')
                src[key]['values'][idx]+=0.05
                with self.assertRaisesRegex(ValueError,"(clean tail drift|historical values drift)"):
                    m.eur_daily_append_source_gate(src,self.next_date(src))

    def test_one_tenor_different_calendar_or_unordered_history_blocks(self):
        for key in ['history2','history10']:
            src=copy.deepcopy(self.live['EUR'])
            src[key]['dates'][-2]=src[key]['dates'][-3]
            with self.assertRaisesRegex(ValueError,"duplicated or unordered"):
                m.eur_daily_append_source_gate(src,self.next_date(src))

    def test_weekly_reference_must_not_use_legacy_curve_values(self):
        # Next official source observation years ahead must not use a stale
        # 7-calendar-day weekly baseline for an invented change.
        eur=self.live['EUR']
        gap=(date.fromisoformat(eur['date'])+timedelta(days=15)).isoformat()
        with self.assertRaisesRegex(ValueError,"gap >12"):
            m.eur_daily_append_source_gate(eur,gap)
        with self.assertRaisesRegex(ValueError,"new official observation does not advance"):
            m.eur_daily_append_source_gate(eur,eur['date'])


    def approved_fake_fixture_for_contract_tests(self):
        """Synthetic source data: contracts ONLY, not market observations."""
        from hashlib import sha256
        from datetime import date
        s=copy.deepcopy(self.live['EUR'])
        if s.get('history_status')==m.EUR_APPROVED_STATUS:
            # Real published fixture is the stronger original official check;
            # no fictitious extra observations are added after promotion.
            return s
        extra=['2026-09-23','2026-09-24','2026-09-25','2026-09-28',
               '2026-09-29','2026-09-30','2026-10-05','2026-10-07',
               '2026-10-08','2026-10-09','2026-10-12']
        for name in ('history2','history10'):
            vals=dict(zip(s[name]['dates'],s[name]['values']))
            for d in extra:
                vals[d]=3.1 if name=='history2' else 3.5
            ordered=sorted(vals.items())
            s[name]['dates']=[d for d,v in ordered]
            s[name]['values']=[v for d,v in ordered]
        assert len(s['history2']['dates'])==282
        paired=[[d,s['history2']['values'][i],s['history10']['values'][i]]
                for i,d in enumerate(s['history2']['dates'])]
        sha=sha256(json.dumps(paired,separators=(',',':'),
                             ensure_ascii=False).encode()).hexdigest()
        s['history_status']=m.EUR_APPROVED_STATUS
        s['history2_quality']='ECB_ORIGINAL_2Y_FULL_HISTORICAL_LATEST_VINTAGE_NOT_PIT'
        s['history10_quality']='ECB_ORIGINAL_10Y_FULL_HISTORICAL_LATEST_VINTAGE_NOT_PIT'
        s['historical_curve_rebase']={
            'schema':'GMFQ_EUR_2Y_10Y_HISTORY_REBASE_NOTICE_V1',
            'status':'PUBLISHED_AFTER_SOURCE_AND_BROWSER_QA',
            'source_authority':'European Central Bank',
            'original_ecb_2y_csv_sha256':
              '2d5b0e884b0d3728c29d935e0982e761896102bd401f4ae406a17680f6079bab',
            'original_ecb_10y_csv_sha256':
              'c536410864ee8f873533509167ab350a189ed0987201b09b490f158aa85b9b4e',
            'original_history_start':'2025-09-16','original_history_end':'2026-10-22',
            'original_point_count':282,'original_paired_values_sha256':sha,
            'historical_first_release_pit_certified':False,
            'source_rebase_not_market_move':True,
            'chf_reference_beta_recalibration_not_official_chf_yield':True,
            'requires_explicit_release':False,
        }
        return s

    def test_approved_origin_fingerprint_maintains_282_publisher_prefix(self):
        s=self.approved_fake_fixture_for_contract_tests()
        proof=m.eur_daily_append_source_gate(s,self.next_date(s))
        self.assertEqual(proof['history_status'],m.EUR_APPROVED_STATUS)
        self.assertFalse(proof['historical_legacy_basis_quarantined'])

    def test_approved_origin_fingerprint_rejects_historical_rewrite(self):
        s=self.approved_fake_fixture_for_contract_tests()
        s['history2']['values'][10]+=.007
        with self.assertRaisesRegex(ValueError,'historical values drift'):
            m.eur_daily_append_source_gate(s,'2026-10-23')
        s=self.approved_fake_fixture_for_contract_tests()
        s['historical_curve_rebase']['original_ecb_2y_csv_sha256']='not_official'
        with self.assertRaisesRegex(ValueError,'publication evidence incomplete'):
            m.eur_daily_append_source_gate(s,'2026-10-23')
        s=self.approved_fake_fixture_for_contract_tests()
        s['historical_curve_rebase']['status']='RESEARCH_CANDIDATE_NOT_PUBLISHED'
        with self.assertRaisesRegex(ValueError,'publication evidence incomplete'):
            m.eur_daily_append_source_gate(s,'2026-10-23')

    def test_candidate_never_passes_as_published_source_even_with_good_rates(self):
        s=self.approved_fake_fixture_for_contract_tests()
        s['history_status']='FULL_ECB_SAME_BASIS_2Y_10Y_RESEARCH_CANDIDATE_ONLY'
        with self.assertRaisesRegex(ValueError,'not approved'):
            m.eur_daily_append_source_gate(s,'2026-10-23')

    def run_builder(self,currencies,*,tamper_eur=False):
        src=copy.deepcopy(self.live)
        if tamper_eur:
            idx=src['EUR']['history2']['dates'].index('2026-10-15')
            src['EUR']['history2']['values'][idx]+=.2
        audit={'status':'PASS','summary':{'updates_available':list(currencies)},
               'currencies':{}}
        for c in currencies:
            d=src[c]
            audit['currencies'][c]={
                'coverage_mode':'LIVE_FETCH',
                'official':{'date':self.next_date(d),'2Y':d['2Y']+.01,
                            '10Y':d['10Y']+.01}}
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)
            (d/'rates.json').write_text(json.dumps(src))
            (d/'audit.json').write_text(json.dumps(audit))
            proc=subprocess.run([sys.executable,str(Path(m.__file__)),
                '--current-rates',str(d/'rates.json'),
                '--audit',str(d/'audit.json'),
                '--output',str(d/'out.json')],
                text=True,capture_output=True)
            return proc,json.loads((d/'out.json').read_text()) if (d/'out.json').exists() else None

    def test_safe_official_eur_update_only_appends_does_not_claim_history_repaired(self):
        proc,out=self.run_builder(['EUR'])
        self.assertEqual(proc.returncode,0,proc.stderr)
        receipt=json.loads(proc.stdout)
        self.assertEqual(receipt['status'],'CANDIDATE_READY')
        self.assertEqual(receipt['changed_currencies'],['EUR'])
        self.assertEqual(receipt['quarantined_currencies'],{})
        self.assertEqual(out['EUR']['history_status'],self.live['EUR']['history_status'])
        self.assertEqual(out['EUR']['history2_quality'],self.live['EUR']['history2_quality'])
        self.assertEqual(out['EUR']['history2']['dates'][-1],self.next_date(self.live['EUR']))
        self.assertEqual(len(out['EUR']['history2']['dates']),
                         len(self.live['EUR']['history2']['dates'])+1)
        self.assertGreaterEqual(out['EUR']['weekly2_validation']['start_date'],'2026-10-16')

    def test_eur_bad_history_quarantines_only_eur_and_other_official_ccy_advances(self):
        proc,out=self.run_builder(['EUR','CAD'],tamper_eur=True)
        self.assertEqual(proc.returncode,0,proc.stderr)
        receipt=json.loads(proc.stdout)
        self.assertEqual(receipt['status'],'CANDIDATE_READY')
        self.assertEqual(receipt['changed_currencies'],['CAD'])
        self.assertEqual(receipt['quarantined_currencies']['EUR']['status'],
                         'DAILY_OFFICIAL_NEW_SNAPSHOT_QUARANTINED')
        self.assertTrue(receipt['quarantined_currencies']['EUR']['existing_eur_history_unchanged'])
        self.assertEqual(out['EUR']['date'],self.live['EUR']['date'])
        self.assertEqual(out['CAD']['date'],self.next_date(self.live['CAD']))

    def test_eur_only_bad_history_no_updates_preserves_source_aged_metadata_path(self):
        proc,out=self.run_builder(['EUR'],tamper_eur=True)
        self.assertEqual(proc.returncode,0,proc.stderr)
        receipt=json.loads(proc.stdout)
        self.assertEqual(receipt['status'],'NO_UPDATES')
        self.assertEqual(receipt['changed_currencies'],[])
        self.assertIn('EUR',receipt['quarantined_currencies'])
        self.assertEqual(out['EUR']['date'],self.live['EUR']['date'])

    def test_no_updates_leave_full_rates_identical(self):
        proc,out=self.run_builder([])
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertEqual(json.loads(proc.stdout)['status'],'NO_UPDATES')
        self.assertEqual(out,self.live)


if __name__=='__main__':
    unittest.main()
