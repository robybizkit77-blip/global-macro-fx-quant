from datetime import date, timedelta

from beta_52w_kernel_v1 import (
    BetaObservation,
    INSUFFICIENT_HISTORY,
    NOT_EVALUATED,
    READY_FOR_RESEARCH,
    normalize_iso_date,
    rolling_ols_52w,
    validate_weekly_panel,
)


def make_rows(n=60):
    start = date(2025, 1, 3)
    rows = []
    for i in range(n):
        x = float(i)
        y = 1.0 + 2.0 * x
        rows.append(
            BetaObservation(
                week=start + timedelta(days=7 * i),
                pair="EURUSD",
                y=y,
                x=x,
                fx_source="TEST_FX",
                rates_source="TEST_2Y",
            )
        )
    return rows


def test_date_normalization():
    assert normalize_iso_date("2025-5-8").isoformat() == "2025-05-08"
    assert normalize_iso_date("2025-05-08").isoformat() == "2025-05-08"


def test_52w_warmup_and_exact_ols():
    rows = make_rows()
    validate_weekly_panel(rows)
    estimates = rolling_ols_52w(rows)

    assert estimates[50].status == INSUFFICIENT_HISTORY
    assert estimates[51].status == READY_FOR_RESEARCH
    assert estimates[-1].n == 52
    assert abs(estimates[-1].alpha - 1.0) < 1e-12
    assert abs(estimates[-1].beta - 2.0) < 1e-12
    assert estimates[-1].b1_status == NOT_EVALUATED
    assert estimates[-1].b2_status == NOT_EVALUATED


def test_zero_variance_x_fails_closed():
    start = date(2025, 1, 3)
    rows = [
        BetaObservation(
            week=start + timedelta(days=7 * i),
            pair="USDJPY",
            y=float(i),
            x=1.0,
            fx_source="TEST_FX",
            rates_source="TEST_2Y",
        )
        for i in range(52)
    ]
    estimate = rolling_ols_52w(rows)[-1]
    assert estimate.status == INSUFFICIENT_HISTORY
    assert estimate.alpha is None
    assert estimate.beta is None


if __name__ == "__main__":
    test_date_normalization()
    test_52w_warmup_and_exact_ols()
    test_zero_variance_x_fails_closed()
    print("PASS beta 52W kernel")
