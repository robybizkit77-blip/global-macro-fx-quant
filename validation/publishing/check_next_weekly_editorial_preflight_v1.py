#!/usr/bin/env python3
"""Editorial publication preflight for FOUR newly scheduled Sunday report types.

Checks only that a fresh HTML edition has a real reference date, an intact
canonical editorial skeleton and attributable sources. It CANNOT certify
individual market facts, bank forecasts, macro interpretations, model
inference, approval, visual matching or ChatGPT-to-GitHub automation.
Absence of a new report is reported as NOT_PRODUCED, never as delivered.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
from difflib import SequenceMatcher
from html import unescape
import json
from pathlib import Path
import re

from validation.publishing.check_next_research_library_delivery_v1 import (
    ROOT, DIRECTORY, BLOCKED, parse_date,
)

MIN_DATE = date(2026, 11, 13)
G8 = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
MONTHS_IT = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
             "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre")
TEMPLATES = {
    "bank": ("Weekly_Bank_FX_Report_",
             "Weekly_Bank_FX_Report_2026-11-06_DARK_DESK_NARRATIVO_V5.html", 22000),
    "cb": ("Weekly_CB_Sentiment_Report_",
           "Weekly_CB_Sentiment_Report_2026-11-06_DARK_RESEARCH_DESK_WANT_CAN_V4_PALETTE.html", 25000),
    "cross": ("Weekly_Global_Macro_Strength_Cross_Asset_",
              "Weekly_Global_Macro_Strength_Cross_Asset_2026-10-17_DARK_EDITORIAL_PRO_CLEAN.html", 13000),
    "pairs": ("Weekly_FX_Pair_Selection_",
              "Weekly_FX_Pair_Selection_Conviction_2026-10-17.html", 9000),
}
SOURCE_URI = re.compile(r"""href\s*=\s*["']https?://[^"']+["']""", re.I)
PAIR = re.compile(
    r"\b(USD|EUR|GBP|JPY|CHF|CAD|AUD|NZD)[/\-]?"
    r"(USD|EUR|GBP|JPY|CHF|CAD|AUD|NZD)\b", re.I)
PLACEHOLDER = re.compile(
    r"\blorem ipsum\b|\bTODO\s*:|\bTBD\b|"
    r"\[(?:inserire|add source|placeholder)[^\]]*\]", re.I)


def body_text(html: str) -> str:
    no_decor = re.sub(r"<(?:style|script)\b[^>]*>.*?</(?:style|script)\s*>",
                      " ", html, flags=re.I | re.S)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", no_decor))).strip()


def normalized_for_reskin(html: str) -> str:
    text = body_text(html).lower()
    text = re.sub(r"\b20\d{2}-\d{2}-\d{2}\b", "<date>", text)
    text = re.sub(
        r"\b\d{1,2}\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|"
        r"luglio|agosto|settembre|ottobre|novembre|dicembre)\s+20\d{2}\b",
        "<date>", text)
    text = re.sub(r"\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|"
                  r"sep|oct|nov|dec)\s+20\d{2}\b", "<date>", text)
    return re.sub(r"\s+", " ", text).strip()


def check_edition(root: Path, category: str, candidate: Path,
                  latest_allowed: date | None = None) -> dict:
    if category not in TEMPLATES:
        raise ValueError(f"UNRECOGNIZED_TYPE:{category}")
    prefix, template_name, minimum = TEMPLATES[category]
    name = candidate.name
    if not (name.startswith(prefix) and name.lower().endswith(".html")):
        raise ValueError(f"UNEXPECTED_WEEKLY_FILENAME:{name}")
    if BLOCKED.search(name):
        raise ValueError(f"UNAPPROVED_WEEKLY_FILENAME:{name}")
    day_str = parse_date(name)
    if day_str is None:
        raise ValueError(f"WEEKLY_DATE_INVALID:{name}")
    day = date.fromisoformat(day_str)
    if day < MIN_DATE or day.weekday() != 4:
        raise ValueError(f"NOT_A_CLOSED_FRIDAY_WEEK:{name}")
    if latest_allowed and day > latest_allowed:
        raise ValueError(f"WEEKLY_DATE_IN_FUTURE:{name}")
    raw = candidate.read_bytes()
    html = raw.decode("utf-8")
    if (len(raw) < minimum or
            not re.search(r"<!doctype\s+html", html[:100], re.I) or
            not re.search(r"<html\b", html[:300], re.I) or
            not re.search(r"</html>\s*$", html, re.I) or
            not re.search(r"<style\b[^>]*>.*?</style>", html, re.I | re.S)):
        raise ValueError(f"WEEKLY_HTML_OR_STYLE_INCOMPLETE:{name}")
    title = re.search(r"<title\b[^>]*>(.*?)</title>", html, re.I | re.S)
    if not title:
        raise ValueError(f"WEEKLY_TITLE_MISSING:{name}")
    title_text = body_text(title.group(1)).lower()
    title_date = f"{day.day} {MONTHS_IT[day.month - 1]} {day.year}"
    if title_date not in title_text and day_str not in title_text:
        raise ValueError(f"WEEKLY_TITLE_REFERENCE_DATE_MISMATCH:{name}")
    text = body_text(html)
    if PLACEHOLDER.search(text) or len(text) < 3400:
        raise ValueError(f"WEEKLY_UNFINISHED_EDITORIAL:{name}")
    # This is a *minimum attributable references* gate, NOT independent
    # verification that any bank or market forecast in the HTML is correct.
    sources = len(SOURCE_URI.findall(html))
    if sources < (3 if category in ("bank", "cb") else 1):
        raise ValueError(f"WEEKLY_ATTRIBUTABLE_SOURCE_LINKS_MISSING:{name}")
    if not re.search(r"fonti|sources|riferimenti", text, re.I):
        raise ValueError(f"WEEKLY_SOURCE_METHODOLOGY_MISSING:{name}")
    if category in ("bank", "cb"):
        for currency in G8:
            if not re.search(r"\b" + currency + r"\b", text):
                raise ValueError(f"WEEKLY_G8_COVERAGE_MISSING:{category}:{currency}")
        if category == "cb" and not re.search(r"WANT", text, re.I):
            raise ValueError(f"WEEKLY_CB_WANT_MISSING:{name}")
        if category == "cb" and not re.search(r"CAN", text, re.I):
            raise ValueError(f"WEEKLY_CB_CAN_MISSING:{name}")
    elif category == "cross":
        for label, pattern in (
            ("equity", r"nasdaq|s&p\s*500|azionar"),
            ("rates", r"treasury|2Y|10Y|rendiment"),
            ("credit", r"\bHY\b|credito|spread"),
            ("commodities", r"oro|gold|WTI|brent|petrolio"),
        ):
            if not re.search(pattern, text, re.I):
                raise ValueError(f"WEEKLY_CROSS_ASSET_MISSING:{label}")
    else:
        pairs = {x + y for x, y in PAIR.findall(text.upper()) if x != y}
        nonusd = [p for p in pairs if "USD" not in p]
        if len(pairs) < 4 or len(nonusd) < 2:
            raise ValueError(f"WEEKLY_FX_SELECTION_NOT_DIVERSIFIED:{name}")
        for label, pattern in (
            ("thesis", r"\bview\b|tesi|scenario"),
            ("timing", r"setup|trigger|conferma"),
            ("invalid", r"invalid|invalida|rischio"),
        ):
            if not re.search(pattern, text, re.I):
                raise ValueError(f"WEEKLY_PAIR_ANALYSIS_MISSING:{label}")

    template = (root / DIRECTORY / template_name)
    if not template.exists():
        raise ValueError(f"CANONICAL_TEMPLATE_NOT_AVAILABLE:{template_name}")
    older = normalized_for_reskin(template.read_text(encoding="utf-8"))
    current = normalized_for_reskin(html)
    similarity = SequenceMatcher(None, older, current, autojunk=True).ratio()
    if similarity >= 0.98:
        raise ValueError(f"REPORT_DATE_ONLY_REPRINT:{name}")

    template_css = re.search(
        r"<style\b[^>]*>(.*?)</style>",
        template.read_text(encoding="utf-8"), re.I | re.S)
    current_css = re.search(r"<style\b[^>]*>(.*?)</style>", html, re.I | re.S)
    same_css = bool(template_css and current_css and
                    template_css.group(1) == current_css.group(1))
    return {
        "type": category, "filename": name, "reference_friday": day_str,
        "status": "STRUCTURAL_EDITORIAL_PREFLIGHT_PASS",
        "source_links_observed": sources,
        "canonical_css_identical": same_css,
        "visual_match_certified": False,
        "market_facts_verified": False,
        "publisher_approval_verified": False,
    }


def scan(root: Path = ROOT, latest_allowed: date | None = None) -> dict:
    files = root / DIRECTORY
    if not files.is_dir():
        raise ValueError("WEEKLY_REPORT_DIRECTORY_NOT_PRESENT")
    results = []
    latest_allowed = latest_allowed or datetime.now().astimezone().date()
    for category, (prefix, _, _) in TEMPLATES.items():
        candidates = []
        for path in files.glob(prefix + "*.html"):
            date_str = parse_date(path.name)
            if date_str and date_str >= MIN_DATE.isoformat():
                candidates.append(path)
        if not candidates:
            results.append({"type": category, "status": "NOT_YET_PRODUCED"})
            continue
        checks = [check_edition(root, category, p, latest_allowed)
                  for p in sorted(candidates)]
        results.append(max(checks, key=lambda x: (x["reference_friday"], x["filename"])))
    return {
        "status": "WEEKLY_STRUCTURAL_PREFLIGHT_ONLY",
        "expected_new_types": len(TEMPLATES),
        "new_files_validated": sum(x["status"] == "STRUCTURAL_EDITORIAL_PREFLIGHT_PASS"
                                   for x in results),
        "new_types_not_yet_produced": sum(x["status"] == "NOT_YET_PRODUCED"
                                          for x in results),
        "results": results, "report_generation_certified": False,
        "transfer_from_chatgpt_certified": False,
        "visual_and_data_facts_certified": False,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--as-of", help="Rome Friday/source cutoff date override for tests")
    args = p.parse_args()
    date_limit = date.fromisoformat(args.as_of) if args.as_of else None
    print("NEXT_SUNDAY_WEEKLY_EDITORIAL_PREFLIGHT",
          json.dumps(scan(latest_allowed=date_limit), ensure_ascii=False))


if __name__ == "__main__":
    main()
