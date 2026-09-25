"""End-to-end check of one test profile against its real test runner.

Copies tests/e2e/fixtures/<profile>/ into a temporary git repository and drives
the Antibody CLI through a whole run, checking every outcome proof depends on:

  red, failing test        -> confirmed (the bug is demonstrated)
  red, passing test        -> unproven, outcome "passed"
  red, test not in report  -> unproven, outcome "broken"
  red, file that does not compile or import -> unproven, outcome "broken"
                              (never confirmed: the core guarantee)
  green after the fix      -> fixed
  vaccine round 0 / 1      -> the variant is caught by the tests / the rule

Every fixture has the same bug, `age > 18` instead of `age >= 18`, so the only
thing that changes between languages is the runner.

Usage: python tests/e2e/run_e2e.py <profile>   (CI runs it for every profile:
.github/workflows/e2e.yml). It needs that profile's toolchain installed.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
BUG, FIX = "age > 18", "age >= 18"

JAVA_BROKEN = ("package demo;\n\nclass BrokenTest {\n    void broken() {\n        int a = ;\n    }\n}\n")
JS_BROKEN = 'const { x } = require("../src/no_such");\n\ntest("never runs", () => {\n  expect(x).toBe(1);\n});\n'

SPECS: dict[str, dict] = {
    "python-pytest": {
        "language": "python", "source": "src/calc.py", "test": "tests/test_calc.py",
        "bug_test": "test_adult_at_18", "ok_test": "test_adult_at_30",
        "broken": ("tests/test_broken.py", "import no_such_module\n\n\ndef test_x():\n    pass\n"),
    },
    "js-vitest": {
        "language": "javascript", "setup": [["npm", "install", "--no-audit", "--no-fund"]],
        "source": "src/calc.js", "test": "tests/calc.test.js",
        "bug_test": "adult at 18", "ok_test": "adult at 30",
        "broken": ("tests/broken.test.js", JS_BROKEN),
    },
    "js-jest": {
        "language": "javascript", "setup": [["npm", "install", "--no-audit", "--no-fund"]],
        "source": "src/calc.js", "test": "tests/calc.test.js",
        "bug_test": "adult at 18", "ok_test": "adult at 30",
        "broken": ("tests/broken.test.js", JS_BROKEN),
    },
    "java-maven": {
        "language": "java", "source": "src/main/java/demo/Calc.java", "test": "src/test/java/demo/CalcTest.java",
        "bug_test": "adultAt18", "ok_test": "adultAt30",
        "broken": ("src/test/java/demo/BrokenTest.java", JAVA_BROKEN),
    },
    "java-gradle": {
        "language": "java", "source": "src/main/java/demo/Calc.java", "test": "src/test/java/demo/CalcTest.java",
        "bug_test": "adultAt18", "ok_test": "adultAt30",
        "broken": ("src/test/java/demo/BrokenTest.java", JAVA_BROKEN),
    },
    "go-gotestsum": {
        "language": "go", "source": "calc.go", "test": "calc_test.go",
        "bug_test": "TestAdultAt18", "ok_test": "TestAdultAt30",
        "broken": ("broken_test.go", 'package calc\n\nimport "testing"\n\nfunc TestBroken(t *testing.T) {\n\tx :=\n}\n'),
    },
    "dotnet": {
        "language": "csharp", "source": "Calc.cs", "test": "CalcTests.cs",
        "bug_test": "AdultAt18", "ok_test": "AdultAt30",
        "broken": ("BrokenTests.cs", "namespace Demo;\n\npublic class BrokenTests\n{\n    [Fact]\n"
                                     "    public void Broken() { int a = ; }\n}\n"),
    },
    "rust-nextest": {
        "language": "rust", "source": "src/lib.rs", "test": "tests/calc.rs",
        "bug_test": "adult_at_18", "ok_test": "adult_at_30",
        "broken": ("tests/broken.rs", "#[test]\nfn broken() {\n    let a = ;\n}\n"),
    },
    "ruby-rspec": {
        "language": "ruby", "setup": [["bundle", "install"]],
        "source": "lib/calc.rb", "test": "spec/calc_spec.rb",
        "bug_test": "adult at 18", "ok_test": "adult at 30",
        "broken": ("spec/broken_spec.rb", 'require_relative "../lib/no_such"\n\nRSpec.describe "broken" do\n'
                                          '  it "never runs" do\n    expect(1).to eq(1)\n  end\nend\n'),
    },
    "php-phpunit": {
        "language": "php", "setup": [["composer", "install", "--no-interaction", "--no-progress"]],
        "source": "src/Calc.php", "test": "tests/CalcTest.php",
        "bug_test": "testAdultAt18", "ok_test": "testAdultAt30",
        "broken": ("tests/BrokenTest.php", "<?php\n\nuse PHPUnit\\Framework\\TestCase;\n\n"
                                           "final class BrokenTest extends TestCase\n{\n"
                                           "    public function testBroken(): void\n    {\n        $a = ;\n    }\n}\n"),
    },
}


def sh(cwd: Path, *cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    executable = shutil.which(cmd[0]) or cmd[0]
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    result = subprocess.run([executable, *cmd[1:]], cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", env=env, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed ({result.returncode}):\n{result.stdout}{result.stderr}")
    return result


class E2E:
    def __init__(self, profile: str, repo: Path):
        self.profile, self.spec, self.repo = profile, SPECS[profile], repo
        self.failures: list[str] = []
        self.run_id = ""

    def antibody(self, *args: str) -> subprocess.CompletedProcess:
        return sh(self.repo, sys.executable, "-m", "antibody", *args, check=False)

    @property
    def rdir(self) -> Path:
        return self.repo / ".antibody" / "runs" / self.run_id

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"\n         {detail}" if not ok and detail else ""))
        if not ok:
            self.failures.append(name)

    def prove(self, cid: str, test: str, phase: str, node: str | None = None) -> dict:
        args = ["prove", cid, "--test", test, "--phase", phase] + (["--node", node] if node else [])
        out = self.antibody(*args)
        path = self.rdir / "verdicts" / f"{cid}.json"
        if not path.exists():
            return {"status": "missing", "reason": out.stdout + out.stderr}
        return json.loads(path.read_text(encoding="utf-8"))

    def expect_verdict(self, name: str, verdict: dict, status: str, outcome: str, phase: str = "red") -> None:
        evidence = verdict.get(phase) or {}
        ok = verdict.get("status") == status and evidence.get("outcome") == outcome
        detail = (f"got status={verdict.get('status')} outcome={evidence.get('outcome')} "
                  f"({evidence.get('detail') or verdict.get('reason')})\n"
                  f"         output tail: {(evidence.get('output_tail') or '')[-1200:]}")
        self.check(f"{name}: {status} / {outcome}", ok, detail)

    def vaccine(self, round_no: int, rule: str | None = None) -> dict:
        args = ["vaccine", "--round", str(round_no)] + (["--rule", rule] if rule else [])
        out = self.antibody(*args)
        path = self.rdir / "vaccine" / f"round_{round_no}.json"
        if not path.exists():
            return {"results": [], "error": out.stdout + out.stderr}
        return json.loads(path.read_text(encoding="utf-8"))

    def run(self) -> int:
        spec, repo = self.spec, self.repo
        for command in spec.get("setup", []):
            sh(repo, *command)
        sh(repo, "git", "init", "-q", "-b", "main")
        sh(repo, "git", "config", "user.email", "e2e@example.invalid")
        sh(repo, "git", "config", "user.name", "Antibody E2E")
        sh(repo, "git", "add", "-A")
        sh(repo, "git", "commit", "-qm", "initial")

        init = self.antibody("init", "--no-bob")
        config = json.loads((repo / ".antibody" / "config.json").read_text(encoding="utf-8"))
        self.check("init detects the profile", config.get("profile") == self.profile,
                   f"detected {config.get('profile')!r}\n{init.stdout}{init.stderr}")
        config["profile"] = self.profile
        (repo / ".antibody" / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

        self.run_id = self.antibody("new", "--commit", "HEAD").stdout.split("run_id=")[1].split()[0]
        (self.rdir / "candidates.json").write_text(json.dumps({
            "run_id": self.run_id, "search_notes": "e2e",
            "candidates": [{"id": f"c0{i}", "file": spec["source"], "line": 1, "snippet": BUG,
                            "reasoning": "e2e", "confidence": "high"} for i in range(1, 5)],
        }), encoding="utf-8")

        self.expect_verdict("failing test", self.prove("c01", spec["test"], "red", spec["bug_test"]),
                            "confirmed", "failed")
        self.expect_verdict("passing test", self.prove("c02", spec["test"], "red", spec["ok_test"]),
                            "unproven", "passed")
        self.expect_verdict("test missing from the report",
                            self.prove("c03", spec["test"], "red", "noSuchTestXyz"), "unproven", "broken")

        broken_file, broken_content = spec["broken"]
        (repo / broken_file).write_text(broken_content, encoding="utf-8")
        self.expect_verdict("test file that does not compile or import",
                            self.prove("c04", broken_file, "red"), "unproven", "broken")
        (repo / broken_file).unlink()

        source = repo / spec["source"]
        source.write_text(source.read_text(encoding="utf-8").replace(BUG, FIX), encoding="utf-8")
        self.expect_verdict("fix verified", self.prove("c01", spec["test"], "green", spec["bug_test"]),
                            "fixed", "passed", phase="green")
        sh(repo, "git", "add", spec["source"])
        sh(repo, "git", "commit", "-qm", "fix: adults start at 18")

        source.write_text(source.read_text(encoding="utf-8").replace(FIX, BUG), encoding="utf-8")
        (self.rdir / "variants" / "v01.patch").write_text(
            sh(repo, "git", "diff", "--", spec["source"]).stdout, encoding="utf-8", newline="\n")
        sh(repo, "git", "checkout", "--", spec["source"])
        (self.rdir / "variants.json").write_text(json.dumps({"run_id": self.run_id, "variants": [
            {"id": "v01", "kind": "syntax", "description": "reintroduces age > 18",
             "target_file": spec["source"], "patch": "variants/v01.patch"}]}), encoding="utf-8")

        round0 = self.vaccine(0)
        result = (round0.get("results") or [{}])[0]
        self.check("vaccine round 0: tests catch the variant",
                   result.get("status") == "detected" and "tests" in result.get("detected_by", []),
                   json.dumps(round0)[:1500])

        rule = f".antibody/runs/{self.run_id}/rule.v1.yml"
        (repo / rule).write_text(
            "rules:\n  - id: antibody-e2e-adult-age\n"
            f"    languages: [{spec['language']}]\n    severity: ERROR\n"
            "    message: Adults start at 18, use >= 18.\n    pattern: $X > 18\n", encoding="utf-8")
        round1 = self.vaccine(1, rule)
        result = (round1.get("results") or [{}])[0]
        self.check("vaccine round 1: the Semgrep rule catches the variant",
                   result.get("status") == "detected" and "rule" in result.get("detected_by", []),
                   json.dumps(round1)[:1500])

        print(f"{self.profile}: {'OK' if not self.failures else f'{len(self.failures)} check(s) failed'}")
        return 1 if self.failures else 0


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in SPECS:
        print(f"usage: run_e2e.py <profile>  ({', '.join(SPECS)})", file=sys.stderr)
        return 2
    profile = argv[0]
    tmp = Path(tempfile.mkdtemp(prefix=f"antibody-e2e-{profile}-"))
    try:
        repo = tmp / "repo"
        shutil.copytree(FIXTURES / profile, repo)
        print(f"== {profile}")
        return E2E(profile, repo).run()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
