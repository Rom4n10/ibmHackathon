"""Phase 2 evidence: run a candidate's test and record red/green proof.

A twin is only "confirmed" when its test ran and failed. A test that never ran
(compile, import or syntax errors, a missing runner, a test the report does not
contain) proves nothing, so it never confirms a twin. How "ran and failed" is
read for each language lives in runners.py.
"""

from __future__ import annotations

from pathlib import Path

from .runners import run_tests, runner_settings
from .runs import load_config, log_event, run_dir
from .schema import read_json, write_json


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
    # Report-based profiles run the whole file and pick the node from the report;
    # pytest's exit codes can only speak for the node if it is the only target.
    exit_code_only = not runner_settings(config).get("test_report")
    target = f"{test_file}::{node_id}" if node_id and exit_code_only else test_file
    evidence = run_tests(Path(repo), [target], config, python, node_id=node_id)
    outcome, detail = evidence["outcome"], evidence["detail"]

    if phase == "red":
        verdict["red"] = evidence
        if outcome == "failed":
            verdict["status"], verdict["reason"] = "confirmed", "Test fails on current code: bug demonstrated."
            log_event(repo, run_id, "twin_confirmed", f"{candidate_id} confirmed with a failing test")
        elif outcome == "passed":
            verdict["status"], verdict["reason"] = "unproven", "Test passes on current code: bug not demonstrated."
        else:
            verdict["status"] = "unproven"
            verdict["reason"] = f"Test is broken, not a proof ({detail})."
    elif phase == "green":
        if verdict["status"] not in ("confirmed", "fixed"):
            raise ValueError(f"{candidate_id} must be confirmed (red) before recording green evidence")
        verdict["green"] = evidence
        if fix_summary:
            verdict["fix_summary"] = fix_summary
        if outcome == "passed":
            verdict["status"], verdict["reason"] = "fixed", "Test passes after the fix."
            log_event(repo, run_id, "twin_fixed", f"{candidate_id} fixed, test is green")
        else:
            verdict["status"] = "confirmed"
            verdict["reason"] = f"Fix not verified yet ({detail})."
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
