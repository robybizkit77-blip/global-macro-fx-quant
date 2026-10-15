#!/usr/bin/env python3
import datetime as dt
import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("rate_beta_observational_v1.py")
spec = importlib.util.spec_from_file_location("rate_beta_observational_v1", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def make_rows(n, beta=2.0):
    start = dt.date(2025, 1, 3)
    rows = []
    for i in range(n):
        week = start + dt.timedelta(days=7 * i)
        x = (i - 20) / 100.0
        y = 0.01 + beta * x
        rows.append((week, y, x))
    return rows


def main():
    short = mod.compute_pair("EURUSD", make_rows(51))
    assert short["status"] == "INSUFFICIENT_HISTORY"
    assert short["beta_current"] is None

    first = mod.compute_pair("EURUSD", make_rows(52))
    assert first["status"] == "READY_OBSERVATIONAL"
    assert abs(first["beta_current"] - 2.0) < 1e-12
    assert first["beta_previous"] is None
    assert first["beta_change"] is None

    changed = mod.compute_pair("EURUSD", make_rows(53))
    assert changed["status"] == "READY_OBSERVATIONAL"
    assert abs(changed["beta_current"] - 2.0) < 1e-12
    assert abs(changed["beta_previous"] - 2.0) < 1e-12
    assert abs(changed["beta_change"]) < 1e-12
    assert changed["b1_status"] == mod.B1_STATUS
    assert changed["b2_status"] == mod.B2_STATUS
    assert changed["regime_status"] == mod.REGIME_STATUS

    flat_x = [(r[0], r[1], 1.0) for r in make_rows(52)]
    zero_var = mod.compute_pair("EURUSD", flat_x)
    assert zero_var["status"] == "BETA_UNDEFINED_ZERO_VARIANCE"
    print("RATE_BETA observational plumbing: PASS")


if __name__ == "__main__":
    main()
