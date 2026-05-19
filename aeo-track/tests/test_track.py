"""Tests for aeo-track. NO actual launchd/crontab side effects — all install
operations are tested via mocked subprocess.run or by inspecting generated
content only."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import track as t  # noqa: E402


class TestWorkspaceID(unittest.TestCase):

    def test_stable_for_same_path(self):
        self.assertEqual(t.workspace_id("/tmp/x"), t.workspace_id("/tmp/x"))

    def test_different_for_different_paths(self):
        self.assertNotEqual(t.workspace_id("/tmp/a"), t.workspace_id("/tmp/b"))

    def test_normalizes_to_absolute(self):
        # workspace_id should canonicalize via abspath
        cwd_id = t.workspace_id(".")
        abs_id = t.workspace_id(os.getcwd())
        self.assertEqual(cwd_id, abs_id)


class TestScheduleParse(unittest.TestCase):

    def test_daily(self):
        s = t.parse_schedule("daily", hour=9, minute=15)
        self.assertEqual(s, {"kind": "daily", "hour": 9, "minute": 15})

    def test_weekly(self):
        s = t.parse_schedule("weekly", hour=10)
        self.assertEqual(s["kind"], "weekly")
        self.assertEqual(s["weekday"], 1)
        self.assertEqual(s["hour"], 10)

    def test_hourly(self):
        s = t.parse_schedule("hourly", minute=30)
        self.assertEqual(s, {"kind": "hourly", "minute": 30})

    def test_every_n_minutes(self):
        s = t.parse_schedule("every 15m")
        self.assertEqual(s, {"kind": "every_n_minutes", "minutes": 15})

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            t.parse_schedule("yearly")

    def test_every_zero_raises(self):
        with self.assertRaises(ValueError):
            t.parse_schedule("every 0m")


class TestCronFieldGen(unittest.TestCase):

    def test_daily_at_9(self):
        self.assertEqual(t.cron_schedule_field({"kind": "daily", "hour": 9, "minute": 0}), "0 9 * * *")

    def test_weekly_monday_at_9(self):
        self.assertEqual(
            t.cron_schedule_field({"kind": "weekly", "weekday": 1, "hour": 9, "minute": 0}),
            "0 9 * * 1",
        )

    def test_hourly(self):
        self.assertEqual(t.cron_schedule_field({"kind": "hourly", "minute": 5}), "5 * * * *")

    def test_every_n_minutes(self):
        self.assertEqual(t.cron_schedule_field({"kind": "every_n_minutes", "minutes": 10}), "*/10 * * * *")


class TestLaunchdGen(unittest.TestCase):

    def test_daily_plist_well_formed(self):
        plist_path, content = t.generate_launchd_plist(
            workdir="/Users/test/proj",
            wrapper_path="/Users/test/.aeo-track/abc/run.sh",
            schedule={"kind": "daily", "hour": 9, "minute": 15},
        )
        # Path is in LaunchAgents and uses the workspace ID
        self.assertIn("LaunchAgents", plist_path)
        self.assertIn(t.LAUNCHD_LABEL_PREFIX, plist_path)
        # Content has correct schedule
        self.assertIn("<key>StartCalendarInterval</key>", content)
        self.assertIn("<key>Hour</key><integer>9</integer>", content)
        self.assertIn("<key>Minute</key><integer>15</integer>", content)
        # Refers to the wrapper script
        self.assertIn("/Users/test/.aeo-track/abc/run.sh", content)
        # XML header present
        self.assertTrue(content.startswith('<?xml version="1.0"'))

    def test_every_n_minutes_uses_start_interval(self):
        _, content = t.generate_launchd_plist(
            workdir="/x",
            wrapper_path="/x/run.sh",
            schedule={"kind": "every_n_minutes", "minutes": 5},
        )
        self.assertIn("<key>StartInterval</key>", content)
        self.assertIn("<integer>300</integer>", content)  # 5 minutes = 300 seconds


class TestCronLineGen(unittest.TestCase):

    def test_daily_line_has_marker(self):
        line = t.generate_cron_line(
            workdir="/x", wrapper_path="/x/run.sh",
            schedule={"kind": "daily", "hour": 9, "minute": 0},
        )
        self.assertTrue(line.startswith("0 9 * * *"))
        self.assertIn('/bin/bash "/x/run.sh"', line)
        self.assertIn(t.CRON_MARKER_PREFIX, line)
        self.assertIn(t.workspace_id("/x"), line)

    def test_wrapper_path_is_quoted(self):
        """Regression: wrapper path with spaces must still parse via cron."""
        line = t.generate_cron_line(
            workdir="/home/user/My Projects/aeo",
            wrapper_path="/home/user/.aeo-track/abc/run.sh",
            schedule={"kind": "daily", "hour": 9, "minute": 0},
        )
        self.assertIn('"/home/user/.aeo-track/abc/run.sh"', line)

    def test_marker_uniqueness(self):
        a = t.cron_marker("/a")
        b = t.cron_marker("/b")
        self.assertNotEqual(a, b)


class TestWrapperGen(unittest.TestCase):

    def test_wrapper_cd_and_run(self):
        wrapper = t.generate_wrapper(
            workdir="/Users/test/proj",
            baseline_script="/path/to/baseline.py",
            state_dir_path="/Users/test/.aeo-track/abc",
        )
        self.assertIn('cd "/Users/test/proj"', wrapper)
        self.assertIn("/path/to/baseline.py", wrapper)
        self.assertIn("set -e", wrapper)
        self.assertIn("source .env", wrapper)
        # Output redirected to a log under the workspace's aeo-data
        self.assertIn("aeo-data/aeo-track.log", wrapper)
        # Has a generated-at comment
        self.assertIn("Generated:", wrapper)


class TestStateLifecycle(unittest.TestCase):
    """Use a temp HOME so state operations don't touch the real ~/.aeo-track."""

    def setUp(self):
        self.tmp_home = tempfile.TemporaryDirectory()
        self._orig_state_root = t.STATE_ROOT
        t.STATE_ROOT = os.path.join(self.tmp_home.name, "aeo-track")

    def tearDown(self):
        t.STATE_ROOT = self._orig_state_root
        self.tmp_home.cleanup()

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as workdir:
            self.assertIsNone(t.load_state(workdir))
            payload = {"foo": "bar", "workdir": workdir}
            path = t.write_state(workdir, payload)
            self.assertTrue(os.path.isfile(path))
            self.assertEqual(t.load_state(workdir), payload)
            t.delete_state(workdir)
            self.assertIsNone(t.load_state(workdir))


class TestApplyAndRemove(unittest.TestCase):
    """Verify the apply/remove paths don't touch real system schedulers — every
    subprocess.run call is intercepted via mock.
    """

    def test_apply_cron_replaces_existing_marker(self):
        marker = t.cron_marker("/x")
        existing = (
            "0 9 * * * /some/other/job\n"
            f"30 10 * * * /old/aeo/job  {marker}\n"
        )
        captured = {}

        def fake_run(cmd, *args, **kwargs):
            if cmd == ["crontab", "-l"]:
                return mock.MagicMock(returncode=0, stdout=existing, stderr="")
            if cmd == ["crontab", "-"]:
                captured["input"] = kwargs.get("input", "")
                return mock.MagicMock(returncode=0, stderr="")
            raise AssertionError(f"Unexpected subprocess call: {cmd}")

        with mock.patch("subprocess.run", side_effect=fake_run):
            t.apply_cron("/x", f"0 12 * * * /new/job  {marker}\n")

        self.assertNotIn("/old/aeo/job", captured["input"])
        self.assertIn("/new/job", captured["input"])
        self.assertIn("/some/other/job", captured["input"])  # unrelated entries preserved

    def test_remove_cron_drops_workspace_lines(self):
        marker = t.cron_marker("/x")
        existing = (
            "0 9 * * * /some/other/job\n"
            f"30 10 * * * /my/aeo/job  {marker}\n"
        )
        captured = {}

        def fake_run(cmd, *args, **kwargs):
            if cmd == ["crontab", "-l"]:
                return mock.MagicMock(returncode=0, stdout=existing, stderr="")
            if cmd == ["crontab", "-"]:
                captured["input"] = kwargs.get("input", "")
                return mock.MagicMock(returncode=0, stderr="")
            raise AssertionError(f"Unexpected subprocess call: {cmd}")

        with mock.patch("subprocess.run", side_effect=fake_run):
            removed = t.remove_cron("/x")

        self.assertTrue(removed)
        self.assertNotIn("/my/aeo/job", captured["input"])
        self.assertIn("/some/other/job", captured["input"])

    def test_remove_cron_idempotent_when_absent(self):
        existing = "0 9 * * * /unrelated/job\n"

        def fake_run(cmd, *args, **kwargs):
            if cmd == ["crontab", "-l"]:
                return mock.MagicMock(returncode=0, stdout=existing, stderr="")
            raise AssertionError(f"Unexpected call: {cmd}")

        with mock.patch("subprocess.run", side_effect=fake_run):
            removed = t.remove_cron("/x")
        self.assertFalse(removed)


class TestCLIDryRun(unittest.TestCase):
    """End-to-end main() invocations that should NOT touch the real system."""

    def test_install_dry_run_without_config_errors(self):
        with tempfile.TemporaryDirectory() as workdir:
            # No aeo.config.json — should error out
            rc = t.main(["--install", "--workdir", workdir])
            self.assertEqual(rc, 2)

    def test_install_dry_run_prints(self):
        with tempfile.TemporaryDirectory() as workdir:
            # Provide a fake config and a fake baseline-script path
            with open(os.path.join(workdir, "aeo.config.json"), "w") as f:
                f.write('{}')
            fake_baseline = os.path.join(workdir, "fake-baseline.py")
            with open(fake_baseline, "w") as f:
                f.write("# fake\n")
            rc = t.main([
                "--install",
                "--workdir", workdir,
                "--baseline-script", fake_baseline,
                "--schedule", "daily",
            ])
            self.assertEqual(rc, 0)  # dry run succeeds


if __name__ == "__main__":
    unittest.main(verbosity=2)
