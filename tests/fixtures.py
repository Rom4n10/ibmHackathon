"""Shared test helpers: disposable git repos and sample-run fixtures."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path

# A small stand-in for pytest that reproduces its exit codes (0 pass, 1 failure,
# 2 import error, 5 no tests) so the suite also runs where pytest is not installed.
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


# The run id used in all sample-run fixture files
SAMPLE_RUN_ID = "20260926-101500"

# Path to the sample-run fixtures (relative to this file)
_FIXTURES_DIR = Path(__file__).parent.parent / "examples" / "sample-run"


def make_temp_repo(sample_run: bool = False) -> Path:
    """Create a disposable git repo in a temp dir and return its path.

    Callers are responsible for cleanup (use in a try/finally or
    unittest.TestCase.addCleanup).
    """
    tmp = Path(tempfile.mkdtemp(prefix="antibody-test-"))
    subprocess.run(["git", "init", str(tmp)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@antibody.test"],
        cwd=tmp, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Antibody Test"],
        cwd=tmp, check=True, capture_output=True,
    )
    # Create an initial commit so HEAD exists (needed for worktree commands)
    (tmp / "README.md").write_text("test repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=tmp, check=True, capture_output=True,
    )

    if sample_run:
        run_dir = tmp / ".antibody" / "runs" / SAMPLE_RUN_ID
        run_dir.mkdir(parents=True)
        (run_dir / "verdicts").mkdir()
        (run_dir / "vaccine").mkdir()
        (run_dir / "variants").mkdir()
        # Copy every file from examples/sample-run/ into the run dir
        for src in _FIXTURES_DIR.iterdir():
            if src.is_file():
                shutil.copyfile(src, run_dir / src.name)
        # Copy subdirs (verdicts, vaccine, variants)
        for subdir in ("verdicts", "vaccine", "variants"):
            src_subdir = _FIXTURES_DIR / subdir
            if src_subdir.is_dir():
                for src in src_subdir.iterdir():
                    if src.is_file():
                        shutil.copyfile(src, run_dir / subdir / src.name)
        # Write config.json
        config = {
            "max_candidates": 6, "max_variants": 6, "max_vaccine_rounds": 3,
            "test_command": ["{python}", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            "test_timeout_s": 300, "semgrep": "semgrep",
        }
        (tmp / ".antibody" / "config.json").write_text(
            json.dumps(config, indent=2), encoding="utf-8"
        )

    return tmp


def use_fake_runner(repo: Path) -> None:
    """Point an initialized repo's test_command at FAKE_RUNNER instead of pytest."""
    (repo / "fake_runner.py").write_text(FAKE_RUNNER, encoding="utf-8")
    config_path = repo / ".antibody" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["test_command"] = ["{python}", "fake_runner.py"]
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
