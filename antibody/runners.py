"""Test runner profiles: how to run a project's tests and read the result.

Antibody proves a twin only when its test *ran and failed*. Exit codes cannot
tell that apart in most ecosystems (Jest, Maven or dotnet exit 1 both for a
failing test and for code that does not compile), so a profile reads the JUnit
XML report that almost every test runner can write:

- the target test is in the report and failed   -> "failed" (bug demonstrated)
- the target test is in the report and passed   -> "passed"
- no report, or the test is not in it           -> "broken" (not a proof)

A profile without a report, and a custom `test_command` without a
`test_report`, fall back to pytest's exit codes (0 pass, 1 failure, 2-5 broken).

Placeholders in `test_command` and `test_env`:
  {python}   --python, $ANTIBODY_PYTHON or the current interpreter
  {report}   a fresh path where the runner must write its JUnit XML report
  {gradle}   ./gradlew (gradlew.bat on Windows) when present, else gradle
  {targets}  the test targets. A token that is exactly "{targets}" becomes one
             argument per target (each preceded by `target_flag` if set), or
             `targets_option` followed by the targets joined with
             `targets_separator`; a token that contains it gets the joined
             targets. Without targets, those tokens are dropped
             (or `default_targets` are used). If no token mentions {targets},
             targets are appended at the end.

`dependency_dirs` lists untracked folders the tests need (node_modules), which
the vaccine links into its clean worktree.
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from .runs import now_iso

# Used when neither a profile nor a test_command is configured (older configs).
LEGACY_COMMAND = ["{python}", "-m", "pytest", "-q", "-p", "no:cacheprovider"]

# Keys a config can set directly to override its profile.
RUNNER_KEYS = ("test_command", "test_report", "test_env", "target_style", "target_flag",
               "target_format", "targets_option", "targets_separator", "default_targets",
               "broken_exit_codes", "dependency_dirs")

PYTEST_EXIT_MEANING = {
    0: "all tests passed",
    1: "tests ran and at least one failed",
    2: "execution interrupted (often an import or syntax error)",
    3: "internal pytest error",
    4: "pytest usage error (bad path or option)",
    5: "no tests were collected",
}

# "verified": exercised end to end against the real runner by the Antibody team.
# Unverified profiles follow each runner's documentation; check them on a real
# project before relying on them, and override any key in .antibody/config.json.
PROFILES: dict[str, dict] = {
    "python-pytest": {
        "language": "python", "verified": True,
        "test_command": ["{python}", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                         "--junitxml={report}", "{targets}"],
        "test_report": "{report}",
        # Collection, usage and "no tests" errors: the test never ran.
        "broken_exit_codes": [2, 3, 4, 5],
    },
    "js-vitest": {
        "language": "javascript", "verified": True,
        "test_command": ["npx", "vitest", "run", "--reporter=junit", "--outputFile={report}", "{targets}"],
        "test_report": "{report}",
        "dependency_dirs": ["node_modules"],
    },
    "js-jest": {
        "language": "javascript", "verified": True,
        "note": "needs the jest-junit package",
        # Targets go first: --reporters takes several values and would swallow them.
        "test_command": ["npx", "jest", "--ci", "{targets}", "--reporters=default", "--reporters=jest-junit"],
        "test_env": {"JEST_JUNIT_OUTPUT_FILE": "{report}"},
        "test_report": "{report}",
        "dependency_dirs": ["node_modules"],
    },
    "java-maven": {
        "language": "java", "verified": False,
        "test_command": ["mvn", "-B", "-q", "test", "-Dtest={targets}",
                         "-Dsurefire.failIfNoSpecifiedTests=false"],
        "test_report": "**/target/surefire-reports/TEST-*.xml",
        "target_style": "stem",
    },
    "java-gradle": {
        "language": "java", "verified": False,
        # cleanTest: an up-to-date test task would not run nor write a new report.
        "test_command": ["{gradle}", "cleanTest", "test", "{targets}"],
        "test_report": "**/build/test-results/test/TEST-*.xml",
        "target_style": "stem", "target_flag": "--tests",
    },
    "go-gotestsum": {
        "language": "go", "verified": False,
        "note": "needs gotestsum (go install gotest.tools/gotestsum@latest)",
        "test_command": ["gotestsum", "--junitfile", "{report}", "--", "{targets}"],
        "test_report": "{report}",
        "target_style": "package", "default_targets": ["./..."],
    },
    "dotnet": {
        "language": "csharp", "verified": False,
        "note": "needs the JunitXml.TestLogger package in the test project",
        "test_command": ["dotnet", "test", "--logger", "junit;LogFilePath={report}", "{targets}"],
        "test_report": "{report}",
        "target_style": "stem", "target_format": "FullyQualifiedName~{target}",
        "targets_option": "--filter", "targets_separator": "|",
    },
    "rust-nextest": {
        "language": "rust", "verified": False,
        "note": "needs cargo-nextest and [profile.antibody.junit] path = \"junit.xml\" in .config/nextest.toml; "
                "twin tests go in tests/<name>.rs",
        "test_command": ["cargo", "nextest", "run", "--profile", "antibody", "{targets}"],
        "test_report": "target/nextest/antibody/junit.xml",
        "target_style": "stem", "target_flag": "--test",
    },
    "ruby-rspec": {
        "language": "ruby", "verified": False,
        "note": "needs the rspec_junit_formatter gem",
        "test_command": ["bundle", "exec", "rspec", "--format", "progress", "--format", "RspecJunitFormatter",
                         "--out", "{report}", "{targets}"],
        "test_report": "{report}",
    },
    "php-phpunit": {
        "language": "php", "verified": False,
        "test_command": ["vendor/bin/phpunit", "--log-junit", "{report}", "{targets}"],
        "test_report": "{report}",
        "dependency_dirs": ["vendor"],
    },
}

# Checked in order; the first match becomes the default profile. A marker is a
# file name (glob allowed) and, optionally, a word its content must contain.
_MARKERS: list[tuple[str, str | None, str]] = [
    ("pom.xml", None, "java-maven"),
    ("build.gradle", None, "java-gradle"),
    ("build.gradle.kts", None, "java-gradle"),
    ("go.mod", None, "go-gotestsum"),
    ("Cargo.toml", None, "rust-nextest"),
    ("*.sln", None, "dotnet"),
    ("*.csproj", None, "dotnet"),
    ("package.json", "vitest", "js-vitest"),
    ("package.json", "jest", "js-jest"),
    ("Gemfile", "rspec", "ruby-rspec"),
    ("composer.json", "phpunit", "php-phpunit"),
    ("pyproject.toml", None, "python-pytest"),
    ("setup.py", None, "python-pytest"),
    ("setup.cfg", None, "python-pytest"),
    ("pytest.ini", None, "python-pytest"),
    ("tox.ini", None, "python-pytest"),
    ("requirements.txt", None, "python-pytest"),
]


def detect_profiles(repo: Path) -> list[str]:
    """Profiles whose markers exist at the repository root, best first."""
    found: list[str] = []
    for pattern, word, profile in _MARKERS:
        if profile in found:
            continue
        for path in Path(repo).glob(pattern):
            if not path.is_file():
                continue
            if word is None or word in path.read_text(encoding="utf-8", errors="ignore"):
                found.append(profile)
                break
    return found


def runner_settings(config: dict) -> dict:
    """The profile named in the config, with any runner key in the config on top."""
    name = config.get("profile")
    if name and name not in PROFILES:
        raise ValueError(f"Unknown test profile '{name}'. Known: {', '.join(PROFILES)}")
    settings = dict(PROFILES[name]) if name else {}
    for key in RUNNER_KEYS:
        if key in config:
            settings[key] = config[key]
    settings.setdefault("test_command", LEGACY_COMMAND)
    return settings


def _target(test_file: str, style: str) -> str:
    path = Path(test_file)
    if style == "stem":
        return path.stem
    if style == "package":
        parent = path.parent.as_posix()
        return "." if parent in ("", ".") else f"./{parent}"
    return test_file


def build_command(settings: dict, targets: list[str], cwd: Path, python: str | None = None,
                  report: str = "") -> list[str]:
    style = settings.get("target_style", "path")
    fmt = settings.get("target_format", "{target}")
    items = [fmt.replace("{target}", _target(t, style)) for t in targets]
    items = items or list(settings.get("default_targets", []))
    interpreter = python or os.environ.get("ANTIBODY_PYTHON") or sys.executable
    wrapper = cwd / ("gradlew.bat" if os.name == "nt" else "gradlew")
    gradle = str(wrapper) if wrapper.exists() else "gradle"

    command: list[str] = []
    mentions_targets = False
    for part in settings["test_command"]:
        part = part.replace("{python}", interpreter).replace("{report}", report).replace("{gradle}", gradle)
        if part == "{targets}":
            mentions_targets = True
            if settings.get("targets_option"):
                if items:
                    command += [settings["targets_option"], settings.get("targets_separator", ",").join(items)]
                continue
            for item in items:
                if settings.get("target_flag"):
                    command.append(settings["target_flag"])
                command.append(item)
        elif "{targets}" in part:
            mentions_targets = True
            if items:
                command.append(part.replace("{targets}", settings.get("targets_separator", ",").join(items)))
        else:
            command.append(part)
    if not mentions_targets:
        command += items
    return command


# A test file path, e.g. tests/app.test.ts or src/test/java/AppTest.java.
_SOURCE_FILE = re.compile(r"[\w.-]+\.(py|js|jsx|mjs|cjs|ts|tsx|mts|cts|java|kt|go|rb|php|cs|rs|scala|swift)$")


def parse_junit(paths: list[Path]) -> list[dict]:
    """Every <testcase> in the given JUnit XML files, with its status.

    Status "load_error" marks a file that failed to load (an import or syntax
    error): some runners, such as Vitest, report it as a failed test case whose
    name and classname are both the test file's path. It must never count as a
    failing test.
    """
    cases = []
    for path in paths:
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError):
            continue
        for case in root.iter("testcase"):
            name, classname = case.get("name", ""), case.get("classname", "")
            problem = next((c for c in case if c.tag in ("failure", "error")), None)
            if problem is not None:
                status = "load_error" if name == classname and _SOURCE_FILE.search(name) else "failed"
            else:
                status = "skipped" if case.find("skipped") is not None else "passed"
            text = (problem.get("message") or problem.text or "") if problem is not None else ""
            message = text.strip().splitlines()
            cases.append({"name": name, "classname": classname, "status": status,
                          "message": message[0][:200] if message else ""})
    return cases


def _matches(case: dict, node_id: str | None) -> bool:
    if not node_id:
        return True
    return node_id in case["name"] or node_id == f"{case['classname']}.{case['name']}"


def classify_report(cases: list[dict], node_id: str | None = None) -> tuple[str, int, int, str]:
    """(outcome, tests_run, tests_failed, detail) from parsed test cases."""
    load_errors = [c for c in cases if c["status"] == "load_error"]
    if load_errors:
        return "broken", 0, 0, f"the test file failed to load: {load_errors[0]['message']}"
    selected = [c for c in cases if _matches(c, node_id)]
    ran = [c for c in selected if c["status"] != "skipped"]
    failed = [c for c in ran if c["status"] == "failed"]
    if not cases:
        return "broken", 0, 0, "the test report has no test cases"
    if not selected:
        return "broken", 0, 0, f"test '{node_id}' is not in the test report"
    if not ran:
        return "broken", 0, 0, "every matching test was skipped"
    if failed:
        return "failed", len(ran), len(failed), f"{len(failed)} of {len(ran)} test(s) failed"
    return "passed", len(ran), 0, f"{len(ran)} test(s) passed"


def _runner_missing(command: list[str], output: str) -> bool:
    """True when `python -m <module>` failed because <module> is not installed."""
    if "-m" not in command[:-1]:
        return False
    module = command[command.index("-m") + 1]
    return f"No module named {module}" in output


def _report_snapshot(pattern: str, cwd: Path) -> dict[str, float]:
    path = Path(pattern)
    full = str(path if path.is_absolute() else cwd / path)
    return {p: os.path.getmtime(p) for p in glob.glob(full, recursive=True)}


def _new_reports(pattern: str, cwd: Path, before: dict[str, float]) -> list[Path]:
    """Reports written by this run: new files, or files whose mtime changed.

    Runners like Maven write to a fixed folder, so reports from an earlier run
    are still there; they must never count as evidence for this one.
    """
    after = _report_snapshot(pattern, cwd)
    return [Path(p) for p, mtime in after.items() if before.get(p) != mtime]


def run_tests(cwd: Path, targets: list[str], config: dict, python: str | None = None,
              env: dict | None = None, node_id: str | None = None) -> dict:
    """Run the configured tests and return a CLI-recorded evidence dict."""
    settings = runner_settings(config)
    report_dir = Path(tempfile.mkdtemp(prefix="antibody-report-"))
    report = str(report_dir / "junit.xml")
    command = build_command(settings, targets, Path(cwd), python, report)
    run_env = dict(env if env is not None else os.environ)
    for key, value in settings.get("test_env", {}).items():
        run_env[key] = value.replace("{report}", report)

    report_pattern = settings.get("test_report", "").replace("{report}", report)
    before = _report_snapshot(report_pattern, Path(cwd)) if report_pattern else {}
    started = time.monotonic()
    timed_out = False
    try:
        # shell=False needs the real executable name on Windows (npx.cmd, mvn.cmd).
        executable = shutil.which(command[0], path=run_env.get("PATH")) or command[0]
        result = subprocess.run([executable, *command[1:]], cwd=cwd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace",
                                timeout=config.get("test_timeout_s", 300), check=False, env=run_env)
        exit_code, output = result.returncode, (result.stdout + result.stderr)
    except subprocess.TimeoutExpired as exc:
        exit_code, timed_out = 124, True
        output = f"Timed out after {exc.timeout}s\n{exc.stdout or ''}{exc.stderr or ''}"
    except FileNotFoundError:
        exit_code = 127
        output = f"Test runner not found: {command[0]}"

    evidence_from = "junit_report" if settings.get("test_report") else "exit_code"
    tests_run = tests_failed = None
    if timed_out:
        outcome, detail = "broken", "the test run timed out"
    elif evidence_from == "junit_report":
        files = _new_reports(report_pattern, Path(cwd), before)
        if exit_code in settings.get("broken_exit_codes", []):
            outcome, detail = "broken", f"the runner reported a broken run (exit {exit_code})"
        elif not files:
            outcome, detail = "broken", (f"no test report was written (exit {exit_code}): the tests did not "
                                         "run, e.g. a compile error or a missing runner")
        else:
            outcome, tests_run, tests_failed, detail = classify_report(parse_junit(files), node_id)
    else:
        if exit_code == 1 and _runner_missing(command, output):
            # `python -m pytest` exits 1 when pytest is not installed, which would
            # look like a real test failure. Report it as a usage error instead.
            exit_code = 4
            output += "\nAntibody: the test runner is not installed for this interpreter."
        outcome = {0: "passed", 1: "failed"}.get(exit_code, "broken")
        detail = f"exit {exit_code}: {PYTEST_EXIT_MEANING.get(exit_code, 'unexpected exit code')}"
    shutil.rmtree(report_dir, ignore_errors=True)

    return {
        "exit_code": exit_code,
        "passed": outcome == "passed",
        "outcome": outcome,
        "tests_run": tests_run,
        "tests_failed": tests_failed,
        "evidence_from": evidence_from,
        "detail": detail,
        "duration_s": round(time.monotonic() - started, 2),
        "output_tail": output[-2000:],
        "recorded_at": now_iso(),
        "recorded_by": "antibody-cli",
    }
