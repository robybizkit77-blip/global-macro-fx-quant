#!/usr/bin/env python3
"""Narrow strict-PIT patches for verified 2024 ONS GBP labour wording.

This wrapper preserves the existing collector unchanged and only adds exact,
period-specific first-release wording verified on official ONS releases for:
- reference month 2024-01 (November 2023 to January 2024), release 12 Mar 2024
- reference month 2024-02 (December 2023 to February 2024), release 16 Apr 2024
- reference month 2024-03 (January to March 2024), release 14 May 2024
- reference month 2024-04 (February to April 2024), release 11 Jun 2024
- reference month 2024-05 (March to May 2024), release 18 Jul 2024
- reference month 2024-06 (April to June 2024), release 13 Aug 2024
"""
from __future__ import annotations

import re

import materialize_gbp_labour_strict_pit_v1 as base

_ORIGINAL_HEADLINE = base.headline
_MARCH_TARGET = 'November 2023 to January 2024'
_APRIL_TARGET = 'December 2023 to February 2024'
_MAY_CANONICAL = 'January 2024 to March 2024'
_MAY_COMPACT = 'January to March 2024'
_JUNE_TARGET = 'February to April 2024'
_JULY_TARGET = 'March to May 2024'
_AUGUST_TARGET = 'April to June 2024'


def _headline_with_verified_2024_cases(text: str, periods: tuple[str, ...]) -> tuple[float, str]:
    if _MARCH_TARGET in periods:
        if not re.search(r'\bLabour market overview, UK:\s*March\s+2024\b', text, re.I):
            return _ORIGINAL_HEADLINE(text, periods)
        if base.release_date(text) != '2024-03-12':
            raise ValueError('ONS March 2024 overview release-date mismatch')
        matches = re.findall(
            r'\bThe UK unemployment rate \(for those aged 16 years and over\) was estimated at\s*'
            r'([0-9]+(?:\.[0-9]+)?)\s*%\s+in\s+November 2023 to January 2024\b', text, flags=re.I)
        values = list(dict.fromkeys(float(v) for v in matches))
        if len(values) != 1:
            raise ValueError(f'ambiguous or missing fixed ONS March 2024 unemployment headline: {values}')
        return values[0], _MARCH_TARGET

    if _APRIL_TARGET in periods:
        if re.search(r'\bLabour market overview, UK:\s*April\s+2024\b', text, re.I):
            if base.release_date(text) != '2024-04-16':
                raise ValueError('ONS April 2024 overview release-date mismatch')
            matches = re.findall(
                r'\bThe UK unemployment rate \(for those aged 16 years and over\) was estimated at\s*'
                r'([0-9]+(?:\.[0-9]+)?)\s*%\s+in\s+December 2023 to February 2024\b', text, flags=re.I)
            values = list(dict.fromkeys(float(v) for v in matches))
            if len(values) != 1:
                raise ValueError(f'ambiguous or missing fixed ONS April 2024 overview unemployment headline: {values}')
            return values[0], _APRIL_TARGET
        if re.search(r'\bEmployment in the UK:\s*April\s+2024\b', text, re.I):
            if base.release_date(text) != '2024-04-16':
                raise ValueError('ONS April 2024 companion release-date mismatch')
            matches = re.findall(
                r'\bThe UK unemployment rate for December 2023 to February 2024\s*\('
                r'([0-9]+(?:\.[0-9]+)?)%\)\s+is above estimates a year ago', text, flags=re.I)
            values = list(dict.fromkeys(float(v) for v in matches))
            if len(values) != 1:
                raise ValueError(f'ambiguous or missing fixed ONS April 2024 companion unemployment headline: {values}')
            return values[0], _APRIL_TARGET

    if _MAY_CANONICAL in periods and _MAY_COMPACT in periods:
        if re.search(r'\bLabour market overview, UK:\s*May\s+2024\b', text, re.I):
            if base.release_date(text) != '2024-05-14':
                raise ValueError('ONS May 2024 overview release-date mismatch')
            matches = re.findall(
                r'\bThe UK unemployment rate \(for people aged 16 years and over\) was estimated at\s*'
                r'([0-9]+(?:\.[0-9]+)?)\s*%\s+in\s+January to March 2024\b', text, flags=re.I)
            values = list(dict.fromkeys(float(v) for v in matches))
            if len(values) != 1:
                raise ValueError(f'ambiguous or missing fixed ONS May 2024 overview unemployment headline: {values}')
            return values[0], _MAY_COMPACT
        if re.search(r'\bEmployment in the UK:\s*May\s+2024\b', text, re.I):
            if base.release_date(text) != '2024-05-14':
                raise ValueError('ONS May 2024 companion release-date mismatch')
            matches = re.findall(
                r'\bThe UK unemployment rate for January to March 2024\s*\('
                r'([0-9]+(?:\.[0-9]+)?)%\)\s+is above estimates of a year ago', text, flags=re.I)
            values = list(dict.fromkeys(float(v) for v in matches))
            if len(values) != 1:
                raise ValueError(f'ambiguous or missing fixed ONS May 2024 companion unemployment headline: {values}')
            return values[0], _MAY_COMPACT

    if _JUNE_TARGET in periods:
        if re.search(r'\bLabour market overview, UK:\s*June\s+2024\b', text, re.I):
            if base.release_date(text) != '2024-06-11':
                raise ValueError('ONS June 2024 overview release-date mismatch')
            matches = re.findall(
                r'\bThe UK unemployment rate \(for people aged 16 years and over\) was estimated at\s*'
                r'([0-9]+(?:\.[0-9]+)?)\s*%\s+in\s+February to April 2024\b', text, flags=re.I)
            values = list(dict.fromkeys(float(v) for v in matches))
            if len(values) != 1:
                raise ValueError(f'ambiguous or missing fixed ONS June 2024 overview unemployment headline: {values}')
            return values[0], _JUNE_TARGET
        if re.search(r'\bEmployment in the UK:\s*June\s+2024\b', text, re.I):
            if base.release_date(text) != '2024-06-11':
                raise ValueError('ONS June 2024 companion release-date mismatch')
            matches = re.findall(r'\bUnemployment rate\s*\(aged 16\+\)\s*\|\s*([0-9]+(?:\.[0-9]+)?)%\b', text, flags=re.I)
            values = list(dict.fromkeys(float(v) for v in matches))
            if len(values) != 1:
                raise ValueError(f'ambiguous or missing fixed ONS June 2024 companion unemployment headline: {values}')
            return values[0], _JUNE_TARGET

    if _JULY_TARGET in periods:
        if re.search(r'\bLabour market overview, UK:\s*July\s+2024\b', text, re.I):
            if base.release_date(text) != '2024-07-18':
                raise ValueError('ONS July 2024 overview release-date mismatch')
            matches = re.findall(
                r'\bThe UK unemployment rate \(for people aged 16 years and over\) was estimated at\s*'
                r'([0-9]+(?:\.[0-9]+)?)\s*%\s+in\s+March to May 2024\b', text, flags=re.I)
            values = list(dict.fromkeys(float(v) for v in matches))
            if len(values) != 1:
                raise ValueError(f'ambiguous or missing fixed ONS July 2024 overview unemployment headline: {values}')
            return values[0], _JULY_TARGET
        if re.search(r'\bEmployment in the UK:\s*July\s+2024\b', text, re.I):
            if base.release_date(text) != '2024-07-18':
                raise ValueError('ONS July 2024 companion release-date mismatch')
            matches = re.findall(
                r'\bThe UK unemployment rate for March to May 2024\s*\('
                r'([0-9]+(?:\.[0-9]+)?)%\)\s+is above estimates of a year ago', text, flags=re.I)
            values = list(dict.fromkeys(float(v) for v in matches))
            if len(values) != 1:
                raise ValueError(f'ambiguous or missing fixed ONS July 2024 companion unemployment headline: {values}')
            return values[0], _JULY_TARGET

    if _AUGUST_TARGET in periods:
        if re.search(r'\bLabour market overview, UK:\s*August\s+2024\b', text, re.I):
            if base.release_date(text) != '2024-08-13':
                raise ValueError('ONS August 2024 overview release-date mismatch')
            matches = re.findall(
                r'\bThe UK unemployment rate \(for people aged 16 years and over\) was estimated at\s*'
                r'([0-9]+(?:\.[0-9]+)?)\s*%\s+in\s+April to June 2024\b', text, flags=re.I)
            values = list(dict.fromkeys(float(v) for v in matches))
            if len(values) != 1:
                raise ValueError(f'ambiguous or missing fixed ONS August 2024 overview unemployment headline: {values}')
            return values[0], _AUGUST_TARGET
        if re.search(r'\bEmployment in the UK:\s*August\s+2024\b', text, re.I):
            if base.release_date(text) != '2024-08-13':
                raise ValueError('ONS August 2024 companion release-date mismatch')
            matches = re.findall(
                r'\bThe UK unemployment rate for April to June 2024\s*\('
                r'([0-9]+(?:\.[0-9]+)?)%\)\s+is below estimates of a year ago', text, flags=re.I)
            values = list(dict.fromkeys(float(v) for v in matches))
            if len(values) != 1:
                raise ValueError(f'ambiguous or missing fixed ONS August 2024 companion unemployment headline: {values}')
            return values[0], _AUGUST_TARGET

    return _ORIGINAL_HEADLINE(text, periods)


base.headline = _headline_with_verified_2024_cases

if __name__ == '__main__':
    raise SystemExit(base.main())
