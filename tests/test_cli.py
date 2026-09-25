"""Integration tests: every CLI command via main()."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from antibody.cli import main
from tests.fixtures import SAMPLE_RUN_ID, make_temp_repo


def _write_run_json(repo: Path, run_id: str) -> None:
    """Write a minimal run.json for the given run (sample fixtures lack it)."""
    run_dir = repo / ".antibody" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "run_id": run_id,
        "created_at": "2026-09-26T10:15:00+00:00",
        "source": {
            "type": "fix_commit",
            "ref": "abc123",
            "fix_commit": "abc123",
            "parent_commit": None,
            "issue": None,
        },
        "baseline": None,
        "events": [
            {"at": "2026-09-26T10:15:00+00:00", "kind": "run_started", "label": "Run started"}
        ],
    }
    (run_dir / "run.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


class TestCliInit(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo()

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_init_no_bob(self):
        ret = main(["--repo", str(self._repo), "init", "--no-bob"])
        self.assertEqual(ret, 0)
        self.assertTrue((self._repo / ".antibody" / "config.json").exists())

    def test_init_no_bob_skips_bob_dir(self):
        main(["--repo", str(self._repo), "init", "--no-bob"])
        self.assertFalse((self._repo / ".bob").exists())


class TestCliNew(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo()
        main(["--repo", str(self._repo), "init", "--no-bob"])

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_new_postmortem_creates_run(self):
        doc = self._repo / "incident.md"
        doc.write_text("# Incident\n", encoding="utf-8")
        out = StringIO()
        with patch("sys.stdout", out):
            ret = main(["--repo", str(self._repo), "new", "--document", str(doc)])
        self.assertEqual(ret, 0)
        self.assertIn("run_id=", out.getvalue())

    def test_new_without_required_arg_exits_nonzero(self):
        with patch("sys.stderr", StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                main(["--repo", str(self._repo), "new"])
        self.assertNotEqual(ctx.exception.code, 0)


class TestCliValidate(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo(sample_run=True)
        self._diagnosis_path = (
            self._repo / ".antibody" / "runs" / SAMPLE_RUN_ID / "diagnosis.json"
        )

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_validate_valid_file_returns_0(self):
        with patch("sys.stdout", StringIO()):
            ret = main(["validate", str(self._diagnosis_path), "--schema", "diagnosis"])
        self.assertEqual(ret, 0)

    def test_validate_invalid_file_returns_2(self):
        bad = self._repo / "bad.json"
        bad.write_text('{"bad": "data"}', encoding="utf-8")
        with patch("sys.stdout", StringIO()), patch("sys.stderr", StringIO()):
            ret = main(["validate", str(bad), "--schema", "diagnosis"])
        self.assertEqual(ret, 2)


class TestCliStatus(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo(sample_run=True)
        _write_run_json(self._repo, SAMPLE_RUN_ID)

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_status_prints_run_id(self):
        out = StringIO()
        with patch("sys.stdout", out):
            ret = main(["--repo", str(self._repo), "status", "--run", SAMPLE_RUN_ID])
        self.assertEqual(ret, 0)
        self.assertIn(SAMPLE_RUN_ID, out.getvalue())


class TestCliMark(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo(sample_run=True)
        _write_run_json(self._repo, SAMPLE_RUN_ID)

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_mark_suspected_returns_0(self):
        with patch("sys.stdout", StringIO()):
            ret = main([
                "--repo", str(self._repo), "mark", "--run", SAMPLE_RUN_ID,
                "c05", "--suspected", "--reason", "Hard to test in isolation",
            ])
        self.assertEqual(ret, 0)

    def test_mark_rejected_returns_0(self):
        with patch("sys.stdout", StringIO()):
            ret = main([
                "--repo", str(self._repo), "mark", "--run", SAMPLE_RUN_ID,
                "c05", "--rejected", "--reason", "Not a real twin",
            ])
        self.assertEqual(ret, 0)


if __name__ == "__main__":
    unittest.main()
