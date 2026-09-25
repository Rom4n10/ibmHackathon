"""Runs, configuration, event log and git helpers.

Layout inside the target repository:

    .antibody/
      config.json                 budgets and test profile (see runners.py)
      runs/<run_id>/
        run.json                  source, timestamps, event log
        diagnosis.json            phase 1 (Bob)
        candidates.json           phase 2 (Bob)
        verdicts/<cid>.json       phase 2 evidence (CLI)
        variants.json             phase 3 (Bob)
        variants/<vid>.patch      phase 3 (Bob)
        rule.v<N>.yml             phase 3 rule versions (Bob)
        vaccine/round_<N>.json    phase 3 evidence (CLI)
        scoreboard.json           for ui/scoreboard.html (CLI)
      antibodies/<NNN-slug>/      phase 4, permanent (CLI)
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .schema import read_json, write_json

ANTIBODY_DIR = ".antibody"

DEFAULT_CONFIG = {
    # Budgets keep Bobcoin usage predictable: every candidate and every
    # variant can cost a subagent spawn. Raise them only on purpose.
    "max_candidates": 6,
    "max_variants": 6,
    "max_vaccine_rounds": 3,
    # How tests are run and read: a profile from runners.PROFILES, detected by
    # `antibody init`. Any runner key (test_command, test_report, ...) set here
    # overrides the profile. No profile and no test_command means plain pytest.
    "profile": None,
    "test_timeout_s": 300,
    "semgrep": "semgrep",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def antibody_root(repo: Path) -> Path:
    return Path(repo) / ANTIBODY_DIR


def run_dir(repo: Path, run_id: str) -> Path:
    path = antibody_root(repo) / "runs" / run_id
    if not path.is_dir():
        raise FileNotFoundError(f"Run '{run_id}' not found at {path}")
    return path


def load_config(repo: Path) -> dict:
    path = antibody_root(repo) / "config.json"
    config = dict(DEFAULT_CONFIG)
    if path.exists():
        config.update(read_json(path))
    return config


def git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=False
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def ensure_git_repo(repo: Path) -> None:
    if git(repo, "rev-parse", "--is-inside-work-tree", check=False) != "true":
        raise RuntimeError(f"{repo} is not a git repository")


def init_repo(repo: Path, profile: str | None = None) -> Path:
    """Create .antibody/. The test profile is `profile`, or detected from the repo."""
    from .runners import PROFILES, detect_profiles

    ensure_git_repo(repo)
    if profile is not None and profile not in PROFILES:
        raise ValueError(f"Unknown test profile '{profile}'. Known: {', '.join(PROFILES)}")
    root = antibody_root(repo)
    (root / "runs").mkdir(parents=True, exist_ok=True)
    (root / "antibodies").mkdir(parents=True, exist_ok=True)
    config = root / "config.json"
    if not config.exists():
        detected = detect_profiles(repo)
        write_json(config, {**DEFAULT_CONFIG, "profile": profile or (detected[0] if detected else None)})
    return root


def new_run(repo: Path, source_type: str, ref: str, issue: str | None = None) -> str:
    ensure_git_repo(repo)
    init_repo(repo)
    fix_commit = parent_commit = None
    if source_type in ("fix_commit", "pull_request"):
        fix_commit = git(repo, "rev-parse", ref)
        parent_commit = git(repo, "rev-parse", f"{fix_commit}^", check=False) or None

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = antibody_root(repo) / "runs" / run_id
    (path / "verdicts").mkdir(parents=True)
    (path / "variants").mkdir()
    (path / "vaccine").mkdir()
    write_json(
        path / "run.json",
        {
            "run_id": run_id,
            "created_at": now_iso(),
            "source": {
                "type": source_type,
                "ref": ref,
                "fix_commit": fix_commit,
                "parent_commit": parent_commit,
                "issue": issue,
            },
            "baseline": None,
            "events": [{"at": now_iso(), "kind": "run_started", "label": f"Run started from {source_type} {ref}"}],
        },
    )
    return run_id


def log_event(repo: Path, run_id: str, kind: str, label: str) -> None:
    path = run_dir(repo, run_id) / "run.json"
    run = read_json(path)
    run["events"].append({"at": now_iso(), "kind": kind, "label": label})
    write_json(path, run)


def set_baseline(repo: Path, run_id: str, minutes: float, twins: int) -> None:
    path = run_dir(repo, run_id) / "run.json"
    run = read_json(path)
    run["baseline"] = {"manual_minutes": minutes, "manual_twins": twins}
    write_json(path, run)


def latest_run(repo: Path) -> str:
    runs = sorted(p.name for p in (antibody_root(repo) / "runs").glob("*") if p.is_dir())
    if not runs:
        raise FileNotFoundError("No runs yet. Start one with: antibody new --commit <fix-sha>")
    return runs[-1]
