#!/usr/bin/env python3
"""Five-feed parity regression, including stale and missing mirrors."""
from __future__ import annotations

import pathlib
import tempfile

from verify_control_room_market_delivery_v1 import FILES, branch_parity


def main():
    assert len(FILES) == 5 and len(set(FILES)) == len(FILES)
    assert {x.rsplit("/", 1)[-1] for x in FILES} == {
        "NATIVE_RATES_DATA.json", "V250_COT_CHART_DATA.json",
        "PAIR_SETUP_OPERATIONAL_VIEW.json", "ECB_G8_PRICE_HISTORY.json",
        "DXY_SYNTHETIC_ECB.json",
    }
    with tempfile.TemporaryDirectory() as temp:
        root = pathlib.Path(temp)
        canonical = {}
        for i, path in enumerate(FILES):
            p = root / path
            p.parent.mkdir(parents=True, exist_ok=True)
            canonical[path] = ("verified-feed-" + str(i)).encode()
            p.write_bytes(canonical[path])
        assert branch_parity(root, reader=canonical.__getitem__)["status"] == "PASS"
        # A changed body, even if valid JSON, must fail.
        mismatch = dict(canonical)
        mismatch[FILES[3]] = b"old-public-copy"
        report = branch_parity(root, reader=mismatch.__getitem__)
        assert report["status"] == "FAIL"
        assert [x["path"] for x in report["checks"] if not x["match"]] == [FILES[3]]
        # A missing public file must fail closed, not silently be skipped.
        missing = dict(canonical)
        del missing[FILES[4]]
        report = branch_parity(root, reader=lambda path: missing[path] if path in missing else (_ for _ in ()).throw(OSError("file missing")))
        assert report["status"] == "FAIL"
        assert report["checks"][-1]["error"]
    print("CONTROL_ROOM_MARKET_FIVE_MIRRORS_SHA_REGRESSION_PASS")


if __name__ == "__main__":
    main()
