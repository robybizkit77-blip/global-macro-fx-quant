from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Sequence

WINDOW_WEEKS = 52
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
READY_FOR_RESEARCH = "READY_FOR_RESEARCH"
NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True)
class BetaObservation:
    week: date
    pair: str
    y: float
    x: float
    fx_source: str
    rates_source: str


@dataclass(frozen=True)
class BetaEstimate:
    pair: str
    as_of: date
    n: int
    alpha: float | None
    beta: float | None
    status: str
    b1_status: str = NOT_EVALUATED
    b2_status: str = NOT_EVALUATED


def normalize_iso_date(raw: str) -> date:
    """Normalize YYYY-M-D / YYYY-MM-DD into a real date.

    This intentionally covers the known JPY maintenance case (e.g. 2025-5-8)
    without changing any economic data or inferred timestamp semantics.
    """
    parts = raw.strip().split("-")
    if len(parts) != 3:
        raise ValueError(f"invalid date: {raw!r}")
    year, month, day = (int(part) for part in parts)
    return date(year, month, day)


def load_panel_csv(path: str | Path) -> list[BetaObservation]:
    """Load an already PIT-certified weekly panel.

    Required columns are deliberately generic: `y` and `x` are the frozen
    dependent/explanatory transforms supplied by the preregistered research
    spec. This kernel does not invent or alter their economic definitions.
    """
    required = {"week", "pair", "y", "x", "fx_source", "rates_source"}
    observations: list[BetaObservation] = []
    seen: set[tuple[str, date]] = set()

    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or set(reader.fieldnames) != required:
            raise ValueError(f"panel columns must be exactly {sorted(required)}")

        for row in reader:
            week = normalize_iso_date(row["week"])
            pair = row["pair"].strip().upper()
            if len(pair) != 6 or not pair.isalpha():
                raise ValueError(f"invalid pair: {pair!r}")

            key = (pair, week)
            if key in seen:
                raise ValueError(f"duplicate observation: {pair} {week.isoformat()}")
            seen.add(key)

            y = float(row["y"])
            x = float(row["x"])
            if not (math.isfinite(y) and math.isfinite(x)):
                raise ValueError(f"non-finite input: {pair} {week.isoformat()}")

            fx_source = row["fx_source"].strip()
            rates_source = row["rates_source"].strip()
            if not fx_source or not rates_source:
                raise ValueError(f"missing provenance: {pair} {week.isoformat()}")

            observations.append(
                BetaObservation(
                    week=week,
                    pair=pair,
                    y=y,
                    x=x,
                    fx_source=fx_source,
                    rates_source=rates_source,
                )
            )

    observations.sort(key=lambda item: (item.pair, item.week))
    return observations


def validate_weekly_panel(rows: Sequence[BetaObservation]) -> None:
    """Fail closed on duplicate/non-monotonic/obviously non-weekly panels."""
    by_pair: dict[str, list[BetaObservation]] = {}
    for row in rows:
        by_pair.setdefault(row.pair, []).append(row)

    for pair, observations in by_pair.items():
        ordered = sorted(observations, key=lambda item: item.week)
        for previous, current in zip(ordered, ordered[1:]):
            if current.week <= previous.week:
                raise ValueError(f"non-monotonic dates for {pair}")
            gap_days = (current.week - previous.week).days
            if gap_days < 5 or gap_days > 10:
                raise ValueError(
                    f"irregular weekly calendar for {pair}: "
                    f"{previous.week.isoformat()} -> {current.week.isoformat()}"
                )


def rolling_ols_52w(rows: Iterable[BetaObservation]) -> list[BetaEstimate]:
    """Run the frozen 52-observation rolling OLS kernel.

    No B1/B2 interpretation is performed here. Those diagnostics stay
    NOT_EVALUATED until their exact preregistered economic definitions are
    recovered and separately reviewed.
    """
    by_pair: dict[str, list[BetaObservation]] = {}
    for row in rows:
        by_pair.setdefault(row.pair, []).append(row)

    estimates: list[BetaEstimate] = []
    for pair, observations in by_pair.items():
        ordered = sorted(observations, key=lambda item: item.week)
        for index, current in enumerate(ordered):
            n_available = index + 1
            if n_available < WINDOW_WEEKS:
                estimates.append(
                    BetaEstimate(
                        pair=pair,
                        as_of=current.week,
                        n=n_available,
                        alpha=None,
                        beta=None,
                        status=INSUFFICIENT_HISTORY,
                    )
                )
                continue

            window = ordered[index + 1 - WINDOW_WEEKS : index + 1]
            xs = [row.x for row in window]
            ys = [row.y for row in window]
            x_mean = sum(xs) / WINDOW_WEEKS
            y_mean = sum(ys) / WINDOW_WEEKS
            sxx = sum((value - x_mean) ** 2 for value in xs)

            if sxx == 0:
                estimates.append(
                    BetaEstimate(
                        pair=pair,
                        as_of=current.week,
                        n=WINDOW_WEEKS,
                        alpha=None,
                        beta=None,
                        status=INSUFFICIENT_HISTORY,
                    )
                )
                continue

            sxy = sum(
                (x_value - x_mean) * (y_value - y_mean)
                for x_value, y_value in zip(xs, ys)
            )
            beta = sxy / sxx
            alpha = y_mean - beta * x_mean
            estimates.append(
                BetaEstimate(
                    pair=pair,
                    as_of=current.week,
                    n=WINDOW_WEEKS,
                    alpha=alpha,
                    beta=beta,
                    status=READY_FOR_RESEARCH,
                )
            )

    return estimates
