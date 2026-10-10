#!/usr/bin/env python3
from __future__ import annotations

import re

import materialize_jpy_inflation_strict_pit_v1 as base

_original_parse_headline_yoy = base.parse_headline_yoy


def parse_headline_yoy_with_official_narrative_fallback(text: str) -> float:
    try:
        return _original_parse_headline_yoy(text)
    except ValueError as original_error:
        compact = re.sub(r"\s+", "", text)

        # Some archived Statistics Bureau PDFs have a broken embedded font on
        # page 1 under pypdf, while later pages remain readable. In those exact
        # releases the official narrative states the all-items YoY move as
        # previous month -> current month. Use only that uniquely labelled
        # national all-items sentence; otherwise fail closed.
        matches = list(
            re.finditer(
                r"総合の前年同月比の(上昇|下落)幅[^（]*（[^）]*?→[^）]*?([0-9]+(?:\.[0-9]+)?)%）",
                compact,
            )
        )
        if len(matches) != 1:
            raise original_error

        direction = matches[0].group(1)
        value = float(matches[0].group(2))
        return value if direction == "上昇" else -value


base.parse_headline_yoy = parse_headline_yoy_with_official_narrative_fallback

if __name__ == "__main__":
    raise SystemExit(base.main())
