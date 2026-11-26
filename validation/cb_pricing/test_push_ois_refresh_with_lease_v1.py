#!/usr/bin/env python3
"""Repository-level smoke tests for OIS push safety using local bare git repos."""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from push_ois_refresh_with_lease_v1 import (
    ESTIMATED_PATHS, G8_HISTORY, G8_PATHS, OPERATIONAL_VIEW, LeaseError, persist,
)
from ois_g8_history_snapshot_v1 import make_record
from test_ois_g8_history_snapshot_v1 import view


def git(*args: str, cwd: Path | None = None) -> str:
    p = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True)
    if p.returncode:
        raise AssertionError(f"git {args}: {p.stderr}")
    return p.stdout.strip()


def write(root: Path, relative: str, data: str):
    p = root / relative
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data)


def fixture(root: Path):
    origin = root / "origin.git"
    git("init", "--bare", "-b", "main", str(origin))
    seed = root / "seed"
    git("init", "-b", "main", str(seed))
    git("config", "user.name", "Test", cwd=seed)
    git("config", "user.email", "test@example.com", cwd=seed)
    git("remote", "add", "origin", str(origin), cwd=seed)
    for path in G8_PATHS:
        write(seed, path, "v1\n")
    write(seed, "live_data/sections/OIS_DATA.json", "official-v1\n")
    write(seed, "live_data/sections/NATIVE_CB_DATA.json", "cb-v1\n")
    write(seed, "README.md", "initial\n")
    git("add", ".", cwd=seed)
    git("commit", "-m", "seed", cwd=seed)
    git("push", "-u", "origin", "main", cwd=seed)
    writer, other = root / "writer", root / "other"
    git("clone", "-q", str(origin), str(writer))
    git("clone", "-q", str(origin), str(other))
    for p in (writer, other):
        git("config", "user.name", "Test", cwd=p)
        git("config", "user.email", "test@example.com", cwd=p)
    return origin, writer, other


def other_commit(other: Path, path: str, content: str):
    write(other, path, content)
    git("add", path, cwd=other)
    git("commit", "-m", "another writer", cwd=other)
    git("push", "origin", "HEAD:main", cwd=other)


def test_unrelated_change():
    with tempfile.TemporaryDirectory() as td:
        origin, writer, other = fixture(Path(td))
        base = git("rev-parse", "HEAD", cwd=writer)
        write(writer, ESTIMATED_PATHS[0], "new validated observation\n")
        other_commit(other, "live_data/sections/MACRO_CONSENSUS_SECONDARY_V1.json", "new consensus\n")
        result = persist(base, "estimated", cwd=writer)
        assert result["status"] == "PUSHED" and result["unrelated_main_advance"] is True, result
        assert git("--git-dir", str(origin), "show", "main:" + ESTIMATED_PATHS[0]) == "new validated observation"
        assert git("--git-dir", str(origin), "show", "main:live_data/sections/MACRO_CONSENSUS_SECONDARY_V1.json") == "new consensus"
        assert git("merge-base", "--is-ancestor", base, "HEAD", cwd=writer) == ""


def test_unrelated_change_without_repository_identity():
    """A hosted runner can replay a local OIS commit without global Git config."""
    with tempfile.TemporaryDirectory() as td:
        origin, writer, other = fixture(Path(td))
        git("config", "--unset", "user.name", cwd=writer)
        git("config", "--unset", "user.email", cwd=writer)
        base = git("rev-parse", "HEAD", cwd=writer)
        write(writer, ESTIMATED_PATHS[0], "identity-free validated observation\n")
        other_commit(other, "live_data/sections/MACRO_CONSENSUS_SECONDARY_V1.json", "concurrent non-OIS change\n")
        result = persist(base, "estimated", cwd=writer)
        assert result["status"] == "PUSHED" and result["unrelated_main_advance"] is True, result
        assert git("--git-dir", str(origin), "show", "main:" + ESTIMATED_PATHS[0]) == "identity-free validated observation"


def test_refuse_protected(mode: str, upstream_path: str):
    with tempfile.TemporaryDirectory() as td:
        origin, writer, other = fixture(Path(td))
        base = git("rev-parse", "HEAD", cwd=writer)
        write(writer, ESTIMATED_PATHS[0], "new validated observation\n")
        other_commit(other, upstream_path, "upstream protected change\n")
        try:
            persist(base, mode, cwd=writer)
            raise AssertionError("protected change was overwritten")
        except LeaseError as exc:
            assert "REFUSED_PROTECTED_OIS_CHANGE" in str(exc), exc
        assert git("--git-dir", str(origin), "show", "main:" + upstream_path) == "upstream protected change"
        assert git("--git-dir", str(origin), "show", "main:" + ESTIMATED_PATHS[0]) != "new validated observation"


def test_readiness_atomic_writer_scope():
    readiness="live_data/sections/OIS_SOURCE_READINESS_VIEW.json"
    operational="live_data/sections/OIS_OPERATIONAL_VIEW.json"
    same_contract="validation/cb_pricing/history/OIS_SAME_CONTRACT_QUOTES_V1.jsonl"
    conflict_journal="validation/cb_pricing/history/OIS_SAME_CONTRACT_CONFLICTS_V1.jsonl"
    research="site/fx-quant-v2/ois-same-contract-repricing-research.json"
    assert readiness in G8_PATHS and readiness in ESTIMATED_PATHS
    assert operational in G8_PATHS and operational in ESTIMATED_PATHS
    assert same_contract in G8_PATHS and same_contract in ESTIMATED_PATHS
    assert conflict_journal in G8_PATHS and conflict_journal in ESTIMATED_PATHS
    assert research in G8_PATHS and research in ESTIMATED_PATHS
    fallback="site/fx-quant-v2/ois-pricing-snapshot.json"
    assert fallback in G8_PATHS and fallback in ESTIMATED_PATHS
    history="site/fx-quant-v2/next/rates-pricing-history-v1.json"
    assert history in G8_PATHS and history in ESTIMATED_PATHS
    # Both existing runners publish matching research and operational data.
    for mode in ("estimated","g8"):
        with tempfile.TemporaryDirectory() as td:
            origin,writer,_=fixture(Path(td))
            base=git("rev-parse","HEAD",cwd=writer)
            write(writer,operational,"new validated operational\n")
            write(writer,readiness,"new matching readiness\n")
            write(writer,research,"new matching futures research\n")
            write(writer,fallback,"new matching fallback\n")
            write(writer,history,"new matching history\n")
            assert persist(base,mode,cwd=writer)["status"]=="PUSHED"
            assert git("--git-dir",str(origin),"show","main:"+operational)=="new validated operational"
            assert git("--git-dir",str(origin),"show","main:"+readiness)=="new matching readiness"
            assert git("--git-dir",str(origin),"show","main:"+research)=="new matching futures research"
            assert git("--git-dir",str(origin),"show","main:"+fallback)=="new matching fallback"
            assert git("--git-dir",str(origin),"show","main:"+history)=="new matching history"
    # Concurrent audited readiness change must refuse any stale OIS rebase.
    for mode in ("estimated","g8"):
        with tempfile.TemporaryDirectory() as td:
            _,writer,other=fixture(Path(td))
            base=git("rev-parse","HEAD",cwd=writer)
            write(writer,operational,"local operational\n")
            write(writer,readiness,"local readiness\n")
            other_commit(other,readiness,"other writer readiness\n")
            try:
                persist(base,mode,cwd=writer)
                raise AssertionError("readiness rebase risk accepted: "+mode)
            except LeaseError as exc:
                assert "REFUSED_PROTECTED_OIS_CHANGE" in str(exc),exc


def test_estimated_history_rejects_rewrite():
    with tempfile.TemporaryDirectory() as td:
        _, writer, _ = fixture(Path(td))
        base = git("rev-parse", "HEAD", cwd=writer)
        write(writer, G8_HISTORY, "rewritten history\n")
        try:
            persist(base, "estimated", cwd=writer)
            raise AssertionError("estimated writer rewrote G8 history")
        except LeaseError as exc:
            assert "REFUSED_G8_HISTORY_REWRITE" in str(exc), exc


def test_estimated_history_requires_certified_official_append():
    for currency in ("CAD", "USD"):
        with tempfile.TemporaryDirectory() as td:
            origin, writer, _ = fixture(Path(td))
            base = git("rev-parse", "HEAD", cwd=writer)
            operational = view("2026-10-20")
            record = make_record(currency, operational["currencies"][currency], "2026-10-20T21:00:00Z")
            write(writer, OPERATIONAL_VIEW, json.dumps(operational))
            write(writer, G8_HISTORY, "v1\n" + json.dumps(record) + "\n")
            if currency == "CAD":
                assert persist(base, "estimated", cwd=writer)["status"] == "PUSHED"
                saved = git("--git-dir", str(origin), "show", "main:" + G8_HISTORY)
                assert saved.splitlines()[0] == "v1" and json.loads(saved.splitlines()[1]) == record
            else:
                try:
                    persist(base, "estimated", cwd=writer)
                    raise AssertionError("estimated writer appended an unofficial curve")
                except LeaseError as exc:
                    assert "REFUSED_NON_OFFICIAL_G8_HISTORY_APPEND" in str(exc), exc
                assert git("--git-dir", str(origin), "show", "main:" + G8_HISTORY) == "v1"


def test_noop_scope():
    with tempfile.TemporaryDirectory() as td:
        _, writer, _ = fixture(Path(td))
        base = git("rev-parse", "HEAD", cwd=writer)
        assert persist(base, "estimated", cwd=writer)["status"] == "NO_CHANGE"
        write(writer, "README.md", "unauthorized change\n")
        try:
            persist(base, "g8", cwd=writer)
            raise AssertionError("out-of-scope modification was accepted")
        except LeaseError as exc:
            assert "REFUSED_OUT_OF_SCOPE" in str(exc), exc



def test_fetch_clock_only_noop():
    for mode in ("estimated", "g8"):
        with tempfile.TemporaryDirectory() as td:
            origin, writer, _ = fixture(Path(td))
            first, second = ESTIMATED_PATHS[:2]
            original = {"generated_at_utc": "2026-11-24T12:00:00Z",
                        "source_as_of": "2026-11-23", "rate": 4.5,
                        "quality": "SECONDARY"}
            for path in (first, second):
                write(writer, path, json.dumps(original))
            git("add", first, second, cwd=writer)
            git("commit", "-m", "baseline source quote", cwd=writer)
            git("push", "origin", "HEAD:main", cwd=writer)
            base = git("rev-parse", "HEAD", cwd=writer)
            same = dict(original, generated_at_utc="2026-11-24T12:30:00Z")
            for path in (first, second):
                write(writer, path, json.dumps(same))
            result = persist(base, mode, cwd=writer)
            assert result["status"] == "NO_CHANGE" and result["reason"] == "FETCH_CLOCK_ONLY", result
            assert git("--git-dir", str(origin), "rev-parse", "main") == base
            # A new source observation must still be published, even at the same rate.
            write(writer, second, json.dumps(dict(same, source_as_of="2026-11-24")))
            result = persist(base, mode, cwd=writer)
            assert result["status"] == "PUSHED", result
            assert json.loads(git("--git-dir", str(origin), "show", "main:" + second))["source_as_of"] == "2026-11-24"


def test_asx_reference_metadata_only_noop():
    for mode in ("estimated", "g8"):
        for scenario in ("same", "rate", "date", "hash_mismatch", "history_append"):
            with tempfile.TemporaryDirectory() as td:
                origin, writer, _ = fixture(Path(td))
                first, proxy = ESTIMATED_PATHS[:2]
                history = "site/fx-quant-v2/next/rates-pricing-history-v1.json"
                def put(digest, clock, rate=3.68, date="2026-11-25", mismatch=False):
                    write(writer, first, json.dumps({"generated_at_utc": clock, "rate": 4.5}))
                    write(writer, proxy, json.dumps({"generated_at_utc": clock, "as_of": date,
                        "monthly_reference": {"schema": "GMFQ_NZD_ASX_EXACT_20_WEEKDAY_REFERENCE_V1",
                            "status": "REFERENCE_PARSED", "decoded_source_sha256": digest,
                            "reference_date": "2026-10-28", "rate": rate}}))
                    write(writer, history, json.dumps({"as_of": date, "currencies": {"NZD": {
                        "fixed_contract_20d": {"basis": "EXACT_LISTED_ASX_BANK_BILL_CONTRACT_NOT_OIS",
                            "source_sha256": "c"*64 if mismatch else digest, "current_rate": rate}}}}))
                put("a"*64, "2026-11-26T09:30:00Z")
                git("add", first, proxy, history, cwd=writer)
                git("commit", "-m", "baseline ASX proof", cwd=writer)
                git("push", "origin", "HEAD:main", cwd=writer)
                base = git("rev-parse", "HEAD", cwd=writer)
                put("b"*64, "2026-11-26T09:35:00Z", rate=3.69 if scenario == "rate" else 3.68,
                    date="2026-11-26" if scenario == "date" else "2026-11-25",
                    mismatch=scenario == "hash_mismatch")
                if scenario == "history_append":
                    write(writer, ESTIMATED_PATHS[5], "v1\\nnew observed record\\n")
                result = persist(base, mode, cwd=writer)
                if scenario == "same":
                    assert result["status"] == "NO_CHANGE" and result["reason"] == "ASX_REFERENCE_METADATA_ONLY", result
                    assert git("--git-dir", str(origin), "rev-parse", "main") == base
                else:
                    assert result["status"] == "PUSHED", (scenario, result)


if __name__ == "__main__":
    test_unrelated_change()
    test_unrelated_change_without_repository_identity()
    test_refuse_protected("estimated", "live_data/sections/OIS_DATA.json")
    test_refuse_protected("estimated", G8_HISTORY)
    test_refuse_protected("g8", ESTIMATED_PATHS[0])
    test_refuse_protected("g8", "validation/cb_pricing/ois_g8_history_snapshot_v1.py")
    test_readiness_atomic_writer_scope()
    test_estimated_history_rejects_rewrite()
    test_estimated_history_requires_certified_official_append()
    test_noop_scope()
    test_fetch_clock_only_noop()
    test_asx_reference_metadata_only_noop()
    print("OIS_SAFE_PUSH_LEASE_V1: PASS (unrelated rebase, protected refusal, no-change, scope)")
