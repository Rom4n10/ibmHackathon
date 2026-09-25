"""Phase 3: attack the defenses with realistic variants and measure immunity.

Each variant is a patch written by Bob that re-introduces the same mistake in
a different shape. The CLI applies every patch in an isolated git worktree
(the developer's checkout is never touched) and checks whether the defenses
catch it:

    detected by "rule"   the Semgrep rule reports the variant's target file
    detected by "tests"  the test suite fails with a real failure (exit 1)

Immunity Score = detected variants / valid variants.

Round 0 runs without a rule: it measures the defenses the repo already had.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .prove import run_tests
from .runs import git, load_config, log_event, now_iso, run_dir
from .schema import read_json, write_json


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _semgrep_hits(worktree: Path, rule: Path, target_file: str, semgrep: str) -> tuple[bool, str]:
    command = [semgrep, "scan", "--config", str(rule), "--json", "--quiet",
               "--metrics=off", target_file]
    result = subprocess.run(command, cwd=worktree, capture_output=True, text=True, check=False)
    if result.returncode not in (0, 1):
        return False, f"semgrep error (exit {result.returncode}): {result.stderr.strip()[-300:]}"
    try:
        findings = json.loads(result.stdout or "{}").get("results", [])
    except json.JSONDecodeError:
        return False, "semgrep returned invalid JSON"
    target = Path(target_file).as_posix()
    hits = [f for f in findings if Path(f.get("path", "")).as_posix().endswith(target)]
    return bool(hits), f"rule matched {len(hits)} time(s)" if hits else "rule did not match"


def _worktree_env(worktree: Path) -> dict:
    """Make the worktree's code win over an editable install of the main checkout.

    If the target project is installed with `pip install -e .`, imports would
    resolve to the developer's checkout and every variant would look "escaped".
    PYTHONPATH entries come before site-packages, so the patched code is used.
    """
    env = dict(os.environ)
    paths = [str(worktree)]
    if (worktree / "src").is_dir():
        paths.insert(0, str(worktree / "src"))
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def _dirty_outside_antibody(repo: Path) -> tuple[list[str], list[str]]:
    """Return (modified tracked files, untracked files), ignoring .antibody/.

    The :(exclude) magic pathspec is not supported by all Git builds on Windows
    (e.g. repos inside paths with spaces such as OneDrive/Escritorio).
    We fall back to a plain 'git status --porcelain' and filter in Python.
    """
    status = git(repo, "status", "--porcelain", "--", ".", ":(exclude).antibody", check=False)
    if not status:
        # Fallback: :(exclude) may not be supported; filter .antibody/ manually.
        status = git(repo, "status", "--porcelain", check=False)
    lines = [
        line for line in status.splitlines()
        if line.strip() and ".antibody" not in line
    ]
    untracked = [line[3:] for line in lines if line.startswith("??")]
    modified = [line for line in lines if not line.startswith("??")]
    return modified, untracked


def run_round(repo: Path, run_id: str, round_no: int, rule: str | None = None,
              tests: list[str] | None = None, python: str | None = None,
              allow_dirty: bool = False) -> dict:
    repo = Path(repo).resolve()
    config = load_config(repo)
    rdir = run_dir(repo, run_id)
    variants = read_json(rdir / "variants.json", "variants")["variants"]

    limit = config["max_variants"]
    if len(variants) > limit:
        print(f"[antibody] budget: using the first {limit} of {len(variants)} variants "
              f"(max_variants in .antibody/config.json)", file=sys.stderr)
        variants = variants[:limit]
    if round_no > config["max_vaccine_rounds"]:
        raise ValueError(f"Round {round_no} exceeds max_vaccine_rounds={config['max_vaccine_rounds']}")

    rule_path = None
    if rule:
        rule_path = (repo / rule).resolve() if not Path(rule).is_absolute() else Path(rule)
        if not rule_path.exists():
            raise FileNotFoundError(f"Rule not found: {rule}")
        if shutil.which(config["semgrep"]) is None:
            raise RuntimeError("Semgrep is not installed. Install it with: pip install semgrep")

    modified, untracked = _dirty_outside_antibody(repo)
    if modified and not allow_dirty:
        raise RuntimeError(
            "Uncommitted changes outside .antibody/. The vaccine runs on HEAD, so commit "
            "the fixes and tests first (or pass --allow-dirty):\n  " + "\n  ".join(modified[:10])
        )
    new_tests = [u for u in untracked if "test" in u.lower()]
    if new_tests:
        print("[antibody] warning: untracked test files are NOT part of the vaccine run "
              "(it runs on HEAD): " + ", ".join(new_tests[:5]), file=sys.stderr)

    tmp = Path(tempfile.mkdtemp(prefix="antibody-wt-"))
    worktree = tmp / "wt"
    git(repo, "worktree", "add", "--detach", str(worktree), "HEAD")
    test_env = _worktree_env(worktree)
    results = []
    try:
        for variant in variants:
            git(worktree, "checkout", "--", ".", check=False)
            git(worktree, "clean", "-fdq", check=False)
            patch = (rdir / variant["patch"]).resolve()
            applied = subprocess.run(["git", "apply", str(patch)], cwd=worktree,
                                     capture_output=True, text=True, check=False)
            if applied.returncode != 0:
                results.append({"variant_id": variant["id"], "status": "invalid", "detected_by": [],
                                "detail": f"patch does not apply: {applied.stderr.strip()[-200:]}"})
                continue

            detected_by, details = [], []
            if rule_path:
                hit, detail = _semgrep_hits(worktree, rule_path, variant["target_file"], config["semgrep"])
                details.append(detail)
                if hit:
                    detected_by.append("rule")

            evidence = run_tests(worktree, tests or [], config, python, env=test_env)
            if evidence["exit_code"] == 1:
                detected_by.append("tests")
                details.append("tests failed")
            elif evidence["exit_code"] == 0:
                details.append("tests passed")
            else:
                results.append({"variant_id": variant["id"], "status": "invalid", "detected_by": [],
                                "detail": f"variant breaks the test run itself (exit {evidence['exit_code']}); "
                                          "not a realistic variant"})
                continue

            results.append({"variant_id": variant["id"],
                            "status": "detected" if detected_by else "escaped",
                            "detected_by": detected_by, "detail": "; ".join(details)})
    finally:
        git(repo, "worktree", "remove", "--force", str(worktree), check=False)
        shutil.rmtree(tmp, ignore_errors=True)

    valid = sum(1 for r in results if r["status"] != "invalid")
    detected = sum(1 for r in results if r["status"] == "detected")
    record = {
        "run_id": run_id,
        "round": round_no,
        "rule_file": (rule_path.relative_to(repo).as_posix() if rule_path.is_relative_to(repo)
                      else Path(rule).as_posix()) if rule_path else None,
        "rule_sha256": _sha256(rule_path) if rule_path else None,
        "tests_target": tests or [],
        "results": results,
        "valid": valid,
        "detected": detected,
        "score": round(detected / valid, 4) if valid else 0.0,
        "recorded_at": now_iso(),
    }
    write_json(rdir / "vaccine" / f"round_{round_no}.json", record, "vaccine_round")
    escaped = [r["variant_id"] for r in results if r["status"] == "escaped"]
    log_event(repo, run_id, "vaccine_round",
              f"Round {round_no}: immunity {record['score']:.0%} ({detected}/{valid})"
              + (f", escaped: {', '.join(escaped)}" if escaped else ""))
    return record


def load_rounds(repo: Path, run_id: str) -> list[dict]:
    rounds = [read_json(p, "vaccine_round") for p in (run_dir(repo, run_id) / "vaccine").glob("round_*.json")]
    return sorted(rounds, key=lambda r: r["round"])
