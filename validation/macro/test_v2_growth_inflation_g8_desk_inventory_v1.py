import copy,json,unittest
from datetime import date
from validation.macro.v2_shadow_features_v1 import ROOT
from validation.macro.v2_growth_inflation_g8_desk_inventory_v1 import inspect
class G8GrowthInflationInventoryTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.data=json.loads((ROOT/"live_data/sections/MACRO_SERIES.json").read_text())
 def test_all_eight_by_two_without_scoring(self):
  r=inspect(self.data)
  self.assertEqual(len(r["rows"]),16)
  self.assertEqual({x["currency"] for x in r["rows"]},set(self.data))
  self.assertEqual(r["certified_first_release_slots"],0)
  self.assertFalse(r["economic_score_computed"])
  self.assertFalse(r["eligible_for_backtest"])
  self.assertFalse(r["safe_to_publish_new_D"])
  self.assertFalse(r["safe_to_update_pair_theses"])
  self.assertFalse(r["writes_live_data"])
  self.assertTrue(all(x["release_timestamp_first_vintage_verified"] is False and
                      x["growth_or_inflation_macro_score"] is None for x in r["rows"]))
 def test_do_not_mutate_original_data(self):
  x=copy.deepcopy(self.data)
  self.assertEqual(inspect(x),inspect(x))
  self.assertEqual(x,self.data)
 def test_no_future_leakage(self):
  x=copy.deepcopy(self.data)
  for v in x["USD"]:
   if v.get("category")=="Crescita":
    v["last_date"]="2099-01-01"
  with self.assertRaises(ValueError):inspect(x)
if __name__=="__main__":unittest.main()
