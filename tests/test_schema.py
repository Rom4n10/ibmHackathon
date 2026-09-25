"""Tests for antibody.schema — contract validation."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from antibody.schema import ContractError, read_json, validate, write_json


class TestValidate(unittest.TestCase):

    def _minimal_diagnosis(self):
        return {
            "run_id": "20260926-101500",
            "source": {
                "type": "fix_commit",
                "ref": "abc123",
                "fix_commit": "abc123",
                "parent_commit": None,
                "issue": None,
            },
            "root_cause": {
                "title": "naive vs aware datetime",
                "pattern": "datetime.now() compared with aware value",
                "why_it_breaks": "raises TypeError",
                "trigger_conditions": ["aware source", "naive now()"],
                "fix_strategy": "use datetime.now(timezone.utc)",
                "language": "python",
            },
            "original_instance": {"file": "billing/invoices.py", "line": 88, "snippet": "if x < datetime.now():"},
        }

    def test_valid_diagnosis_passes(self):
        validate("diagnosis", self._minimal_diagnosis())  # must not raise

    def test_missing_required_field_raises(self):
        data = self._minimal_diagnosis()
        del data["root_cause"]
        with self.assertRaises(ContractError) as ctx:
            validate("diagnosis", data)
        self.assertIn("root_cause", str(ctx.exception))

    def test_wrong_type_raises(self):
        data = self._minimal_diagnosis()
        data["original_instance"]["line"] = "not-an-int"  # must be integer
        with self.assertRaises(ContractError):
            validate("diagnosis", data)

    def test_unknown_schema_name_raises(self):
        with self.assertRaises(KeyError):
            validate("nonexistent_schema", {})

    def test_valid_verdict_passes(self):
        verdict = {
            "candidate_id": "c01",
            "status": "confirmed",
            "reason": "Test fails on current code.",
            "test": {"file": "tests/test_c01.py", "node_id": None},
            "red": {
                "exit_code": 1, "passed": False, "duration_s": 1.2,
                "output_tail": "1 failed", "recorded_at": "2026-09-26T10:00:00+00:00",
                "recorded_by": "antibody-cli",
            },
            "green": None,
            "fix_summary": None,
        }
        validate("verdict", verdict)  # must not raise

    def test_invalid_status_enum_raises(self):
        verdict = {
            "candidate_id": "c01", "status": "INVENTED_STATUS",
            "reason": None, "test": None, "red": None, "green": None, "fix_summary": None,
        }
        with self.assertRaises(ContractError) as ctx:
            validate("verdict", verdict)
        self.assertIn("INVENTED_STATUS", str(ctx.exception))


class TestReadWriteJson(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._dir = Path(self._tmp)

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_write_then_read_roundtrip(self):
        path = self._dir / "out.json"
        data = {"key": "value", "num": 42}
        write_json(path, data)
        result = read_json(path)
        self.assertEqual(result, data)

    def test_read_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            read_json(self._dir / "missing.json")

    def test_read_invalid_json_raises(self):
        path = self._dir / "bad.json"
        path.write_text("{not valid json}", encoding="utf-8")
        with self.assertRaises(ContractError):
            read_json(path)

    def test_write_with_schema_validates(self):
        path = self._dir / "out.json"
        with self.assertRaises(ContractError):
            write_json(path, {"bad": "data"}, schema="diagnosis")

    def test_write_creates_parent_dirs(self):
        path = self._dir / "deep" / "nested" / "out.json"
        write_json(path, {"x": 1})
        self.assertTrue(path.exists())
