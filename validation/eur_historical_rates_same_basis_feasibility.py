#!/usr/bin/env python3
"""Read-only feasibility audit for EUR historical 2Y/10Y rates on one official basis.

Source: ECB AAA euro-area central government bond zero-coupon spot curve,
Svensson model, daily observations. The 2Y and 10Y points are taken from the
same official curve family and aligned by observation date.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import urllib.request
from datetime import date
from pathlib import Path

START = date(2016, 1, 1)
BASE = "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.{series}?format=csvdata&startPeriod=2016-01-01"
SERIES = {"2Y": "SR_2Y", "10Y": "SR_10Y"}


def fetch(series: str):
    url = BASE.format(series=series)
    req = urllib.request.Request(url, headers={"User-Agent": "GMFQ-EUR-rates-PIT-audit/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode("utf-8-sig")
        status = getattr(r, "status", 200)
    if status != 200:
        raise RuntimeError(f"HTTP {status} for {series}")
    rows = list(csv.DictReader(io.StringIO(raw)))
    out = {}
    metadata = {}
    for row in rows:
        d = row.get("TIME_PERIOD") or row.get("TIME_PERIOD_START")
        v = row.get("OBS_VALUE")
        if not d or v in (None, ""):
            continue
        try:
            dd = date.fromisoformat(d[:10])
            vv = float(v)
        except Exception:
            continue
        if dd < START or not (math.isfinite(vv)):
            continue
        out[dd.isoformat()] = vv
        for k in ("TITLE", "TITLE_COMPL", "UNIT", "UNIT_MULT", "FREQ", "DATA_TYPE_FM", "REF_AREA"):
            if row.get(k) not in (None, ""):
                metadata[k] = row.get(k)
    return url, out, metadata


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    u2, y2, m2 = fetch(SERIES["2Y"])
    u10, y10, m10 = fetch(SERIES["10Y"])
    if not y2 or not y10:
        raise SystemExit("Missing ECB history")

    d2 = set(y2)
    d10 = set(y10)
    common = sorted(d2 & d10)
    only2 = sorted(d2 - d10)
    only10 = sorted(d10 - d2)
    paired = [(d, y2[d], y10[d], y10[d] - y2[d]) for d in common]

    first = common[0]
    last = common[-1]
    checks = {
        "same_official_authority": True,
        "same_curve_family": True,
        "same_frequency_daily": (m2.get("FREQ") in (None, "B") and m10.get("FREQ") in (None, "B")),
        "starts_by_2016_01_04": first <= "2016-01-04",
        "at_least_2500_paired_observations": len(common) >= 2500,
        "date_alignment_complete": len(only2) == 0 and len(only10) == 0,
        "all_values_finite": all(math.isfinite(a) and math.isfinite(b) for _, a, b, _ in paired),
        "latest_observation_recent": (date.today() - date.fromisoformat(last)).days <= 10,
    }
    passed = all(checks.values())

    out = {
        "schema": "GMFQ_EUR_HISTORICAL_RATES_SAME_BASIS_FEASIBILITY_V1",
        "status": "PASS" if passed else "FAIL",
        "mode": "READ_ONLY_AUDIT",
        "authority": "European Central Bank",
        "source_family": "ECB AAA euro-area central government bond zero-coupon spot curve, Svensson model",
        "series": {
            "2Y": {"key": SERIES["2Y"], "url": u2, "metadata": m2, "observations": len(y2)},
            "10Y": {"key": SERIES["10Y"], "url": u10, "metadata": m10, "observations": len(y10)},
        },
        "window": {
            "requested_start": START.isoformat(),
            "first_common_observation": first,
            "latest_common_observation": last,
            "paired_observations": len(common),
            "2y_only_dates": len(only2),
            "10y_only_dates": len(only10),
            "2y_only_examples": only2[:10],
            "10y_only_examples": only10[:10],
        },
        "latest_sample": {
            "date": paired[-1][0],
            "2Y": paired[-1][1],
            "10Y": paired[-1][2],
            "curve_10Y_minus_2Y_pp": paired[-1][3],
        },
        "checks": checks,
        "historical_rates_assessment": "EUR historical 2Y/10Y same-basis reconstruction is feasible from one official ECB daily curve family." if passed else "EUR historical rates same-basis requirements not fully proven.",
        "changes_live_data": False,
        "changes_engine_rules": False,
        "changes_oos_baseline": False,
    }

    Path(args.output).write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
