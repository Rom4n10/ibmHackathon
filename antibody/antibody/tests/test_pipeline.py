"""End-to-end tests for the deterministic half of Antibody.

They build a tiny git repo with a real naive-vs-aware datetime bug, then run
the same commands Bob runs from the Antibody mode. A small stand-in runner
reproduces pytest's exit codes (0 pass, 1 failure, 2 import error, 5 no
tests) so the suite also runs where pytest is not installed.
"""

import json
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

from antibody.memory import build_scoreboard, finalize
from antibody.prove import mark, prove
from antibody.runs import init_repo, new_run, run_dir
from antibody.schema import ContractError, read_json, validate, write_json
from antibody.vaccine import run_round

FAKE_RUNNER = textwrap.dedent('''
    import importlib.util, sys, traceback
    files = [a.split("::")[0] for a in sys.argv[1:] if not a.startswith("-")] or ["tests/test_clock.py"]
    ran = failed = 0
    for path in files:
        spec = importlib.util.spec_from_file_location("t", path)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            traceback.print_exc(); sys.exit(2)
        for name in dir(mod):
            if name.startswith("test_"):
                ran += 1
                try:
                    getattr(mod, name)()
                except Exception:
                    failed += 1; traceback.print_exc()
    sys.exit(5 if ran == 0 else (1 if failed else 0))
''')

BUGGY = textwrap.dedent('''
    from datetime import datetime, timezone

    def is_expired(expires_at):
        return expires_at < datetime.now()

    def seconds_left(expires_at):
        return (expires_at - datetime.now()).total_seconds()
''')

FIXED_ORIGINAL = BUGGY.replace(
    "return expires_at < datetime.now()", "return expires_at < datetime.now(timezone.utc)"
)

REGRESSION_TEST = textwrap.dedent('''
    import sys
    sys.path.insert(0, "src")
    from datetime import datetime, timezone, timedelta
    from clock import is_expired

    def test_is_expired_accepts_aware_datetimes():
        assert is_expired(datetime.now(timezone.utc) - timedelta(seconds=5))
''')

TWIN_TEST = textwrap.dedent('''
    import sys
    sys.path.insert(0, "src")
    from datetime import datetime, timezone, timedelta
    from clock import seconds_left

    def test_seconds_left_accepts_aware_datetimes():
        assert seconds_left(datetime.now(timezone.utc) + timedelta(seconds=60)) > 0
''')


def sh(cwd, *cmd):
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        sh(self.repo, "git", "init", "-q")
        sh(self.repo, "git", "config", "user.email", "test@example.invalid")
        sh(self.repo, "git", "config", "user.name", "Test")
        (self.repo / "src").mkdir()
        (self.repo / "tests").mkdir()
        (self.repo / "src" / "clock.py").write_text(BUGGY)
        (self.repo / "fake_runner.py").write_text(FAKE_RUNNER)
        (self.repo / ".gitignore").write_text("__pycache__/\n")
        sh(self.repo, "git", "add", ".")
        sh(self.repo, "git", "commit", "-qm", "initial")
        # The fix commit Antibody starts from.
        (self.repo / "src" / "clock.py").write_text(FIXED_ORIGINAL)
        (self.repo / "tests" / "test_clock.py").write_text(REGRESSION_TEST)
        sh(self.repo, "git", "add", ".")
        sh(self.repo, "git", "commit", "-qm", "fix: compare aware datetimes in is_expired")
        self.fix_sha = sh(self.repo, "git", "rev-parse", "HEAD")

        init_repo(self.repo)
        config = read_json(self.repo / ".antibody" / "config.json")
        config["test_command"] = ["{python}", "fake_runner.py"]
        write_json(self.repo / ".antibody" / "config.json", config)
        self.run_id = new_run(self.repo, "fix_commit", self.fix_sha)
        self.rdir = run_dir(self.repo, self.run_id)
        write_json(self.rdir / "diagnosis.json", {
            "run_id": self.run_id,
            "source": {"type": "fix_commit", "ref": self.fix_sha, "fix_commit": self.fix_sha,
                       "parent_commit": None, "issue": None},
            "root_cause": {
                "title": "A timezone-aware datetime is compared with a naive one",
                "pattern": "Arithmetic or comparison between an aware datetime argument and datetime.now() without tz",
                "why_it_breaks": "Python raises TypeError when naive and aware datetimes are mixed.",
                "trigger_conditions": ["caller passes an aware datetime"],
                "fix_strategy": "Use datetime.now(timezone.utc) on the naive side.",
                "language": "python",
            },
            "original_instance": {"file": "src/clock.py", "line": 5,
                                  "snippet": "return expires_at < datetime.now()"},
        }, "diagnosis")
        write_json(self.rdir / "candidates.json", {
            "run_id": self.run_id,
            "candidates": [
                {"id": "c01", "file": "src/clock.py", "line": 8,
                 "snippet": "(expires_at - datetime.now()).total_seconds()",
                 "reasoning": "Same naive now() mixed with an aware argument.", "confidence": "high"},
                {"id": "c02", "file": "src/clock.py", "line": 2,
                 "snippet": "from datetime import datetime, timezone",
                 "reasoning": "Import only, probably not a twin.", "confidence": "low"},
            ],
        }, "candidates")

    def tearDown(self):
        subprocess.run(["git", "worktree", "prune"], cwd=self.repo, check=False)
        self.tmp.cleanup()

    def test_red_then_green_confirms_and_fixes_a_twin(self):
        (self.repo / "tests" / "test_twin_c01.py").write_text(TWIN_TEST)
        verdict = prove(self.repo, self.run_id, "c01", "tests/test_twin_c01.py", "red")
        self.assertEqual(verdict["status"], "confirmed")
        self.assertEqual(verdict["red"]["exit_code"], 1)
        self.assertEqual(verdict["red"]["recorded_by"], "antibody-cli")

        clock = self.repo / "src" / "clock.py"
        clock.write_text(clock.read_text().replace(
            "(expires_at - datetime.now())", "(expires_at - datetime.now(timezone.utc))"))
        verdict = prove(self.repo, self.run_id, "c01", "tests/test_twin_c01.py", "green",
                        fix_summary="use an aware now()")
        self.assertEqual(verdict["status"], "fixed")
        validate("verdict", read_json(self.rdir / "verdicts" / "c01.json"))

    def test_broken_test_is_never_a_proof(self):
        (self.repo / "tests" / "test_broken.py").write_text("import does_not_exist\n")
        verdict = prove(self.repo, self.run_id, "c01", "tests/test_broken.py", "red")
        self.assertEqual(verdict["status"], "unproven")
        self.assertIn("broken", verdict["reason"])

    def test_passing_test_does_not_confirm(self):
        (self.repo / "tests" / "test_passes.py").write_text("def test_ok():\n    assert True\n")
        verdict = prove(self.repo, self.run_id, "c01", "tests/test_passes.py", "red")
        self.assertEqual(verdict["status"], "unproven")

    def test_green_requires_red_first(self):
        (self.repo / "tests" / "test_twin_c01.py").write_text(TWIN_TEST)
        with self.assertRaises(ValueError):
            prove(self.repo, self.run_id, "c01", "tests/test_twin_c01.py", "green")

    def test_mark_rejected(self):
        verdict = mark(self.repo, self.run_id, "c02", "rejected", "import line, not a comparison")
        self.assertEqual(verdict["status"], "rejected")

    def _write_variants(self):
        clock = self.repo / "src" / "clock.py"
        original = clock.read_text()
        # v01: re-introduce the original bug, covered by the regression test.
        clock.write_text(original.replace("expires_at < datetime.now(timezone.utc)",
                                          "expires_at < datetime.now()"))
        (self.rdir / "variants" / "v01.patch").write_text(sh(self.repo, "git", "diff") + "\n")
        clock.write_text(original)
        # v02: same mistake in new, untested code.
        clock.write_text(original + "\ndef days_left(expires_at):\n"
                                    "    return (expires_at - datetime.now()).days\n")
        (self.rdir / "variants" / "v02.patch").write_text(sh(self.repo, "git", "diff") + "\n")
        clock.write_text(original)
        # v03: a patch that does not apply.
        (self.rdir / "variants" / "v03.patch").write_text("not a patch\n")
        write_json(self.rdir / "variants.json", {"run_id": self.run_id, "variants": [
            {"id": "v01", "kind": "syntax", "description": "Original bug again",
             "target_file": "src/clock.py", "patch": "variants/v01.patch"},
            {"id": "v02", "kind": "relocation", "description": "Same mistake in a new helper",
             "target_file": "src/clock.py", "patch": "variants/v02.patch"},
            {"id": "v03", "kind": "other", "description": "Broken patch",
             "target_file": "src/clock.py", "patch": "variants/v03.patch"},
        ]}, "variants")

    def test_vaccine_round_zero_measures_existing_defenses(self):
        self._write_variants()
        record = run_round(self.repo, self.run_id, 0, tests=["tests/test_clock.py"])
        by_id = {r["variant_id"]: r for r in record["results"]}
        self.assertEqual(by_id["v01"]["status"], "detected")
        self.assertEqual(by_id["v01"]["detected_by"], ["tests"])
        self.assertEqual(by_id["v02"]["status"], "escaped")
        self.assertEqual(by_id["v03"]["status"], "invalid")
        self.assertEqual((record["valid"], record["detected"], record["score"]), (2, 1, 0.5))
        # The developer's checkout is untouched.
        self.assertIn("datetime.now(timezone.utc)", (self.repo / "src" / "clock.py").read_text())

    def test_vaccine_refuses_dirty_tree(self):
        self._write_variants()
        (self.repo / "src" / "clock.py").write_text("# uncommitted\n")
        with self.assertRaises(RuntimeError):
            run_round(self.repo, self.run_id, 0)

    def test_scoreboard_and_finalize(self):
        (self.repo / "tests" / "test_twin_c01.py").write_text(TWIN_TEST)
        prove(self.repo, self.run_id, "c01", "tests/test_twin_c01.py", "red")
        self._write_variants()
        sh(self.repo, "git", "add", "tests")
        sh(self.repo, "git", "commit", "-qm", "test: prove twin c01")
        run_round(self.repo, self.run_id, 0, tests=["tests/test_clock.py"])

        board = build_scoreboard(self.repo, self.run_id, "example/clock")
        self.assertEqual(board["rounds"][0]["label"], "Before Antibody")
        self.assertEqual(board["twins"][0]["status"], "confirmed")
        self.assertTrue((self.rdir / "scoreboard.json").exists())

        rule = self.rdir / "rule.v1.yml"
        rule.write_text(f"rules:\n  - id: naive-now\n    message: Caused the bug fixed in {self.fix_sha[:7]}\n")
        folder = finalize(self.repo, self.run_id, "naive-vs-aware-datetime",
                          str(rule.relative_to(self.repo)))
        manifest = read_json(folder / "manifest.json", "manifest")
        self.assertEqual(manifest["id"], "001")
        self.assertEqual(manifest["twins"][0]["candidate_id"], "c01")
        history = (folder / "history.md").read_text()
        self.assertIn("Twins found and proven", history)
        self.assertNotIn("test@example.invalid", history)


class ContractTest(unittest.TestCase):
    def test_rejects_unknown_status(self):
        with self.assertRaises(ContractError):
            validate("verdict", {"candidate_id": "c01", "status": "probably"})

    def test_rejects_bad_candidate_id(self):
        with self.assertRaises(ContractError):
            validate("candidates", {"run_id": "x", "candidates": [
                {"id": "1", "file": "a.py", "line": 1, "snippet": "", "reasoning": "", "confidence": "high"}]})

    def test_examples_match_their_contracts(self):
        root = Path(__file__).resolve().parents[1] / "examples" / "sample-run"
        pairs = [("diagnosis.json", "diagnosis"), ("candidates.json", "candidates"),
                 ("variants.json", "variants"), ("scoreboard.json", "scoreboard")]
        for name, schema in pairs:
            read_json(root / name, schema)
        for path in (root / "verdicts").glob("*.json"):
            read_json(path, "verdict")
        for path in (root / "vaccine").glob("*.json"):
            read_json(path, "vaccine_round")
        data = json.loads((root / "scoreboard.json").read_text())
        self.assertGreater(len(data["rounds"]), 1)


if __name__ == "__main__":
    unittest.main()
