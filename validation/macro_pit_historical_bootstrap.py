#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import pathlib
import subprocess
import sys
import tempfile
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERIES_PATH = ROOT / "live_data/sections/MACRO_SERIES.json"
HEAT_PATH = ROOT / "live_data/sections/MACRO_THERMOMETER_DATA.json"
BUILDER = ROOT / "validation/build_macro_candidate.py"


def load(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def period_key(value: Any, frequency: str) -> str:
    text = str(value)
    if frequency == "M":
        require(len(text) >= 7 and text[4] == "-", f"invalid monthly date: {text!r}")
        return text[:7]
    if frequency == "Q":
        return text
    return text


def percentile(history: list[float], value: float) -> float:
    require(bool(history), "empty history")
    below = sum(1 for x in history if x < value)
    equal = sum(1 for x in history if x == value)
    return round(100.0 * (below + 0.5 * equal) / len(history), 1)


def temperature_label(pct: float, thresholds: list[dict[str, Any]]) -> str:
    for row in thresholds:
        lo, hi = float(row["min"]), float(row["max"])
        if lo <= pct < hi or (pct == 100.0 and hi == 100.0):
            return str(row["label"])
    raise ValueError(f"percentile outside thresholds: {pct}")


def direction(values: list[float]) -> str:
    if len(values) < 2:
        return "STABILE"
    d = values[-1] - values[-2]
    return "SALE" if d > 1e-12 else "SCENDE" if d < -1e-12 else "STABILE"


def acceleration(values: list[float]) -> str:
    if len(values) < 3:
        return "STABILE"
    d1 = values[-2] - values[-3]
    d2 = values[-1] - values[-2]
    dd = d2 - d1
    return "ACCELERA" if dd > 1e-12 else "RALLENTA" if dd < -1e-12 else "STABILE"


def row_map(rows: Any) -> dict[str, dict[str, Any]]:
    require(isinstance(rows, list), "currency series entry must be an array")
    out = {str(row.get("id")): row for row in rows if isinstance(row, dict) and row.get("id")}
    require(len(out) == len(rows), "series rows must have unique ids")
    return out


def changed_paths(before: Any, after: Any, path: str = "") -> list[str]:
    if type(before) is not type(after):
        return [path or "/"]
    if isinstance(before, dict):
        out: list[str] = []
        for key in sorted(set(before) | set(after)):
            token = str(key).replace("~", "~0").replace("/", "~1")
            if key not in before or key not in after:
                out.append(f"{path}/{token}")
            else:
                out.extend(changed_paths(before[key], after[key], f"{path}/{token}"))
        return out
    if isinstance(before, list):
        out: list[str] = []
        for i in range(max(len(before), len(after))):
            if i >= len(before) or i >= len(after):
                out.append(f"{path}/{i}")
            else:
                out.extend(changed_paths(before[i], after[i], f"{path}/{i}"))
        return out
    return [] if before == after else [path or "/"]


def validate_manifest(manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    require(manifest.get("schema") == "GMFQ_MACRO_HISTORICAL_BOOTSTRAP_ANCHOR_V1", "unexpected bootstrap manifest schema")
    target = manifest.get("target")
    previous = manifest.get("previous")
    current = manifest.get("current")
    require(isinstance(target, dict) and isinstance(previous, dict) and isinstance(current, dict), "manifest target/previous/current missing")
    for key in ("currency", "dimension", "macro_series_id"):
        require(bool(target.get(key)), f"target missing {key}")
    for point, name in ((previous, "previous"), (current, "current")):
        for key in ("observation_date", "value", "release_date", "official_reference"):
            require(point.get(key) is not None and point.get(key) != "", f"{name} missing {key}")
        require(math.isfinite(float(point["value"])), f"{name} value is not finite")
    freq = str(manifest.get("frequency"))
    require(freq in {"M", "Q"}, "bootstrap supports M/Q core series only")
    require(period_key(previous["observation_date"], freq) < period_key(current["observation_date"], freq), "economic periods are not increasing")
    require(str(previous["release_date"]) < str(current["release_date"]), "release dates are not increasing")
    provenance = manifest.get("provenance")
    require(isinstance(provenance, dict), "provenance missing")
    require(provenance.get("before_snapshot_kind") == "RECONSTRUCTED", "before snapshot must be explicitly RECONSTRUCTED")
    require(provenance.get("after_snapshot_kind") == "CANONICAL", "after snapshot must be CANONICAL")
    require(provenance.get("official_release_pair_verified") is True, "official release pair must be verified")
    return target, previous, current


def reconstruct_before(after_series: dict[str, Any], after_heat: dict[str, Any], manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    target, previous, current = validate_manifest(manifest)
    c, d, sid = target["currency"], target["dimension"], target["macro_series_id"]
    freq = str(manifest["frequency"])
    series = copy.deepcopy(after_series)
    heat = copy.deepcopy(after_heat)
    row = row_map(series[c]).get(sid)
    require(isinstance(row, dict), f"target series not found: {c}.{sid}")
    dates, values = row.get("dates"), row.get("values")
    require(isinstance(dates, list) and isinstance(values, list) and len(dates) == len(values) and len(dates) >= 2, "target series history invalid")
    require(period_key(dates[-1], freq) == period_key(current["observation_date"], freq), "canonical latest period differs from manifest current")
    require(abs(float(values[-1]) - float(current["value"])) < 1e-12, "canonical latest value differs from manifest current")
    require(period_key(dates[-2], freq) == period_key(previous["observation_date"], freq), "penultimate canonical period differs from manifest previous")
    require(abs(float(values[-2]) - float(previous["value"])) < 1e-12, "penultimate canonical value differs from manifest previous")

    removed_date = dates.pop()
    removed_value = float(values.pop())
    row["last_date"] = dates[-1]
    row["last_value"] = values[-1]

    hrow = heat.get("currencies", {}).get(c, {}).get(d)
    require(isinstance(hrow, dict), "target heatmap row missing")
    require(str(hrow.get("series_id")) == str(manifest["series_id"]), "heatmap series_id differs from manifest")
    require(str(hrow.get("frequency")) == freq, "heatmap frequency differs from manifest")
    require(str(hrow.get("transformation")) == str(manifest["transformation"]), "heatmap transformation differs from manifest")
    require(period_key(hrow.get("as_of"), freq) == period_key(current["observation_date"], freq), "heatmap as_of differs from current")
    require(abs(float(hrow.get("latest_value")) - float(current["value"])) < 1e-12, "heatmap latest value differs from current")

    hist = hrow.get("history")
    require(isinstance(hist, list) and hist, "heatmap history missing")
    hist_values = [float(x) for x in hist]
    require(abs(hist_values[-1] - float(current["value"])) < 1e-12, "heatmap history tail differs from current")
    hist_values.pop()

    preferred = int(heat.get("lookback_rule", {}).get("preferred_years", 10)) * (12 if freq == "M" else 4)
    if preferred > 0 and len(hist) >= preferred:
        # The canonical AFTER may have trimmed one old observation when current was appended.
        # Recover exactly that one predecessor from the full canonical series history.
        before_last_period = period_key(previous["observation_date"], freq)
        prior_values = [(period_key(dt, freq), float(v)) for dt, v in zip(dates, values)]
        matching_end = [i for i, (p, _) in enumerate(prior_values) if p == before_last_period]
        require(len(matching_end) == 1, "cannot locate previous period in full series history")
        end_idx = matching_end[0]
        needed = preferred - len(hist_values)
        require(needed in {0, 1}, f"unexpected heatmap reconstruction gap: {needed}")
        if needed == 1:
            start_idx = end_idx - len(hist_values)
            require(start_idx >= 0, "not enough full series history to reconstruct trimmed heatmap point")
            hist_values.insert(0, prior_values[start_idx][1])

    require(hist_values and abs(hist_values[-1] - float(previous["value"])) < 1e-12, "reconstructed heatmap tail differs from previous official value")
    hrow["history"] = hist_values
    hrow["latest_value"] = float(previous["value"])
    hrow["as_of"] = str(previous["observation_date"])
    pct = percentile(hist_values, float(previous["value"]))
    hrow["percentile"] = pct
    hrow["temperature_score"] = pct
    hrow["temperature_label"] = temperature_label(pct, heat["thresholds"])
    hrow["direction"] = direction(hist_values)
    hrow["acceleration"] = acceleration(hist_values)
    detail = "unemployment" if d == "labour" else "inflation"
    heat["currencies"][c].setdefault("as_of_detail", {})[detail] = str(previous["observation_date"])

    meta = {
        "removed_period": removed_date,
        "removed_value": removed_value,
        "reconstructed_previous_period": row["last_date"],
        "reconstructed_previous_value": row["last_value"],
        "before_history_observations": len(hist_values),
    }
    return series, heat, meta


def candidate_from_manifest(manifest: dict[str, Any], after_series: dict[str, Any]) -> dict[str, Any]:
    target, _, current = validate_manifest(manifest)
    row = row_map(after_series[target["currency"]])[target["macro_series_id"]]
    candidate = {
        "currency": target["currency"],
        "dimension": target["dimension"],
        "macro_series_id": target["macro_series_id"],
        "observation_date": str(current["observation_date"]),
        "value": float(current["value"]),
        "source": str(manifest["source"]),
        "series_id": str(manifest["series_id"]),
        "frequency": str(manifest["frequency"]),
        "transformation": str(manifest["transformation"]),
    }
    if row.get("unit") is not None:
        candidate["unit"] = row["unit"]
    return candidate


def validate_atomic_delta(before_series: dict[str, Any], after_series: dict[str, Any], before_heat: dict[str, Any], after_heat: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    c, d, sid = target["currency"], target["dimension"], target["macro_series_id"]
    require(set(before_series) == set(after_series), "currency coverage changed")
    changed_rows = []
    for currency in sorted(before_series):
        b, a = row_map(before_series[currency]), row_map(after_series[currency])
        for key in sorted(set(b) | set(a)):
            if b.get(key) != a.get(key):
                changed_rows.append({"currency": currency, "macro_series_id": key, "changed_paths": changed_paths(b.get(key), a.get(key))})
    require(len(changed_rows) == 1 and changed_rows[0]["currency"] == c and changed_rows[0]["macro_series_id"] == sid, f"non-atomic series delta: {changed_rows}")
    cells = changed_paths(before_heat, after_heat)
    detail = "unemployment" if d == "labour" else "inflation"
    allowed = (f"/currencies/{c}/{d}", f"/currencies/{c}/as_of_detail/{detail}")
    forbidden = [p for p in cells if not p.startswith(allowed)]
    require(not forbidden, f"non-atomic heatmap delta: {forbidden}")
    require(bool(cells), "bootstrap did not change heatmap")
    return {"changed_rows": changed_rows, "changed_heatmap_cells": cells}


def verify(manifest_path: pathlib.Path, evidence_output: pathlib.Path, work_dir: pathlib.Path | None = None) -> dict[str, Any]:
    manifest = load(manifest_path)
    target, _, _ = validate_manifest(manifest)
    after_series = load(SERIES_PATH)
    after_heat = load(HEAT_PATH)
    before_series, before_heat, reconstruction = reconstruct_before(after_series, after_heat, manifest)
    candidate = candidate_from_manifest(manifest, after_series)
    delta = validate_atomic_delta(before_series, after_series, before_heat, after_heat, target)

    live_before = {"series": hashlib.sha256(SERIES_PATH.read_bytes()).hexdigest(), "heat": hashlib.sha256(HEAT_PATH.read_bytes()).hexdigest()}
    own_tmp = None
    if work_dir is None:
        own_tmp = tempfile.TemporaryDirectory(prefix="gmfq-historical-pit-")
        work = pathlib.Path(own_tmp.name)
    else:
        work = work_dir
        work.mkdir(parents=True, exist_ok=True)
    try:
        before_series_path = work / "before_MACRO_SERIES.json"
        before_heat_path = work / "before_MACRO_THERMOMETER_DATA.json"
        candidate_path = work / "candidate.json"
        dump(before_series_path, before_series)
        dump(before_heat_path, before_heat)
        dump(candidate_path, candidate)
        replay = work / "replay"
        proc = subprocess.run([
            sys.executable, str(BUILDER), "--candidate", str(candidate_path),
            "--series-input", str(before_series_path), "--heatmap-input", str(before_heat_path),
            "--output-dir", str(replay),
        ], cwd=ROOT, text=True, capture_output=True)
        require(proc.returncode == 0, f"builder replay failed: {proc.stderr or proc.stdout}")
        replay_series = load(replay / "MACRO_SERIES.json")
        replay_heat = load(replay / "MACRO_THERMOMETER_DATA.json")
        summary = load(replay / "summary.json")
        exact_series = replay_series == after_series
        exact_heat = replay_heat == after_heat
        require(exact_series, "replay MACRO_SERIES is not exact canonical AFTER")
        require(exact_heat, "replay heatmap is not exact canonical AFTER")
    finally:
        if own_tmp is not None:
            own_tmp.cleanup()

    live_after = {"series": hashlib.sha256(SERIES_PATH.read_bytes()).hexdigest(), "heat": hashlib.sha256(HEAT_PATH.read_bytes()).hexdigest()}
    require(live_before == live_after, "historical bootstrap wrote canonical live data")
    git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    evidence = {
        "schema": "GMFQ_MACRO_PIT_ANCHOR_EVIDENCE_V1",
        "status": "PASS",
        "target": target,
        "candidate": candidate,
        "anchor": {
            "before_git_head": git_head,
            "after_git_head": git_head,
            "before_sha256": {"semantic_sha256": canonical_sha256(before_series), "heatmap_semantic_sha256": canonical_sha256(before_heat)},
            "after_sha256": {"semantic_sha256": canonical_sha256(after_series), "heatmap_semantic_sha256": canonical_sha256(after_heat)},
        },
        "atomic_delta": delta,
        "macro_series_exact_match": True,
        "heatmap_exact_match": True,
        "live_data_written_by_replay": False,
        "engine_or_source_infrastructure_changed": False,
        "registry_promotion": "NOT_ATTEMPTED",
        "builder_summary": summary,
        "bootstrap_provenance": {
            "schema": "GMFQ_MACRO_PIT_HISTORICAL_BOOTSTRAP_PROVENANCE_V1",
            "before_state": "RECONSTRUCTED_FROM_CANONICAL_AFTER_AND_OFFICIAL_PRIOR_RELEASE",
            "after_state": "CANONICAL_RUNTIME",
            "manifest_sha256": canonical_sha256(manifest),
            "official_release_pair_verified": True,
            "reconstruction": reconstruction,
            "previous": manifest["previous"],
            "current": manifest["current"],
        },
    }
    dump(evidence_output, evidence)
    return evidence


def main() -> int:
    ap = argparse.ArgumentParser(description="Fail-closed historical PIT bootstrap for one macro core series")
    ap.add_argument("--anchor-manifest", required=True)
    ap.add_argument("--evidence-output", required=True)
    ap.add_argument("--work-dir")
    args = ap.parse_args()
    evidence = verify(
        pathlib.Path(args.anchor_manifest).resolve(),
        pathlib.Path(args.evidence_output).resolve(),
        pathlib.Path(args.work_dir).resolve() if args.work_dir else None,
    )
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False, indent=2))
        raise
