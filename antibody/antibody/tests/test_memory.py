"""Tests for antibody.memory — finalize and scoreboard."""
from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from antibody.memory import build_scoreboard, finalize
from antibody.runs import run_dir
from antibody.schema import read_json
from tests.fixtures import SAMPLE_RUN_ID, make_temp_repo


def _ensure_run_json(repo: Path) -> None:
    """The sample-run fixture has no run.json; memory functions log events to it."""
    path = run_dir(repo, SAMPLE_RUN_ID) / "run.json"
    if path.exists():
        return
    path.write_text(json.dumps({
        "run_id": SAMPLE_RUN_ID,
        "created_at": "2026-09-26T10:15:00+00:00",
        "source": {"type": "fix_commit", "ref": "HEAD", "fix_commit": None,
                   "parent_commit": None, "issue": None},
        "baseline": None,
        "events": [],
    }), encoding="utf-8")


class TestFinalize(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo(sample_run=True)
        _ensure_run_json(self._repo)
        # Write a minimal rule file (finalize needs an existing file)
        self._rule_path = self._repo / "rule.v2.yml"
        # Copy from the sample-run fixtures
        src = Path(__file__).parent.parent / "examples" / "sample-run" / "rule.v2.yml"
        shutil.copyfile(src, self._rule_path)

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_creates_antibody_folder(self):
        folder = finalize(self._repo, SAMPLE_RUN_ID, "naive-vs-aware-datetime",
                          str(self._rule_path.relative_to(self._repo)))
        self.assertTrue(folder.is_dir())
        self.assertTrue((folder / "manifest.json").exists())
        self.assertTrue((folder / "rule.yml").exists())
        self.assertTrue((folder / "history.md").exists())

    def test_manifest_passes_schema(self):
        folder = finalize(self._repo, SAMPLE_RUN_ID, "naive-vs-aware-datetime",
                          str(self._rule_path.relative_to(self._repo)))
        read_json(folder / "manifest.json", "manifest")  # must not raise

    def test_missing_rule_raises(self):
        with self.assertRaises(FileNotFoundError):
            finalize(self._repo, SAMPLE_RUN_ID, "slug", "nonexistent/rule.yml")

    def test_slug_appears_in_folder_name(self):
        folder = finalize(self._repo, SAMPLE_RUN_ID, "my-test-slug",
                          str(self._rule_path.relative_to(self._repo)))
        self.assertIn("my-test-slug", folder.name)


class TestBuildScoreboard(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo(sample_run=True)
        _ensure_run_json(self._repo)

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_scoreboard_json_is_written(self):
        build_scoreboard(self._repo, SAMPLE_RUN_ID, "owner/project")
        out = run_dir(self._repo, SAMPLE_RUN_ID) / "scoreboard.json"
        self.assertTrue(out.exists())

    def test_scoreboard_passes_schema(self):
        data = build_scoreboard(self._repo, SAMPLE_RUN_ID, "owner/project")
        # validate() is called inside build_scoreboard; reaching here = passed
        self.assertIn("twins", data)
        self.assertIn("rounds", data)

    def test_scoreboard_has_repo_label(self):
        data = build_scoreboard(self._repo, SAMPLE_RUN_ID, "my-org/my-repo")
        self.assertEqual(data["repo"], "my-org/my-repo")
