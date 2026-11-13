"""Fail-closed mirror source contract tests, without network or source vintages."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from validation.publishing.check_fxv2_mirror_source_contract_v1 import (
    ROOT, REL, FILES, validate,
)


class SourceMirrorContractTest(unittest.TestCase):
    def test_current_approved_main_v2_research_is_publishable_as_research(self):
        outcome = validate(ROOT)
        self.assertEqual(outcome["status"], "SOURCE_CONTRACT_PASS")
        self.assertEqual(outcome["files"], 4)
        self.assertFalse(outcome["core_promotion"])
        self.assertFalse(outcome["source_freshness_certified"])

    def fixture(self, root, edit):
        target = root / REL
        target.mkdir(parents=True, exist_ok=True)
        for name in FILES:
            data = json.loads((ROOT / REL / name).read_text(encoding="utf-8"))
            edit(name, data)
            (target / name).write_text(json.dumps(data), encoding="utf-8")

    def test_invalid_schema_or_forced_core_promotion_fails(self):
        for change in ("schema", "engine", "signals", "pair_count"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as dir:
                def mutate(name, data):
                    if change == "schema" and name == "ois-pricing-snapshot.json":
                        data["schema"] = "INVALID"
                    if change == "engine" and name == "pricing-relative-28pairs-research.json":
                        data["eligible_for_fx_engine"] = True
                    if change == "signals" and name == "quant-temporal-readiness-v1.json":
                        data["eligible_for_signals"] = True
                    if change == "pair_count" and name == "pricing-relative-28pairs-research.json":
                        data["pairs"].pop(next(iter(data["pairs"])))
                self.fixture(Path(dir), mutate)
                with self.assertRaises(ValueError):
                    validate(Path(dir))

    def test_missing_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as dir:
            self.fixture(Path(dir), lambda _name, _data: None)
            (Path(dir) / REL / "ois-pricing-snapshot.json").unlink()
            with self.assertRaises(ValueError):
                validate(Path(dir))


if __name__ == "__main__":
    unittest.main()
