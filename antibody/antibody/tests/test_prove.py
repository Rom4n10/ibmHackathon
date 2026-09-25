"""Tests for antibody.prove — red/green evidence runner."""
from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from antibody.prove import mark, prove
from antibody.runs import init_repo, new_run, run_dir
from antibody.schema import read_json
from tests.fixtures import make_temp_repo


def _write_candidates(repo: Path, run_id: str, ids: list[str]) -> None:
    """Write a minimal candidates.json with the given ids."""
    from antibody.schema import write_json
    data = {
        "run_id": run_id,
        "search_notes": "test",
        "candidates": [
            {"id": cid, "file": "src/app.py", "line": 1,
             "snippet": "x = 1", "reasoning": "test", "confidence": "high"}
            for cid in ids
        ],
    }
    write_json(run_dir(repo, run_id) / "candidates.json", data, "candidates")


def _write_failing_test(repo: Path, rel_path: str) -> str:
    """Write a test that always fails (exit code 1). Returns repo-relative path."""
    test_path = repo / rel_path
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text("def test_always_fails():\n    assert False, 'injected failure'\n",
                         encoding="utf-8")
    return rel_path


def _write_passing_test(repo: Path, rel_path: str) -> str:
    """Write a test that always passes (exit code 0). Returns repo-relative path."""
    test_path = repo / rel_path
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text("def test_always_passes():\n    assert True\n", encoding="utf-8")
    return rel_path


class TestProveRed(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo()
        init_repo(self._repo)
        self._run_id = new_run(self._repo, "postmortem", "x.md")
        _write_candidates(self._repo, self._run_id, ["c01", "c02"])

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_red_failing_test_confirms_twin(self):
        test_file = _write_failing_test(self._repo, "tests/test_twin_c01.py")
        verdict = prove(self._repo, self._run_id, "c01", test_file, "red")
        self.assertEqual(verdict["status"], "confirmed")
        self.assertIsNotNone(verdict["red"])
        self.assertEqual(verdict["red"]["exit_code"], 1)
        self.assertEqual(verdict["red"]["recorded_by"], "antibody-cli")

    def test_red_passing_test_leaves_unproven(self):
        test_file = _write_passing_test(self._repo, "tests/test_twin_c02.py")
        verdict = prove(self._repo, self._run_id, "c02", test_file, "red")
        self.assertEqual(verdict["status"], "unproven")

    def test_red_unknown_candidate_raises(self):
        with self.assertRaises(ValueError):
            prove(self._repo, self._run_id, "c99", "tests/x.py", "red")

    def test_red_missing_test_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            prove(self._repo, self._run_id, "c01", "tests/does_not_exist.py", "red")

    def test_verdict_file_is_written(self):
        test_file = _write_failing_test(self._repo, "tests/test_twin_c01.py")
        prove(self._repo, self._run_id, "c01", test_file, "red")
        verdict_path = run_dir(self._repo, self._run_id) / "verdicts" / "c01.json"
        self.assertTrue(verdict_path.exists())
        data = read_json(verdict_path, "verdict")
        self.assertEqual(data["status"], "confirmed")


class TestProveGreen(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo()
        init_repo(self._repo)
        self._run_id = new_run(self._repo, "postmortem", "x.md")
        _write_candidates(self._repo, self._run_id, ["c01"])
        # First confirm the twin in red
        test_file = _write_failing_test(self._repo, "tests/test_twin_c01.py")
        prove(self._repo, self._run_id, "c01", test_file, "red")

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_green_requires_prior_red_confirmation(self):
        _write_candidates(self._repo, self._run_id, ["c01", "c02"])
        _write_passing_test(self._repo, "tests/test_c02.py")
        # c02 was never confirmed
        with self.assertRaises(ValueError):
            prove(self._repo, self._run_id, "c02", "tests/test_c02.py", "green")

    def test_green_passing_test_marks_fixed(self):
        test_file = _write_passing_test(self._repo, "tests/test_twin_c01_fixed.py")
        verdict = prove(self._repo, self._run_id, "c01", test_file, "green",
                        fix_summary="Use datetime.now(timezone.utc)")
        self.assertEqual(verdict["status"], "fixed")
        self.assertEqual(verdict["fix_summary"], "Use datetime.now(timezone.utc)")


class TestMark(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo()
        init_repo(self._repo)
        self._run_id = new_run(self._repo, "postmortem", "x.md")
        _write_candidates(self._repo, self._run_id, ["c01"])

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_mark_suspected(self):
        verdict = mark(self._repo, self._run_id, "c01", "suspected", "Celery task, hard to test")
        self.assertEqual(verdict["status"], "suspected")

    def test_mark_rejected(self):
        verdict = mark(self._repo, self._run_id, "c01", "rejected", "Not a twin, different pattern")
        self.assertEqual(verdict["status"], "rejected")

    def test_mark_invalid_status_raises(self):
        with self.assertRaises(ValueError):
            mark(self._repo, self._run_id, "c01", "INVALID", "reason")
