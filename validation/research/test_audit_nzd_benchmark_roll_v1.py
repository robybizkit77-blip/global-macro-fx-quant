import copy
import json
import unittest

from validation.research.audit_nzd_benchmark_roll_v1 import EVIDENCE, audit


class NzBenchmarkRollTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(EVIDENCE.read_text())

    def test_roll_not_misclassified_as_repricing(self):
        out = audit(self.data)
        self.assertEqual(out["quoted_2y_difference_bp"], 19)
        self.assertIsNone(out["comparable_same_instrument_change_bp"])
        self.assertFalse(out["eligible_for_pair_repricing"])

    def test_changing_identity_fails_closed(self):
        changed = copy.deepcopy(self.data)
        changed["currencies"]["NZD"]["observations"][1]["benchmark_2y"] = "May 2028"
        with self.assertRaises(AssertionError):
            audit(changed)

    def test_approval_must_stay_false(self):
        changed = copy.deepcopy(self.data)
        changed["currencies"]["NZD"]["canonical_rate_update_approved"] = True
        with self.assertRaises(AssertionError):
            audit(changed)


if __name__ == "__main__":
    unittest.main()
