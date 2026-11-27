import copy, json, pathlib, unittest
from validation.build_cot_official_oi_v1 import build
ROOT=pathlib.Path(__file__).resolve().parents[1]
class TestOfficialOI(unittest.TestCase):
    def setUp(self):
        self.seed=json.loads((ROOT/'site/fx-quant-v2/next/cot-official-oi-v1.json').read_text())
        self.chart={c:{'dates':[r['date']],'long':[r['long']],'short':[r['short']],'net':[r['net']],'netoi':[round(r['net']/r['open_interest']*100,3)]} for c,r in self.seed['currencies'].items()}
        self.summary={'source':'CFTC Legacy Futures Only current reports','status':'NO_UPDATE','official_as_of':self.seed['as_of'],'official':copy.deepcopy(self.seed['currencies'])}
    def test_reconstruction(self):
        self.assertEqual(build(self.summary,self.chart),self.seed)
    def test_mismatches(self):
        for key, value in [('date','2026-01-01'),('open_interest',1),('long',123),('net',1),('open_interest',True)]:
            s=copy.deepcopy(self.summary);s['official']['USD'][key]=value
            with self.assertRaises(ValueError): build(s,self.chart)
        s=copy.deepcopy(self.summary);del s['official']['USD']
        with self.assertRaises(ValueError): build(s,self.chart)
        h=copy.deepcopy(self.chart);h['USD']['netoi'][-1]=0
        with self.assertRaises(ValueError): build(self.summary,h)
if __name__=='__main__': unittest.main()
