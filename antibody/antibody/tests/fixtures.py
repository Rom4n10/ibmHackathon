"""Shared test helpers: disposable git repos and sample-run fixtures."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

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
