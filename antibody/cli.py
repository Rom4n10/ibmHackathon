"""Command line interface. Bob calls these commands from the Antibody mode;
humans can call them too. Every command prints a short, parseable summary.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from importlib import resources
from pathlib import Path

from . import __version__
from .memory import build_scoreboard, finalize
from .prove import mark, prove
from .runs import init_repo, latest_run, new_run, run_dir, set_baseline
from .schema import SCHEMA_NAMES, ContractError, read_json
from .vaccine import load_rounds, run_round


def _repo(args) -> Path:
    return Path(args.repo).resolve()


def _run(args) -> str:
    return args.run or latest_run(_repo(args))


def _install_bob_mode(repo: Path, force: bool) -> list[str]:
    template = Path(str(resources.files("antibody") / "bob_template" / "bob"))
    target = repo / ".bob"
    copied, skipped = [], []
    for src in sorted(template.rglob("*")):
        if src.is_dir():
            continue
        dest = target / src.relative_to(template)
        if dest.exists() and not force:
            skipped.append(str(dest.relative_to(repo)))
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        copied.append(str(dest.relative_to(repo)))
    for path in skipped:
        print(f"  kept existing {path} (use --force to overwrite, or merge by hand)")
    return copied


def cmd_init(args) -> int:
    repo = _repo(args)
    root = init_repo(repo)
    print(f"Initialized {root.relative_to(repo)}/")
    if not args.no_bob:
        copied = _install_bob_mode(repo, args.force)
        print(f"Installed the Antibody Bob mode ({len(copied)} files in .bob/). Reload Bob IDE to see it.")
    return 0


def cmd_new(args) -> int:
    repo = _repo(args)
    if args.commit:
        run_id = new_run(repo, "fix_commit", args.commit, args.issue)
    else:
        run_id = new_run(repo, args.source_type, args.document, args.issue)
    print(f"run_id={run_id}")
    print(f"folder={run_dir(repo, run_id).relative_to(repo)}")
    return 0


def cmd_status(args) -> int:
    repo, run_id = _repo(args), _run(args)
    rdir = run_dir(repo, run_id)
    print(f"run {run_id}")
    for name, schema in (("diagnosis.json", "diagnosis"), ("candidates.json", "candidates"),
                         ("variants.json", "variants")):
        path = rdir / name
        if not path.exists():
            print(f"  {name:<16} missing")
            continue
        try:
            read_json(path, schema)
            print(f"  {name:<16} ok")
        except ContractError as exc:
            print(f"  {name:<16} INVALID\n    {exc}")
    verdicts = sorted((rdir / "verdicts").glob("c*.json"))
    counts: dict[str, int] = {}
    for v in verdicts:
        status = read_json(v)["status"]
        counts[status] = counts.get(status, 0) + 1
    print("  verdicts        " + (", ".join(f"{k}={n}" for k, n in sorted(counts.items())) or "none"))
    for r in load_rounds(repo, run_id):
        print(f"  vaccine round {r['round']}  immunity {r['score']:.0%} ({r['detected']}/{r['valid']})")
    return 0


def cmd_prove(args) -> int:
    verdict = prove(_repo(args), _run(args), args.candidate, args.test, args.phase,
                    args.node, args.fix_summary, args.python)
    print(f"{args.candidate} status={verdict['status']}")
    print(f"reason: {verdict['reason']}")
    evidence = verdict.get(args.phase) or {}
    if evidence and evidence.get("exit_code") not in (0, 1):
        print("--- test output (tail) ---")
        print(evidence["output_tail"][-800:])
    return 0 if verdict["status"] in ("confirmed", "fixed") else 3


def cmd_mark(args) -> int:
    status = "suspected" if args.suspected else "rejected"
    verdict = mark(_repo(args), _run(args), args.candidate, status, args.reason)
    print(f"{args.candidate} status={verdict['status']}")
    return 0


def cmd_vaccine(args) -> int:
    record = run_round(_repo(args), _run(args), args.round, args.rule, args.tests,
                       args.python, args.allow_dirty)
    print(f"round={record['round']} immunity={record['score']:.0%} "
          f"detected={record['detected']}/{record['valid']}")
    for r in record["results"]:
        by = "+".join(r["detected_by"]) or "-"
        print(f"  {r['variant_id']}  {r['status']:<9} by={by:<11} {r.get('detail', '')}")
    return 0


def cmd_finalize(args) -> int:
    folder = finalize(_repo(args), _run(args), args.slug, args.rule, args.summary, args.link)
    print(f"antibody={folder.relative_to(_repo(args))}")
    return 0


def cmd_scoreboard(args) -> int:
    repo, run_id = _repo(args), _run(args)
    data = build_scoreboard(repo, run_id, args.repo_label)
    out = run_dir(repo, run_id) / "scoreboard.json"
    print(f"scoreboard={out.relative_to(repo)} twins={len(data['twins'])} rounds={len(data['rounds'])}")
    print("Open ui/scoreboard.html and load this file.")
    return 0


def cmd_baseline(args) -> int:
    set_baseline(_repo(args), _run(args), args.minutes, args.twins)
    print(f"baseline recorded: {args.minutes} min by hand, {args.twins} twin(s) found")
    return 0


def cmd_validate(args) -> int:
    read_json(Path(args.file), args.schema)
    print(f"{args.file}: valid {args.schema}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="antibody", description="An immune system for your repository.")
    parser.add_argument("--version", action="version", version=f"antibody {__version__}")
    parser.add_argument("--repo", default=".", help="Target repository (default: current directory)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="Create .antibody/ and install the Bob mode into .bob/")
    p.add_argument("--no-bob", action="store_true", help="Do not install the Bob mode files")
    p.add_argument("--force", action="store_true", help="Overwrite existing .bob files")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("new", help="Start a run from a fix commit or a document")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--commit", help="The fix commit (SHA, branch or ref)")
    group.add_argument("--document", help="Path to a postmortem or incident log")
    p.add_argument("--source-type", choices=["postmortem", "incident_log"], default="postmortem")
    p.add_argument("--issue", help="Issue URL or id linked to the fix")
    p.set_defaults(func=cmd_new)

    def with_run(p):
        p.add_argument("--run", help="Run id (default: latest run)")
        return p

    p = with_run(sub.add_parser("status", help="Show the state of a run and validate its files"))
    p.set_defaults(func=cmd_status)

    p = with_run(sub.add_parser("prove", help="Run a candidate's test and record red/green evidence"))
    p.add_argument("candidate", help="Candidate id, e.g. c01")
    p.add_argument("--test", required=True, help="Repo-relative test file")
    p.add_argument("--node", help="Test node inside the file, e.g. test_name")
    p.add_argument("--phase", choices=["red", "green"], required=True)
    p.add_argument("--fix-summary", help="One line describing the fix (green phase)")
    p.add_argument("--python", help="Interpreter of the target project (default: $ANTIBODY_PYTHON)")
    p.set_defaults(func=cmd_prove)

    p = with_run(sub.add_parser("mark", help="Mark a candidate as suspected or rejected"))
    p.add_argument("candidate")
    state = p.add_mutually_exclusive_group(required=True)
    state.add_argument("--suspected", action="store_true")
    state.add_argument("--rejected", action="store_true")
    p.add_argument("--reason", required=True)
    p.set_defaults(func=cmd_mark)

    p = with_run(sub.add_parser("vaccine", help="Run one vaccine round and compute the Immunity Score"))
    p.add_argument("--round", type=int, required=True, help="0 = existing defenses, no rule")
    p.add_argument("--rule", help="Repo-relative Semgrep rule file (omit for round 0)")
    p.add_argument("--tests", nargs="*", help="Test targets (default: full suite)")
    p.add_argument("--python", help="Interpreter of the target project")
    p.add_argument("--allow-dirty", action="store_true", help="Run even with uncommitted changes")
    p.set_defaults(func=cmd_vaccine)

    p = with_run(sub.add_parser("finalize", help="Create the permanent antibody from a run"))
    p.add_argument("--slug", required=True, help="kebab-case name, e.g. naive-vs-aware-datetime")
    p.add_argument("--rule", required=True, help="Final rule file to keep")
    p.add_argument("--summary", help="Memory summary shown to future developers")
    p.add_argument("--link", action="append", help="Link to the issue, PR or postmortem (repeatable)")
    p.set_defaults(func=cmd_finalize)

    p = with_run(sub.add_parser("scoreboard", help="Build scoreboard.json for the UI"))
    p.add_argument("--repo-label", help="Name shown in the UI, e.g. owner/project")
    p.set_defaults(func=cmd_scoreboard)

    p = with_run(sub.add_parser("baseline", help="Record the manual search baseline for ROI"))
    p.add_argument("--minutes", type=float, required=True)
    p.add_argument("--twins", type=int, required=True)
    p.set_defaults(func=cmd_baseline)

    p = sub.add_parser("validate", help="Validate a JSON file against a contract")
    p.add_argument("file")
    p.add_argument("--schema", required=True, choices=SCHEMA_NAMES)
    p.set_defaults(func=cmd_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ContractError, FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"antibody: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
