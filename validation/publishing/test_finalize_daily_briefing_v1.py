from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

from validation.publishing import finalize_daily_briefing_v1 as handoff


class BriefingHandoffTests(TestCase):
    def setUp(self):
        self.sha = "f" * 40
        self.filename = handoff.report_name("2026-11-18")
        self.run = {
            "name": handoff.QA_WORKFLOW, "event": "pull_request",
            "conclusion": "success", "head_branch": "briefing/2026-11-18-morning-desk",
            "head_sha": self.sha, "head_repository": {"full_name": handoff.REPO},
            "pull_requests": [],
        }
        self.pr = {
            "number": 1344, "state": "open", "draft": False, "merged": False,
            "changed_files": 2, "user": {"login": handoff.PUBLISHER},
            "base": {"ref": "main", "repo": {"full_name": handoff.REPO}},
            "head": {"sha": self.sha, "repo": {"full_name": handoff.REPO}},
        }
        self.files = [
            {"filename": handoff.INDEX, "status": "modified"},
            {"filename": f"{handoff.REPORTS}/{self.filename}", "status": "added"},
        ]
        self.checks = [
            {"name": n, "status": "completed", "conclusion": "success",
             "app": {"slug": "github-actions"}} for n in sorted(handoff.REQUIRED_CHECKS)
        ]

    def replay(self, *, failure=False, extra_file=False, already_merged=False):
        writes = []
        reads = []
        self.pr["merged"] = already_merged
        self.pr["state"] = "closed" if already_merged else "open"

        def fake_api(path, body=None):
            if path.startswith("pulls?"):
                self.assertIn("head=robybizkit77-blip%3Abriefing%2F2026-11-18-morning-desk", path)
                return [self.pr]
            if path == "pulls/1344":
                return self.pr
            if path.endswith("/files"):
                return self.files + ([{"filename": ".github/workflows/x.yml", "status": "added"}]
                                     if extra_file else [])
            if "/check-runs?" in path:
                self.assertIn(self.sha, path)
                reads.append(path)
                checks = [dict(c) for c in self.checks]
                if failure:
                    checks[0]["conclusion"] = "failure"
                elif len(reads) == 1:
                    checks[0]["status"] = "in_progress"
                return {"check_runs": checks}
            if path == "pulls/1344/merge":
                writes.append(body)
                self.pr["merged"] = True
                return {"merged": True}
            self.fail(f"Unexpected request {path}")

        def fake_content(path, ref):
            if path != handoff.INDEX:
                return b"<html>Approved briefing</html>"
            name = self.filename if ref != "main" or self.pr["merged"] else handoff.report_name("2026-11-17")
            return ('{"file":"' + name + '"}').encode()

        with patch.object(handoff, "api", side_effect=fake_api), \
             patch.object(handoff, "content", side_effect=fake_content), \
             patch.object(handoff.time, "sleep"), \
             patch.object(handoff, "datetime") as clock:
            clock.now.return_value = datetime(2026, 11, 18, 7, 54)
            if failure:
                with self.assertRaisesRegex(ValueError, "failed checks"):
                    handoff.finish(self.run)
            else:
                returned = handoff.finish(self.run)
                self.assertEqual(returned, None if extra_file else self.filename)
        return writes, reads

    def test_empty_webhook_pr_array_waits_then_merges_verified_sha(self):
        writes, reads = self.replay()
        self.assertEqual(len(reads), 2)
        self.assertEqual(writes, [{"sha": self.sha, "merge_method": "squash"}])

    def test_failure_third_path_and_already_merged(self):
        self.assertEqual(self.replay(failure=True)[0], [])
        self.assertEqual(self.replay(extra_file=True), ([], []))
        self.assertEqual(self.replay(already_merged=True)[0], [])

    def test_missing_skipped_and_non_github_checks_never_pass(self):
        self.checks[0]["app"] = {"slug": "other"}
        self.checks[1]["conclusion"] = "skipped"
        pending, failed = handoff.check_status(self.checks)
        self.assertEqual(pending, [self.checks[0]["name"]])
        self.assertEqual(failed, [self.checks[1]["name"]])

    def test_untrusted_run_does_not_call_api(self):
        with patch.object(handoff, "api") as api:
            self.assertIsNone(handoff.finish({**self.run, "head_repository": {"full_name": "fork/site"}}))
        api.assert_not_called()
