#!/usr/bin/env python3
"""Repository-level smoke tests for OIS push safety using local bare git repos."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from push_ois_refresh_with_lease_v1 import (
    ESTIMATED_PATHS, G8_PATHS, LeaseError, persist,
)


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
    assert readiness in G8_PATHS and readiness in ESTIMATED_PATHS
    assert operational in G8_PATHS and operational in ESTIMATED_PATHS
    assert same_contract in G8_PATHS and same_contract in ESTIMATED_PATHS
    assert conflict_journal in G8_PATHS and conflict_journal in ESTIMATED_PATHS
    # Both existing runners can publish matching operational and access data.
    for mode in ("estimated","g8"):
        with tempfile.TemporaryDirectory() as td:
            origin,writer,_=fixture(Path(td))
            base=git("rev-parse","HEAD",cwd=writer)
            write(writer,operational,"new validated operational\n")
            write(writer,readiness,"new matching readiness\n")
            assert persist(base,mode,cwd=writer)["status"]=="PUSHED"
            assert git("--git-dir",str(origin),"show","main:"+operational)=="new validated operational"
            assert git("--git-dir",str(origin),"show","main:"+readiness)=="new matching readiness"
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
    # G8-only history cannot be published by the estimated OIS writer.
    with tempfile.TemporaryDirectory() as td:
        _,writer,_=fixture(Path(td))
        base=git("rev-parse","HEAD",cwd=writer)
        write(writer,"validation/cb_pricing/history/OIS_G8_SNAPSHOTS_V1.jsonl","out of scope\n")
        try:
            persist(base,"estimated",cwd=writer)
            raise AssertionError("estimated writer accepted G8-only history")
        except LeaseError as exc:
            assert "REFUSED_OUT_OF_SCOPE" in str(exc),exc

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


if __name__ == "__main__":
    test_unrelated_change()
    test_unrelated_change_without_repository_identity()
    test_refuse_protected("estimated", "live_data/sections/OIS_DATA.json")
    test_refuse_protected("g8", ESTIMATED_PATHS[0])
    test_refuse_protected("g8", "validation/cb_pricing/ois_g8_history_snapshot_v1.py")
    test_readiness_atomic_writer_scope()
    test_noop_scope()
    print("OIS_SAFE_PUSH_LEASE_V1: PASS (unrelated rebase, protected refusal, no-change, scope)")
