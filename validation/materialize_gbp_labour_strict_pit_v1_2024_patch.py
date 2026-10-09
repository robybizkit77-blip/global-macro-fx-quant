#!/usr/bin/env python3
"""Narrow strict-PIT patch for the March 2024 ONS GBP labour wording.

This wrapper preserves the existing collector unchanged and only adds the
period-specific first-release wording verified on the official ONS March 2024
overview for reference month 2024-01 (November 2023 to January 2024).
"""
from __future__ import annotations

import re

import materialize_gbp_labour_strict_pit_v1 as base

_ORIGINAL_HEADLINE = base.headline
_TARGET_PERIOD = 'November 2023 to January 2024'


def _headline_with_march_2024(text: str, periods: tuple[str, ...]) -> tuple[float, str]:
    if _TARGET_PERIOD in periods:
        if not re.search(r'\bLabour market overview, UK:\s*March\s+2024\b', text, re.I):
            return _ORIGINAL_HEADLINE(text, periods)
        if base.release_date(text) != '2024-03-12':
            raise ValueError('ONS March 2024 overview release-date mismatch')
        # Exact first-release sentence verified on the official period-specific
        # overview. Keep this deliberately narrow rather than widening the
        # generic unemployment regex used for the full archive.
        matches = re.findall(
            r'\bThe UK unemployment rate \(for those aged 16 years and over\) was estimated at\s*'
            r'([0-9]+(?:\.[0-9]+)?)\s*%\s+in\s+November 2023 to January 2024\b',
            text,
            flags=re.I,
        )
        values = list(dict.fromkeys(float(v) for v in matches))
        if len(values) != 1:
            raise ValueError(f'ambiguous or missing fixed ONS March 2024 unemployment headline: {values}')
        return values[0], _TARGET_PERIOD
    return _ORIGINAL_HEADLINE(text, periods)


base.headline = _headline_with_march_2024

if __name__ == '__main__':
    raise SystemExit(base.main())
