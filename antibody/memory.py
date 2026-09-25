"""Phase 4: turn a run into a permanent antibody, and build scoreboard data.

Privacy note: antibodies never store author names or emails from git history.
They record what broke and how it was fixed, not who wrote it.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from .runs import antibody_root, log_event, now_iso, run_dir
from .schema import read_json, validate, write_json
from .vaccine import load_rounds


def _verdicts(repo: Path, run_id: str) -> dict[str, dict]:
    folder = run_dir(repo, run_id) / "verdicts"
    return {p.stem: read_json(p, "verdict") for p in sorted(folder.glob("c*.json"))}


def _candidates(repo: Path, run_id: str) -> list[dict]:
    path = run_dir(repo, run_id) / "candidates.json"
    return read_json(path, "candidates")["candidates"] if path.exists() else []


def _twins(repo: Path, run_id: str) -> list[dict]:
    verdicts = _verdicts(repo, run_id)
    twins = []
    for cand in _candidates(repo, run_id):
        verdict = verdicts.get(cand["id"])
        if verdict and verdict["status"] in ("confirmed", "fixed"):
            twins.append({
                "candidate_id": cand["id"],
                "file": cand["file"],
                "line": cand["line"],
                "status": verdict["status"],
                "test_file": (verdict.get("test") or {}).get("file"),
            })
    return twins


def _render_history(manifest: dict, diagnosis: dict) -> str:
    rc = diagnosis["root_cause"]
    src = manifest["source"]
    lines = [
        f"# Antibody {manifest['id']}: {rc['title']}",
        "",
        f"Created {manifest['created_at']} from {src.get('type')} `{src.get('ref')}`.",
        "",
        "## What broke",
        "",
        rc["why_it_breaks"],
        "",
        f"**Pattern:** {rc['pattern']}",
        "",
        "**Triggers when:** " + "; ".join(rc["trigger_conditions"]),
        "",
        "## How it was fixed",
        "",
        rc["fix_strategy"],
        "",
        f"Original instance: `{diagnosis['original_instance']['file']}:{diagnosis['original_instance']['line']}`",
        "",
        "## Twins found and proven",
        "",
    ]
    if manifest["twins"]:
        lines += ["| Twin | Location | Status | Test |", "|---|---|---|---|"]
        for t in manifest["twins"]:
            lines.append(f"| {t['candidate_id']} | `{t['file']}:{t['line']}` | {t['status']} | "
                         f"`{t.get('test_file') or '-'}` |")
    else:
        lines.append("No twins were proven in this run.")
    lines += ["", "## Immunity", ""]
    if manifest["immunity"]:
        lines += ["| Round | Detected | Immunity |", "|---|---|---|"]
        for r in manifest["immunity"]:
            label = "0 (before Antibody)" if r["round"] == 0 else str(r["round"])
            lines.append(f"| {label} | {r['detected']}/{r['valid']} | {r['score']:.0%} |")
    else:
        lines.append("No vaccine rounds recorded.")
    lines += ["", "## Defenses", "",
              f"- Semgrep rule: `{manifest['rule_file']}`",
              "- Regression tests: listed in the twins table above.", ""]
    return "\n".join(lines)


def finalize(repo: Path, run_id: str, slug: str, rule: str, summary: str | None = None,
             links: list[str] | None = None) -> Path:
    repo = Path(repo).resolve()
    rdir = run_dir(repo, run_id)
    diagnosis = read_json(rdir / "diagnosis.json", "diagnosis")
    rule_path = (repo / rule).resolve()
    if not rule_path.exists():
        raise FileNotFoundError(f"Rule not found: {rule}")

    source = diagnosis["source"]
    rule_text = rule_path.read_text(encoding="utf-8")
    anchors = [a for a in (source.get("fix_commit"), source.get("ref")) if a]
    if not any(a[:7] in rule_text for a in anchors):
        print("[antibody] warning: the rule message does not reference the original fix or incident. "
              "Memory works best when the message says what happened last time.")

    folder_root = antibody_root(repo) / "antibodies"
    number = f"{len([p for p in folder_root.glob('[0-9][0-9][0-9]-*') if p.is_dir()]) + 1:03d}"
    folder = folder_root / f"{number}-{slug}"
    folder.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(rule_path, folder / "rule.yml")

    manifest = {
        "id": number,
        "slug": slug,
        "created_at": now_iso(),
        "run_id": run_id,
        "source": source,
        "root_cause": {"title": diagnosis["root_cause"]["title"],
                       "pattern": diagnosis["root_cause"]["pattern"]},
        "twins": _twins(repo, run_id),
        "rule_file": str((folder / "rule.yml").relative_to(repo)),
        "immunity": [{"round": r["round"], "score": r["score"], "valid": r["valid"],
                      "detected": r["detected"]} for r in load_rounds(repo, run_id)],
        "memory": {"summary": summary or diagnosis["root_cause"]["why_it_breaks"],
                   "fix_commit": source.get("fix_commit"), "links": links or []},
    }
    write_json(folder / "manifest.json", manifest, "manifest")
    (folder / "history.md").write_text(_render_history(manifest, diagnosis), encoding="utf-8")
    log_event(repo, run_id, "antibody_created", f"Antibody {number}-{slug} created")
    return folder


def _minutes_since(start: str, moment: str) -> float:
    delta = datetime.fromisoformat(moment) - datetime.fromisoformat(start)
    return round(max(delta.total_seconds(), 0) / 60, 2)


def build_scoreboard(repo: Path, run_id: str, repo_label: str | None = None) -> dict:
    repo = Path(repo).resolve()
    rdir = run_dir(repo, run_id)
    run = read_json(rdir / "run.json")
    diagnosis = read_json(rdir / "diagnosis.json", "diagnosis")
    verdicts = _verdicts(repo, run_id)
    variants_path = rdir / "variants.json"
    variant_info = {v["id"]: v for v in read_json(variants_path, "variants")["variants"]} \
        if variants_path.exists() else {}

    twins = []
    for cand in _candidates(repo, run_id):
        verdict = verdicts.get(cand["id"], {"status": "unproven"})
        twins.append({"id": cand["id"], "file": cand["file"], "line": cand["line"],
                      "status": verdict["status"], "reasoning": cand["reasoning"]})

    rounds = []
    for r in load_rounds(repo, run_id):
        label = "Before Antibody" if r["rule_file"] is None else f"Round {r['round']}"
        rounds.append({
            "round": r["round"], "label": label, "score": r["score"],
            "variants": [{"id": res["variant_id"],
                          "kind": variant_info.get(res["variant_id"], {}).get("kind", "other"),
                          "description": variant_info.get(res["variant_id"], {}).get("description", ""),
                          "status": res["status"], "detected_by": res["detected_by"]}
                         for res in r["results"]],
        })

    start = run["created_at"]
    timeline = [{"t_min": _minutes_since(start, e["at"]), "kind": e["kind"], "label": e["label"]}
                for e in run["events"]]
    scoreboard = {
        "run_id": run_id,
        "title": diagnosis["root_cause"]["title"],
        "repo": repo_label,
        "root_cause": {"title": diagnosis["root_cause"]["title"],
                       "pattern": diagnosis["root_cause"]["pattern"]},
        "original": {"file": diagnosis["original_instance"]["file"],
                     "line": diagnosis["original_instance"]["line"]},
        "twins": twins,
        "rounds": rounds,
        "timeline": timeline,
        "baseline": run.get("baseline"),
        "duration_minutes": timeline[-1]["t_min"] if timeline else 0,
    }
    validate("scoreboard", scoreboard)
    write_json(rdir / "scoreboard.json", scoreboard)
    return scoreboard
