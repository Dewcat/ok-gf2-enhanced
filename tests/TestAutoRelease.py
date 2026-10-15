import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("auto_release", Path(__file__).resolve().parents[1] / "scripts/auto_release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class TestAutoRelease(unittest.TestCase):
    def test_versions(self):
        self.assertEqual(release.stable_tags(["v1.2.9", "v1.2.10-beta", "v1.2.10", "bad"]), ["v1.2.9", "v1.2.10"])
        self.assertEqual(release.next_version("v1.2.99"), "v1.3.0")
        self.assertEqual(release.next_version("v1.2.9"), "v1.2.10")

    def exercise(self, *, complete=True, changed=True, publish=True, active=False, api_error=False):
        calls = []
        tag = "v1.2.86"
        assets = [f"ok-gf2-win32-dewcat-setup-{tag}.exe", f"ok-gf2-win32-online-setup-{tag}.exe", "SHA256SUMS.txt", "launcher-manifest.json", f"ok-gf2-win32-{tag}.zip", f"win32_sha256-{tag}.txt"]
        def fake(*args):
            calls.append(args)
            if args[:3] == ("git", "tag", "--merged"):
                return tag
            if args[:3] == ("gh", "api", "--paginate"):
                if api_error:
                    raise RuntimeError("API failed")
                return json.dumps([[{"tag_name": tag, "draft": False, "assets": [{"name": n} for n in assets] if complete else []}]])
            if args[:2] == ("git", "log"):
                return "abc123" if changed else ""
            if args[:2] == ("gh", "api"):
                return json.dumps({"workflow_runs": [{"head_branch": tag, "status": "in_progress"}] if active else []})
            return ""
        with patch.object(release, "run", side_effect=fake), patch.dict("os.environ", {"GITHUB_REPOSITORY": "Dewcat/ok-gf2-enhanced"}), patch("sys.argv", ["auto_release.py"] + (["--publish"] if publish else [])):
            release.main()
        return calls

    def test_new_release_dispatches_tag(self):
        calls = self.exercise()
        self.assertIn(("git", "tag", "v1.2.87", "HEAD"), calls)
        self.assertEqual(calls[-1][-2:], ("--ref", "v1.2.87"))

    def test_no_change_skips(self):
        calls = self.exercise(changed=False)
        self.assertFalse(any(c[:2] == ("git", "push") for c in calls))
        self.assertFalse(any(c[:2] == ("gh", "workflow") for c in calls))

    def test_incomplete_release_retries_same_tag(self):
        calls = self.exercise(complete=False)
        self.assertFalse(any(c[:2] == ("git", "push") for c in calls))
        self.assertEqual(calls[-1][-2:], ("--ref", "v1.2.86"))

    def test_active_build_skips_retry(self):
        calls = self.exercise(complete=False, active=True)
        self.assertFalse(any(c[:2] == ("gh", "workflow") for c in calls))

    def test_dry_run_does_not_publish(self):
        calls = self.exercise(publish=False)
        self.assertFalse(any(c[:2] in [("git", "push"), ("gh", "workflow")] for c in calls))

    def test_api_failure_aborts(self):
        with self.assertRaisesRegex(RuntimeError, "API failed"):
            self.exercise(api_error=True)

    def test_real_git_path_filters(self):
        paths = release.watched_paths()
        with tempfile.TemporaryDirectory() as folder:
            def git(*args):
                return subprocess.check_output(["git", "-C", folder, *args], text=True).strip()
            git("init", "-q")
            git("config", "user.name", "Test")
            git("config", "user.email", "test@example.invalid")
            git("commit", "--allow-empty", "-qm", "baseline")
            git("tag", "v1.0.0")
            for name in ["README.md", "assets/downloads.svg", "src/guide.MD"]:
                target = Path(folder, name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("documentation", encoding="utf-8")
            git("add", ".")
            git("commit", "-qm", "docs and stats")
            self.assertEqual(git("log", "-1", "--format=%H", "v1.0.0..HEAD", "--", *paths), "")
            Path(folder, "src/task.py").write_text("print('changed')", encoding="utf-8")
            git("add", ".")
            git("commit", "-qm", "runtime change")
            self.assertTrue(git("log", "-1", "--format=%H", "v1.0.0..HEAD", "--", *paths))


if __name__ == "__main__":
    unittest.main()
