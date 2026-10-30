#!/usr/bin/env python3
"""Independent 08:00 Europe/Rome delivery receipt for the Pages publisher.

Unlike the parent orchestrator SLA, this evaluates the publisher's own
pre-write source gate AND exact public HTTP proof. It observes real public
delivery even when an independent producer triggers the publisher. Verification observed after 08:00 cannot prove when files first became available.\nOnly verified-before-08:00 observations certify on-time service. This is read-only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from verify_pages_http_delivery_v1 import FILES

ROME = ZoneInfo("Europe/Rome")
TARGET = dt.time(8, 0)


def parse_aware(value: object) -> dt.datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None


def evaluate(source: dict | None, public: dict | None, now: dt.datetime, *, expected_files: tuple[str, ...] = FILES) -> dict:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone aware")
    local_now = now.astimezone(ROME)
    checked = parse_aware(source.get("checked_at_rome")) if isinstance(source, dict) else None
    verified = parse_aware(public.get("verified_at_utc")) if isinstance(public, dict) else None
    checked_rome = checked.astimezone(ROME) if checked else None
    verified_rome = verified.astimezone(ROME) if verified else None
    morning = isinstance(source, dict) and source.get("morning_gate_required") is True
    source_ok = bool(
        morning
        and source.get("schema") == "GMFQ_PAGES_MORNING_SOURCE_GATE_V1"
        and source.get("status") == "PASS_MORNING_SOURCES_VERIFIED"
        and source.get("critical_daily_problems") == []
        and checked_rome is not None
        and checked_rome.weekday() < 5
        and checked_rome.date() == local_now.date()
    )
    rows = public.get("checks") if isinstance(public, dict) else None
    paths = [r.get("path") for r in rows] if isinstance(rows, list) and all(isinstance(r, dict) for r in rows) else []
    public_ok = bool(
        isinstance(public, dict)
        and public.get("status") == "PASS"
        and public.get("basis") == "PUBLIC_HTTP_200_EXACT_SHA256"
        and public.get("conclusion") == "ALL_PUBLIC_FILES_MATCH"
        and len(paths) == len(expected_files)
        and set(paths) == set(expected_files)
        and all(r.get("http_200_and_sha256_match") is True and r.get("http_status") == 200
                and isinstance(r.get("expected_sha256"), str)
                and len(r["expected_sha256"]) == 64
                and r.get("public_sha256") == r["expected_sha256"]
                for r in rows)
        and verified_rome is not None
        and checked_rome is not None
        and checked_rome <= verified_rome <= local_now
        and verified_rome.date() == checked_rome.date()
    )
    if not morning:
        status = "NOT_APPLICABLE_NO_MORNING_SOURCE_GATE"
    elif not source_ok:
        status = "FAIL_MORNING_SOURCE_GATE"
    elif not public_ok:
        status = "FAIL_PUBLIC_HTTP_UNVERIFIED"
    else:
        deadline = dt.datetime.combine(checked_rome.date(), TARGET, tzinfo=ROME)
        status = "PASS_PUBLIC_HTTP_BY_0800" if verified_rome <= deadline else "VERIFIED_AFTER_0800_DELIVERY_TIME_UNPROVEN"
    deadline = dt.datetime.combine(local_now.date(), TARGET, tzinfo=ROME)
    watch = source.get("issuer_policy_watch") if isinstance(source, dict) else None
    watch = watch if isinstance(watch, dict) else {}
    watch_status = watch.get("status", "NOT_CERTIFIED")
    pending = watch.get("currencies") if isinstance(watch.get("currencies"), list) else []
    # HTTP files may be available by 08:00 while a same-day central-bank
    # decision is still unresolved. Keep delivery and policy facts separate.
    cb_policy_clear_at_observation = bool(
        source_ok and watch_status == "NO_PENDING_SAME_DAY_CB_DECISION"
    )
    return {
        "schema": "GMFQ_INDEPENDENT_PAGES_0800_SLA_V1",
        "status": status,
        "target_timezone": "Europe/Rome",
        "target_rome": deadline.isoformat(timespec="seconds"),
        "source_checked_at_rome": checked_rome.isoformat(timespec="seconds") if checked_rome else None,
        "public_verified_at_rome": verified_rome.isoformat(timespec="seconds") if verified_rome else None,
        "evaluated_at_rome": local_now.isoformat(timespec="seconds"),
        "source_pass": source_ok,
        "on_time_delivery_proven": status == "PASS_PUBLIC_HTTP_BY_0800",
        "cb_policy_watch_status": watch_status,
        "cb_policy_pending_currencies": pending,
        "cb_policy_no_pending_same_day_decision_proven": cb_policy_clear_at_observation,
        "http_delivery_does_not_certify_cb_release": True,
        "verified_after_deadline": bool(public_ok and verified_rome > deadline),
        "public_exact_bytes_pass": public_ok,
        "verified_file_count": len(paths),
        "independent_of_parent_orchestrator": True,
        "scope": "EXACT_PUBLIC_HTTP_FILES_AND_MORNING_SOURCE_GATE_ONLY",
        "model_beta_forward_effect": "NONE",
        "note": "The receipt certifies exact public HTTP files, not a same-day CB decision. A post-08:00 HTTP read cannot prove first availability was late. Does not guarantee future cron timing.",
    }


def read_json(path: str) -> dict | None:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--public", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--as-of", help="Aware ISO timestamp for deterministic tests only")
    args = parser.parse_args()
    now = dt.datetime.fromisoformat(args.as_of) if args.as_of else dt.datetime.now(dt.timezone.utc)
    report = evaluate(read_json(args.source), read_json(args.public), now)
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("PAGES_INDEPENDENT_0800_SLA", json.dumps(report, sort_keys=True))
    return 0  # Read-only evidence must not prevent legitimate late recovery.


if __name__ == "__main__":
    raise SystemExit(main())
