"""Phase 2 evidence: run a candidate's test and record red/green proof.

A twin is only "confirmed" when its test fails with a real assertion failure
(pytest exit code 1). Collection errors, import errors or syntax errors
(exit codes 2-5) prove nothing, so they never confirm a twin.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from .runs import load_config, log_event, now_iso, run_dir
from .schema import read_json, write_json

PYTEST_EXIT_MEANING = {
    0: "all tests passed",
    1: "tests ran and at least one failed",
    2: "execution interrupted (often an import or syntax error)",
    3: "internal pytest error",
    4: "pytest usage error (bad path or option)",
    5: "no tests were collected",
}


def build_test_command(config: dict, targets: list[str], python: str | None = None) -> list[str]:
    interpreter = python or os.environ.get("ANTIBODY_PYTHON") or sys.executable
    return [part.replace("{python}", interpreter) for part in config["test_command"]] + list(targets)


def run_tests(cwd: Path, targets: list[str], config: dict, python: str | None = None,
              env: dict | None = None) -> dict:
    """Run the configured test command and return a CLI-recorded evidence dict."""
    command = build_test_command(config, targets, python)
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=config.get("test_timeout_s", 300),
            check=False,
            env=env,
        )
        exit_code, output = result.returncode, (result.stdout + result.stderr)
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        output = f"Timed out after {exc.timeout}s\n{exc.stdout or ''}{exc.stderr or ''}"
    return {
        "exit_code": exit_code,
        "passed": exit_code == 0,
        "duration_s": round(time.monotonic() - started, 2),
        "output_tail": output[-2000:],
        "recorded_at": now_iso(),
        "recorded_by": "antibody-cli",
    }


def _verdict_path(repo: Path, run_id: str, candidate_id: str) -> Path:
    return run_dir(repo, run_id) / "verdicts" / f"{candidate_id}.json"


def _known_candidates(repo: Path, run_id: str) -> set[str]:
    data = read_json(run_dir(repo, run_id) / "candidates.json", "candidates")
    return {c["id"] for c in data["candidates"]}


def _load_verdict(repo: Path, run_id: str, candidate_id: str) -> dict:
    path = _verdict_path(repo, run_id, candidate_id)
    if path.exists():
        return read_json(path, "verdict")
    return {"candidate_id": candidate_id, "status": "unproven", "reason": None,
            "test": None, "red": None, "green": None, "fix_summary": None}


def prove(repo: Path, run_id: str, candidate_id: str, test_file: str, phase: str,
          node_id: str | None = None, fix_summary: str | None = None,
          python: str | None = None) -> dict:
    """Record red (bug demonstrated) or green (fix verified) evidence."""
    if candidate_id not in _known_candidates(repo, run_id):
        raise ValueError(f"{candidate_id} is not listed in candidates.json")
    if not (Path(repo) / test_file).exists():
        raise FileNotFoundError(f"Test file not found: {test_file}")

    config = load_config(repo)
    verdict = _load_verdict(repo, run_id, candidate_id)
    verdict["test"] = {"file": test_file, "node_id": node_id}
    target = f"{test_file}::{node_id}" if node_id else test_file
    evidence = run_tests(Path(repo), [target], config, python)
    meaning = PYTEST_EXIT_MEANING.get(evidence["exit_code"], "unexpected exit code")

    if phase == "red":
        verdict["red"] = evidence
        if evidence["exit_code"] == 1:
            verdict["status"], verdict["reason"] = "confirmed", "Test fails on current code: bug demonstrated."
            log_event(repo, run_id, "twin_confirmed", f"{candidate_id} confirmed with a failing test")
        elif evidence["exit_code"] == 0:
            verdict["status"], verdict["reason"] = "unproven", "Test passes on current code: bug not demonstrated."
        else:
            verdict["status"] = "unproven"
            verdict["reason"] = f"Test is broken, not a proof (exit {evidence['exit_code']}: {meaning})."
    elif phase == "green":
        if verdict["status"] not in ("confirmed", "fixed"):
            raise ValueError(f"{candidate_id} must be confirmed (red) before recording green evidence")
        verdict["green"] = evidence
        if fix_summary:
            verdict["fix_summary"] = fix_summary
        if evidence["exit_code"] == 0:
            verdict["status"], verdict["reason"] = "fixed", "Test passes after the fix."
            log_event(repo, run_id, "twin_fixed", f"{candidate_id} fixed, test is green")
        else:
            verdict["status"] = "confirmed"
            verdict["reason"] = f"Fix not verified yet (exit {evidence['exit_code']}: {meaning})."
    else:
        raise ValueError("phase must be 'red' or 'green'")

    write_json(_verdict_path(repo, run_id, candidate_id), verdict, "verdict")
    return verdict


def mark(repo: Path, run_id: str, candidate_id: str, status: str, reason: str) -> dict:
    """Mark a candidate as suspected (could not be tested) or rejected (not a twin)."""
    if status not in ("suspected", "rejected"):
        raise ValueError("status must be 'suspected' or 'rejected'")
    if candidate_id not in _known_candidates(repo, run_id):
        raise ValueError(f"{candidate_id} is not listed in candidates.json")
    verdict = _load_verdict(repo, run_id, candidate_id)
    verdict["status"], verdict["reason"] = status, reason
    write_json(_verdict_path(repo, run_id, candidate_id), verdict, "verdict")
    log_event(repo, run_id, f"twin_{status}", f"{candidate_id} {status}: {reason}")
    return verdict
