"""Tests for antibody.runners: profiles, commands and JUnit-based evidence."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

from antibody.prove import prove
from antibody.runners import (PROFILES, build_command, classify_report, detect_profiles, parse_junit,
                              run_tests, runner_settings)
from antibody.runs import init_repo, load_config, new_run, run_dir
from antibody.schema import write_json
from antibody.vaccine import _link_dependencies, _unlink_dependencies
from tests.fixtures import make_temp_repo

# Stands in for any runner that writes a JUnit report: runs test_* functions of
# the given files and writes one <testcase> per function. FAKE_NO_REPORT=1
# mimics a compile error (exit 1, no report), like Maven or dotnet.
FAKE_JUNIT_RUNNER = textwrap.dedent('''
    import importlib.util, os, sys
    from xml.sax.saxutils import quoteattr
    report, files = sys.argv[1], sys.argv[2:]
    if os.environ.get("FAKE_NO_REPORT"):
        print("error: cannot compile"); sys.exit(1)
    cases, failed = [], 0
    for path in files:
        spec = importlib.util.spec_from_file_location("t", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name in sorted(n for n in dir(mod) if n.startswith("test_")):
            try:
                getattr(mod, name)()
                cases.append(f"<testcase classname={quoteattr(path)} name={quoteattr(name)}/>")
            except Exception as exc:
                failed += 1
                cases.append(f"<testcase classname={quoteattr(path)} name={quoteattr(name)}>"
                             f"<failure message={quoteattr(str(exc))}/></testcase>")
    with open(report, "w", encoding="utf-8") as fh:
        fh.write("<testsuites><testsuite>" + "".join(cases) + "</testsuite></testsuites>")
    sys.exit(1 if failed else 0)
''')


def _junit(tmp: Path, body: str) -> Path:
    path = tmp / f"report-{time.monotonic_ns()}.xml"
    path.write_text(f"<testsuites><testsuite>{body}</testsuite></testsuites>", encoding="utf-8")
    return path


class TestDetectProfiles(unittest.TestCase):

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="antibody-detect-"))

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def _touch(self, name: str, content: str = "") -> None:
        (self.repo / name).write_text(content, encoding="utf-8")

    def test_markers(self):
        cases = [("pom.xml", "", "java-maven"), ("build.gradle.kts", "", "java-gradle"),
                 ("go.mod", "", "go-gotestsum"), ("Cargo.toml", "", "rust-nextest"),
                 ("App.csproj", "", "dotnet"), ("pyproject.toml", "", "python-pytest"),
                 ("package.json", '{"devDependencies": {"vitest": "^3"}}', "js-vitest"),
                 ("package.json", '{"devDependencies": {"jest": "^30"}}', "js-jest")]
        for name, content, expected in cases:
            with self.subTest(marker=name, expected=expected):
                for path in self.repo.iterdir():
                    path.unlink()
                self._touch(name, content)
                self.assertEqual(detect_profiles(self.repo), [expected])

    def test_package_json_without_a_test_runner_is_not_a_match(self):
        self._touch("package.json", '{"dependencies": {"next": "15"}}')
        self.assertEqual(detect_profiles(self.repo), [])

    def test_several_languages_best_first(self):
        self._touch("requirements.txt")
        self._touch("pom.xml")
        self.assertEqual(detect_profiles(self.repo), ["java-maven", "python-pytest"])


class TestBuildCommand(unittest.TestCase):

    def _cmd(self, profile: str, targets: list[str], **overrides) -> list[str]:
        settings = runner_settings({"profile": profile, **overrides})
        return build_command(settings, targets, Path("."), python="py", report="R.xml")

    def test_pytest_splices_targets_and_report(self):
        self.assertEqual(self._cmd("python-pytest", ["tests/test_a.py"]),
                         ["py", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--junitxml=R.xml",
                          "tests/test_a.py"])

    def test_maven_joins_class_names_and_drops_the_flag_without_targets(self):
        cmd = self._cmd("java-maven", ["src/test/java/a/TwinC01Test.java", "src/test/java/b/OtherTest.java"])
        self.assertIn("-Dtest=TwinC01Test,OtherTest", cmd)
        self.assertFalse(any(p.startswith("-Dtest=") for p in self._cmd("java-maven", [])))

    def test_gradle_repeats_the_target_flag(self):
        cmd = self._cmd("java-gradle", ["src/test/java/ATest.java", "src/test/java/BTest.java"])
        self.assertEqual(cmd[-4:], ["--tests", "ATest", "--tests", "BTest"])
        self.assertLess(cmd.index("cleanTest"), cmd.index("test"))

    def test_rust_selects_integration_test_binaries(self):
        self.assertEqual(self._cmd("rust-nextest", ["tests/twin_c01.rs"])[-2:], ["--test", "twin_c01"])

    def test_go_uses_packages_and_defaults_to_all(self):
        self.assertEqual(self._cmd("go-gotestsum", ["billing/twin_test.go"])[-1], "./billing")
        self.assertEqual(self._cmd("go-gotestsum", ["twin_test.go"])[-1], ".")
        self.assertEqual(self._cmd("go-gotestsum", [])[-1], "./...")

    def test_dotnet_formats_a_filter_expression(self):
        cmd = self._cmd("dotnet", ["tests/TwinC01Tests.cs", "tests/OtherTests.cs"])
        self.assertEqual(cmd[-2:], ["--filter", "FullyQualifiedName~TwinC01Tests|FullyQualifiedName~OtherTests"])
        self.assertNotIn("--filter", self._cmd("dotnet", []))

    def test_jest_puts_targets_before_the_reporters(self):
        cmd = self._cmd("js-jest", ["a.test.js"])
        self.assertLess(cmd.index("a.test.js"), cmd.index("--reporters=default"))

    def test_custom_command_without_placeholder_appends_targets(self):
        settings = runner_settings({"test_command": ["{python}", "run.py"]})
        self.assertEqual(build_command(settings, ["t.py"], Path("."), python="py"), ["py", "run.py", "t.py"])


class TestRunnerSettings(unittest.TestCase):

    def test_config_keys_override_the_profile(self):
        settings = runner_settings({"profile": "js-vitest", "test_command": ["pnpm", "vitest"]})
        self.assertEqual(settings["test_command"], ["pnpm", "vitest"])
        self.assertEqual(settings["test_report"], "{report}")

    def test_no_profile_is_plain_pytest_by_exit_code(self):
        settings = runner_settings({})
        self.assertEqual(settings["test_command"][1:3], ["-m", "pytest"])
        self.assertNotIn("test_report", settings)

    def test_unknown_profile_raises(self):
        with self.assertRaises(ValueError):
            runner_settings({"profile": "cobol"})

    def test_every_profile_has_a_command_and_a_report(self):
        for name, profile in PROFILES.items():
            with self.subTest(profile=name):
                self.assertTrue(profile["test_command"])
                self.assertTrue(profile["test_report"])


class TestClassifyReport(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="antibody-junit-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _classify(self, body: str, node: str | None = None) -> tuple:
        return classify_report(parse_junit([_junit(self.tmp, body)]), node)

    def test_failure_and_error_both_count_as_a_failing_test(self):
        # JUnit reports an unexpected exception (the usual bug) as <error>.
        self.assertEqual(self._classify('<testcase classname="A" name="t"><failure/></testcase>')[0], "failed")
        self.assertEqual(self._classify('<testcase classname="A" name="t"><error/></testcase>')[0], "failed")

    def test_passing_test(self):
        self.assertEqual(self._classify('<testcase classname="A" name="t"/>')[:3], ("passed", 1, 0))

    def test_empty_or_skipped_only_is_broken(self):
        self.assertEqual(self._classify("")[0], "broken")
        self.assertEqual(self._classify('<testcase classname="A" name="t"><skipped/></testcase>')[0], "broken")

    def test_node_selects_one_test(self):
        body = ('<testcase classname="A" name="test_ok"/>'
                '<testcase classname="A" name="test_bug"><failure/></testcase>')
        self.assertEqual(self._classify(body, "test_ok")[0], "passed")
        self.assertEqual(self._classify(body, "test_bug")[0], "failed")
        self.assertEqual(self._classify(body, "test_missing")[0], "broken")

    def test_file_that_failed_to_load_is_broken(self):
        # Vitest reports an import error as a failed case named after the file.
        body = ('<testcase classname="tests/twin.test.ts" name="tests/twin.test.ts">'
                '<failure message="Cannot find module ./nope"/></testcase>')
        outcome, _, _, detail = self._classify(body)
        self.assertEqual(outcome, "broken")
        self.assertIn("Cannot find module", detail)

    def test_same_name_and_classname_that_is_not_a_file_is_a_real_test(self):
        # jest-junit uses the same template for both by default.
        body = '<testcase classname="clock shows the bug" name="clock shows the bug"><failure/></testcase>'
        self.assertEqual(self._classify(body)[0], "failed")


class TestRunTestsWithReport(unittest.TestCase):

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="antibody-run-"))
        (self.repo / "runner.py").write_text(FAKE_JUNIT_RUNNER, encoding="utf-8")
        (self.repo / "t_fail.py").write_text("def test_bug():\n    assert False\n", encoding="utf-8")
        (self.repo / "t_pass.py").write_text("def test_ok():\n    pass\n", encoding="utf-8")
        self.config = {"test_command": [sys.executable, "runner.py", "{report}", "{targets}"],
                       "test_report": "{report}"}

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_failing_and_passing(self):
        failed = run_tests(self.repo, ["t_fail.py"], self.config)
        self.assertEqual((failed["outcome"], failed["tests_failed"], failed["evidence_from"]),
                         ("failed", 1, "junit_report"))
        self.assertEqual(run_tests(self.repo, ["t_pass.py"], self.config)["outcome"], "passed")

    def test_exit_1_without_a_report_is_broken_not_a_failure(self):
        env = dict(os.environ, FAKE_NO_REPORT="1")
        evidence = run_tests(self.repo, ["t_fail.py"], self.config, env=env)
        self.assertEqual((evidence["exit_code"], evidence["outcome"]), (1, "broken"))
        self.assertIn("no test report", evidence["detail"])

    def test_stale_reports_are_ignored(self):
        old = self.repo / "reports" / "TEST-old.xml"
        old.parent.mkdir()
        old.write_text('<testsuite><testcase classname="A" name="t"><failure/></testcase></testsuite>',
                       encoding="utf-8")
        # Written just before the run, as a previous prove would leave it (Maven).
        config = dict(self.config, test_report="reports/TEST-*.xml")
        env = dict(os.environ, FAKE_NO_REPORT="1")
        self.assertEqual(run_tests(self.repo, ["t_fail.py"], config, env=env)["outcome"], "broken")

    def test_missing_runner_is_broken(self):
        config = dict(self.config, test_command=["antibody-no-such-runner", "{targets}"])
        evidence = run_tests(self.repo, ["t_fail.py"], config)
        self.assertEqual((evidence["exit_code"], evidence["outcome"]), (127, "broken"))


class TestProveWithReport(unittest.TestCase):

    def setUp(self):
        self.repo = make_temp_repo()
        init_repo(self.repo)
        (self.repo / "runner.py").write_text(FAKE_JUNIT_RUNNER, encoding="utf-8")
        (self.repo / "tests").mkdir()
        (self.repo / "tests" / "test_twin.py").write_text(
            "def test_ok():\n    pass\n\ndef test_bug():\n    raise TypeError('naive vs aware')\n",
            encoding="utf-8")
        config_path = self.repo / ".antibody" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config.update(test_command=[sys.executable, "runner.py", "{report}", "{targets}"],
                      test_report="{report}")
        config_path.write_text(json.dumps(config), encoding="utf-8")
        self.run_id = new_run(self.repo, "postmortem", "x.md")
        write_json(run_dir(self.repo, self.run_id) / "candidates.json", {
            "run_id": self.run_id, "search_notes": "test",
            "candidates": [{"id": c, "file": "a.py", "line": 1, "snippet": "x", "reasoning": "r",
                            "confidence": "high"} for c in ("c01", "c02", "c03")]}, "candidates")

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_node_decides_the_verdict(self):
        bug = prove(self.repo, self.run_id, "c01", "tests/test_twin.py", "red", node_id="test_bug")
        ok = prove(self.repo, self.run_id, "c02", "tests/test_twin.py", "red", node_id="test_ok")
        missing = prove(self.repo, self.run_id, "c03", "tests/test_twin.py", "red", node_id="test_nope")
        self.assertEqual(bug["status"], "confirmed")
        self.assertEqual((bug["red"]["tests_run"], bug["red"]["tests_failed"]), (1, 1))
        self.assertEqual(ok["status"], "unproven")
        self.assertEqual(missing["status"], "unproven")
        self.assertIn("not in the test report", missing["reason"])


class TestInitProfile(unittest.TestCase):

    def setUp(self):
        self.repo = make_temp_repo()

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_init_writes_the_detected_profile(self):
        (self.repo / "package.json").write_text('{"devDependencies": {"vitest": "3"}}', encoding="utf-8")
        init_repo(self.repo)
        self.assertEqual(load_config(self.repo)["profile"], "js-vitest")

    def test_init_with_explicit_profile(self):
        init_repo(self.repo, "java-maven")
        self.assertEqual(load_config(self.repo)["profile"], "java-maven")

    def test_init_with_unknown_profile_raises(self):
        with self.assertRaises(ValueError):
            init_repo(self.repo, "cobol")


class TestDependencyLinks(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="antibody-links-"))
        self.repo, self.worktree = self.tmp / "repo", self.tmp / "wt"
        (self.repo / "node_modules" / "pkg").mkdir(parents=True)
        (self.repo / "node_modules" / "pkg" / "index.js").write_text("x", encoding="utf-8")
        self.worktree.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_link_is_usable_and_unlinking_keeps_the_real_folder(self):
        links = _link_dependencies(self.repo, self.worktree, ["node_modules", "vendor"])
        self.assertEqual(len(links), 1)  # vendor does not exist, so it is skipped
        self.assertTrue((self.worktree / "node_modules" / "pkg" / "index.js").exists())
        _unlink_dependencies(links)
        self.assertFalse((self.worktree / "node_modules").exists())
        self.assertTrue((self.repo / "node_modules" / "pkg" / "index.js").exists())


if __name__ == "__main__":
    unittest.main()
