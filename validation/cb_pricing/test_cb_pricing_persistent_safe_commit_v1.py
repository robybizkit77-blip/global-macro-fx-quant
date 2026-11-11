"""CB Pricing publication must survive unrelated commits without overwrite.

Real local Git origin exercises a late branch advance and a same-file conflict;
source-candidate validation occurs upstream of this safe persistence layer.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

from validation.macro.persist_calendar_news_safe_v12 import persist

WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/cb-pricing-persistent-daily-v1.yml"
SCOPE = (
    "live_data/sections/OIS_DATA.json",
    "live_data/sections/NATIVE_CB_DATA.json",
    "live_data/manifest.v2.json",
    "payload/part-00.txt",
)


def git(root, *args, check=True):
    p = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if check and p.returncode:
        raise AssertionError(f"git {args}: {p.stderr}")
    return p.stdout.strip()


def write(root, path, value):
    p = root / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(value, encoding="utf-8")


class CBPricingSafeCommitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.base, self.worker, self.rival = (root / s for s in ("base", "worker", "rival"))
        self.origin = root / "origin.git"
        git(root, "init", "--bare", str(self.origin))
        git(root, "init", "-b", "main", str(self.base))
        git(self.base, "config", "user.name", "Test")
        git(self.base, "config", "user.email", "test@example.com")
        for path in SCOPE:
            write(self.base, path, "before\n")
        write(self.base, "README.md", "original\n")
        git(self.base, "add", ".")
        git(self.base, "commit", "-m", "start")
        git(self.base, "remote", "add", "origin", str(self.origin))
        git(self.base, "push", "-u", "origin", "main")
        git(self.origin, "symbolic-ref", "HEAD", "refs/heads/main")
        for path in (self.worker, self.rival):
            git(root, "clone", "--branch", "main", str(self.origin), str(path))
            git(path, "config", "user.name", "Test")
            git(path, "config", "user.email", "test@example.com")

    def test_real_unrelated_main_update_rebases_pricing_without_force(self):
        write(self.worker, SCOPE[0], "validated issuer source new rate\n")
        write(self.rival, "README.md", "independent source note\n")
        git(self.rival, "add", "README.md")
        git(self.rival, "commit", "-m", "other worker")
        git(self.rival, "push", "origin", "main")
        receipt = persist(self.worker, managed=SCOPE)
        self.assertEqual(receipt["status"], "PERSISTED")
        self.assertTrue(receipt["rebased_onto_latest_main"])
        git(self.worker, "fetch", "origin", "main")
        self.assertEqual(git(self.worker, "show", "origin/main:" + SCOPE[0]),
                         "validated issuer source new rate")
        self.assertEqual(git(self.worker, "show", "origin/main:README.md"),
                         "independent source note")

    def test_same_rate_or_manifest_file_conflict_is_not_overwritten(self):
        for path in (SCOPE[0], SCOPE[2]):
            with self.subTest(path=path):
                # Restore both clones to newest remote state before each replay.
                git(self.worker, "fetch", "origin", "main")
                git(self.worker, "reset", "--hard", "origin/main")
                git(self.rival, "pull", "--ff-only")
                write(self.worker, path, "new candidate\n")
                write(self.rival, path, "other worker already updated\n")
                git(self.rival, "add", path)
                git(self.rival, "commit", "-m", "concurrent same field")
                git(self.rival, "push", "origin", "main")
                with self.assertRaisesRegex(RuntimeError,
                                            "REMOTE_MANAGED_FILES_MOVED_FAIL_CLOSED"):
                    persist(self.worker, managed=SCOPE)
                git(self.rival, "fetch", "origin", "main")
                self.assertEqual(git(self.rival, "show", "origin/main:" + path),
                                 "other worker already updated")

    def test_workflow_wires_source_scope_and_no_force(self):
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("from validation.macro.persist_calendar_news_safe_v12 import persist", content)
        self.assertIn("result=persist(managed=scope,max_attempts=6)", content)
        for path in SCOPE:
            self.assertIn(path, content)
        self.assertNotIn("git push --force", content)
        self.assertIn("github.ref == 'refs/heads/main'", content)


if __name__ == "__main__":
    unittest.main()
