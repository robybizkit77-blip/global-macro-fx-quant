import hashlib
import json
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from validation.macro.archive_chf_labour_snb_editions_v1 import SCHEMA, archive_edition
from validation.macro.capture_chf_labour_snb_vintage_v1 import LABEL, URL

FOUND = {"editionDate": "20261021_0900", "publicSinceDate": "20261021_0900"}
NEXT = {"editionDate": "20261123_0900", "publicSinceDate": "20261123_0900"}


def source():
    values = [
        {"date": f"{2024 + month // 12:04d}-{month % 12 + 1:02d}", "value": 2.7 + month * 0.01}
        for month in range(33)
    ]
    raw = json.dumps({"timeseries": [{
        "header": [{"dim": "Overview", "dimItem": LABEL}],
        "values": values,
    }]}).encode()
    observed = datetime.fromisoformat("2026-11-20T11:10:00+00:00")
    return raw, {}, observed, observed, URL


class ArchiveSnbTests(unittest.TestCase):
    def test_preserves_exact_window_and_known_at_date_and_skips_existing_edition(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            fetch = Mock(return_value=source())
            status, path = archive_edition(directory, read_metadata=lambda: FOUND, read_source=fetch)
            self.assertEqual(status, "RECORDED")
            self.assertEqual(path.name, "20261021_0900--20261021_0900.json")
            frozen = path.read_bytes()
            receipt = json.loads(frozen)
            self.assertEqual(receipt["schema"], SCHEMA)
            self.assertEqual(receipt["available_to_research_from_utc"], "2026-11-20T11:10:00+00:00")
            self.assertEqual(receipt["snb_metadata_as_reported"], FOUND)
            values = receipt["observations_in_this_edition"]
            self.assertEqual(len(values), 25)
            self.assertEqual((values[0]["period"], values[-1]["period"]), ("2024-09", "2026-09"))
            meta = receipt["source_capture"]
            self.assertEqual(meta["raw_payload_sha256"], hashlib.sha256(source()[0]).hexdigest())
            self.assertFalse(meta["first_release_exact_value_certified"])
            self.assertIsNone(meta["first_release_instant_utc"])
            self.assertEqual(archive_edition(directory, read_metadata=lambda: FOUND, read_source=fetch),
                             ("ALREADY_ARCHIVED", path))
            fetch.assert_called_once()
            self.assertEqual(path.read_bytes(), frozen)

    def test_changed_edition_during_download_cannot_be_joined(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            read_metadata = Mock(side_effect=[FOUND, NEXT])
            with self.assertRaisesRegex(ValueError, "different edition during retrieval"):
                archive_edition(directory, read_metadata=read_metadata, read_source=source)
            self.assertEqual(list(directory.iterdir()), [])

    def test_invalid_metadata_rejected_before_data_download(self):
        with tempfile.TemporaryDirectory() as temp:
            fetch = Mock()
            with self.assertRaisesRegex(ValueError, "Invalid SNB edition clock"):
                archive_edition(Path(temp), read_metadata=lambda: {"editionDate": "../"}, read_source=fetch)
            fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
