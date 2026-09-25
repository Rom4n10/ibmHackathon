"""Tests for antibody.runs — run lifecycle and git helpers."""
from __future__ import annotations

import json
import os
import shutil
import stat
import unittest
from unittest import mock

from antibody.runs import (
    antibody_root, init_repo, latest_run, load_config, log_event,
    new_run, run_dir, set_baseline,
)
from tests.fixtures import make_temp_repo


class TestInitRepo(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo()

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_creates_antibody_dirs(self):
        init_repo(self._repo)
        self.assertTrue((self._repo / ".antibody" / "runs").is_dir())
        self.assertTrue((self._repo / ".antibody" / "antibodies").is_dir())

    def test_creates_config_json(self):
        init_repo(self._repo)
        config_path = self._repo / ".antibody" / "config.json"
        self.assertTrue(config_path.exists())

    def test_idempotent(self):
        init_repo(self._repo)
        init_repo(self._repo)  # second call must not raise
        config_path = self._repo / ".antibody" / "config.json"
        self.assertTrue(config_path.exists())

    def test_not_a_git_repo_raises(self):
        tmp = make_temp_repo()
        try:
            # git object files are read-only on Windows; clear the flag and retry
            def _force(func, path, _exc):
                os.chmod(path, stat.S_IWRITE)
                func(path)
            shutil.rmtree(tmp / ".git", onerror=_force)
            self.assertFalse((tmp / ".git").exists())
            # Stop git discovery at tmp's parent so an enclosing repo (e.g. a
            # git-tracked home directory) is not picked up.
            with mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": str(tmp.parent)}):
                with self.assertRaises(RuntimeError):
                    init_repo(tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestNewRun(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo()
        init_repo(self._repo)

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_creates_run_dirs(self):
        run_id = new_run(self._repo, "postmortem", "docs/incident-2026.md")
        rdir = run_dir(self._repo, run_id)
        self.assertTrue((rdir / "verdicts").is_dir())
        self.assertTrue((rdir / "variants").is_dir())
        self.assertTrue((rdir / "vaccine").is_dir())

    def test_run_json_has_source(self):
        run_id = new_run(self._repo, "postmortem", "incident.md", issue="#99")
        run_json = json.loads((run_dir(self._repo, run_id) / "run.json").read_text())
        self.assertEqual(run_json["source"]["type"], "postmortem")
        self.assertEqual(run_json["source"]["issue"], "#99")

    def test_run_json_has_events(self):
        run_id = new_run(self._repo, "postmortem", "x.md")
        run_json = json.loads((run_dir(self._repo, run_id) / "run.json").read_text())
        self.assertGreaterEqual(len(run_json["events"]), 1)
        self.assertEqual(run_json["events"][0]["kind"], "run_started")


class TestLatestRun(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo()
        init_repo(self._repo)

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_no_runs_raises(self):
        with self.assertRaises(FileNotFoundError):
            latest_run(self._repo)

    def test_returns_latest_alphabetically(self):
        runs = self._repo / ".antibody" / "runs"
        (runs / "20260926-100000").mkdir(parents=True)
        (runs / "20260926-200000").mkdir(parents=True)
        self.assertEqual(latest_run(self._repo), "20260926-200000")


class TestLogEventAndBaseline(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo()
        init_repo(self._repo)
        self._run_id = new_run(self._repo, "postmortem", "x.md")

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_log_event_appends(self):
        log_event(self._repo, self._run_id, "test_event", "something happened")
        run_json = json.loads((run_dir(self._repo, self._run_id) / "run.json").read_text())
        kinds = [e["kind"] for e in run_json["events"]]
        self.assertIn("test_event", kinds)

    def test_set_baseline_records(self):
        set_baseline(self._repo, self._run_id, 45.5, 3)
        run_json = json.loads((run_dir(self._repo, self._run_id) / "run.json").read_text())
        self.assertEqual(run_json["baseline"]["manual_minutes"], 45.5)
        self.assertEqual(run_json["baseline"]["manual_twins"], 3)


if __name__ == "__main__":
    unittest.main()
