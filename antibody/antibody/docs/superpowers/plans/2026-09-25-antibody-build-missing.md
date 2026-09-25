# Antibody — Build Missing Pieces Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the test suite that's missing, verify the CLI works end-to-end, and leave the project ready for the 48h hackathon demo run.

**Architecture:** Tests live in `tests/` at the repo root (alongside the `antibody/` package). They use `examples/sample-run/` as fixture data — no real git repo or network needed. Each test imports the Python modules directly (not via subprocess) for unit tests, and uses `tempfile` + `git init` for integration tests.

**Tech Stack:** Python 3.10+, `unittest` (stdlib only — no pytest dependency for the test runner itself, but pytest must run them), `tempfile`, `pathlib`, `json`.

**Spec:** `antibody/docs/ARCHITECTURE.md`, `antibody/docs/CONTRACTS.md`

## Global Constraints

- stdlib only in `antibody/` — no new runtime imports
- Python 3.10+ only
- `python -m unittest discover -s tests` must pass (this is the CI command)
- Never write `recorded_by` = anything except `"antibody-cli"` in evidence files
- Test command: `python -m unittest discover -s tests` from the repo root (`antibody/antibody/`)
- Sample-run fixtures live at: `antibody/examples/sample-run/` (relative to the package root)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `tests/__init__.py` | Create | Makes `tests/` a package |
| `tests/test_schema.py` | Create | Unit tests: `schema.validate()`, `read_json()`, `write_json()` |
| `tests/test_runs.py` | Create | Unit tests: `init_repo()`, `new_run()`, `latest_run()`, `log_event()`, `set_baseline()` — uses a real temp git repo |
| `tests/test_prove.py` | Create | Unit tests: `prove()` and `mark()` — uses sample-run fixtures + a temp git repo |
| `tests/test_memory.py` | Create | Unit tests: `finalize()` and `build_scoreboard()` — uses sample-run fixtures |
| `tests/test_cli.py` | Create | Integration tests: every CLI command via `main()` directly |
| `tests/fixtures.py` | Create | Helper: copies sample-run into a temp dir, creates a throwaway git repo |

---

## PARTE 1: ENTENDER CÓMO USAR ANTIBODY

**Antes de escribir tests, leer esto para entender el flujo completo.**

### Cómo funciona Antibody de punta a punta

Antibody es una herramienta que vive en DOS repos al mismo tiempo:

```
antibody/          ← este repo: el código de la herramienta
  antibody/        ← el paquete Python (CLI, lógica)
  tests/           ← ← ← lo que vamos a crear

demo-target/       ← el repo donde corre la demo (un proyecto Python aparte)
  .antibody/       ← carpeta creada por `antibody init`
  .bob/            ← modo de Bob instalado por `antibody init`
```

### Flujo completo (lo que hace `antibody` sobre un repo externo)

```
1. antibody init
   └─ crea demo-target/.antibody/config.json
   └─ copia el modo de Bob en demo-target/.bob/

2. antibody new --commit <sha>
   └─ crea demo-target/.antibody/runs/20260926-HHMMSS/
   └─ crea run.json con la fuente del bug

   [Bob escribe diagnosis.json y candidates.json manualmente en esa carpeta]

3. antibody validate diagnosis.json --schema diagnosis
   └─ verifica que el JSON es válido

4. antibody prove c01 --test tests/antibody/test_twin_c01.py --phase red
   └─ corre pytest sobre el test
   └─ si falla (exit 1): twin confirmado
   └─ graba verdicts/c01.json

5. antibody prove c01 --test tests/antibody/test_twin_c01.py --phase green
   └─ corre pytest después del fix
   └─ si pasa (exit 0): twin fixed
   └─ actualiza verdicts/c01.json

6. antibody vaccine --round 0
   └─ aplica cada patch de variants/ en un git worktree aislado
   └─ corre semgrep + pytest por cada variante
   └─ graba vaccine/round_0.json con el Immunity Score

7. antibody vaccine --round 1 --rule rule.v1.yml
   └─ igual pero con una regla Semgrep

8. antibody finalize --slug nombre-del-bug --rule rule.v1.yml
   └─ crea .antibody/antibodies/001-nombre-del-bug/
   └─ copia la regla, crea manifest.json y history.md

9. antibody scoreboard
   └─ lee todo y genera scoreboard.json para el UI
```

### Cómo correr los tests del repo de Antibody mismo

```bash
cd antibody/antibody          # ← la carpeta con pyproject.toml
pip install -e ".[tools]"
python -m unittest discover -s tests
```

---

## Task 1: Scaffolding de tests + fixtures helper

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/fixtures.py`

**Interfaces:**
- Produces: `make_temp_repo(sample_run: bool = False) -> Path` — retorna un Path a un repo git temporal con `.antibody/` inicializado. Si `sample_run=True` también copia los fixtures de `examples/sample-run/` en `.antibody/runs/20260926-101500/`.
- Produces: `SAMPLE_RUN_ID = "20260926-101500"` — constante usada en todos los tests.

- [ ] **Step 1: Crear `tests/__init__.py` vacío**

```python
# tests/__init__.py
```

- [ ] **Step 2: Crear `tests/fixtures.py`**

```python
"""Shared test helpers: disposable git repos and sample-run fixtures."""
from __future__ import annotations

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
                    shutil.copyfile(src, run_dir / subdir / src.name)
        # Write config.json
        import json
        config = {
            "max_candidates": 6, "max_variants": 6, "max_vaccine_rounds": 3,
            "test_command": ["{python}", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            "test_timeout_s": 300, "semgrep": "semgrep",
        }
        (tmp / ".antibody" / "config.json").write_text(
            json.dumps(config, indent=2), encoding="utf-8"
        )

    return tmp
```

- [ ] **Step 3: Verificar que el helper importa sin errores**

```bash
cd antibody/antibody
python -c "from tests.fixtures import make_temp_repo, SAMPLE_RUN_ID; print('OK')"
```

Esperado: `OK`

- [ ] **Step 4: Commit**

```bash
git add tests/__init__.py tests/fixtures.py
git commit -m "test: add test scaffolding and fixtures helper"
```

---

## Task 2: Tests de schema.py

**Files:**
- Create: `tests/test_schema.py`

**Interfaces:**
- Consumes: `antibody.schema.validate`, `antibody.schema.read_json`, `antibody.schema.write_json`, `antibody.schema.ContractError`

- [ ] **Step 1: Escribir los tests**

```python
"""Tests for antibody.schema — contract validation."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from antibody.schema import ContractError, read_json, validate, write_json


class TestValidate(unittest.TestCase):

    def _minimal_diagnosis(self):
        return {
            "run_id": "20260926-101500",
            "source": {
                "type": "fix_commit",
                "ref": "abc123",
                "fix_commit": "abc123",
                "parent_commit": None,
                "issue": None,
            },
            "root_cause": {
                "title": "naive vs aware datetime",
                "pattern": "datetime.now() compared with aware value",
                "why_it_breaks": "raises TypeError",
                "trigger_conditions": ["aware source", "naive now()"],
                "fix_strategy": "use datetime.now(timezone.utc)",
                "language": "python",
            },
            "original_instance": {"file": "billing/invoices.py", "line": 88, "snippet": "if x < datetime.now():"},
        }

    def test_valid_diagnosis_passes(self):
        validate("diagnosis", self._minimal_diagnosis())  # must not raise

    def test_missing_required_field_raises(self):
        data = self._minimal_diagnosis()
        del data["root_cause"]
        with self.assertRaises(ContractError) as ctx:
            validate("diagnosis", data)
        self.assertIn("root_cause", str(ctx.exception))

    def test_wrong_type_raises(self):
        data = self._minimal_diagnosis()
        data["original_instance"]["line"] = "not-an-int"  # must be integer
        with self.assertRaises(ContractError):
            validate("diagnosis", data)

    def test_unknown_schema_name_raises(self):
        with self.assertRaises(KeyError):
            validate("nonexistent_schema", {})

    def test_valid_verdict_passes(self):
        verdict = {
            "candidate_id": "c01",
            "status": "confirmed",
            "reason": "Test fails on current code.",
            "test": {"file": "tests/test_c01.py", "node_id": None},
            "red": {
                "exit_code": 1, "passed": False, "duration_s": 1.2,
                "output_tail": "1 failed", "recorded_at": "2026-09-26T10:00:00+00:00",
                "recorded_by": "antibody-cli",
            },
            "green": None,
            "fix_summary": None,
        }
        validate("verdict", verdict)  # must not raise

    def test_invalid_status_enum_raises(self):
        verdict = {
            "candidate_id": "c01", "status": "INVENTED_STATUS",
            "reason": None, "test": None, "red": None, "green": None, "fix_summary": None,
        }
        with self.assertRaises(ContractError) as ctx:
            validate("verdict", verdict)
        self.assertIn("INVENTED_STATUS", str(ctx.exception))


class TestReadWriteJson(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._dir = Path(self._tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_write_then_read_roundtrip(self):
        path = self._dir / "out.json"
        data = {"key": "value", "num": 42}
        write_json(path, data)
        result = read_json(path)
        self.assertEqual(result, data)

    def test_read_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            read_json(self._dir / "missing.json")

    def test_read_invalid_json_raises(self):
        path = self._dir / "bad.json"
        path.write_text("{not valid json}", encoding="utf-8")
        with self.assertRaises(ContractError):
            read_json(path)

    def test_write_with_schema_validates(self):
        path = self._dir / "out.json"
        with self.assertRaises(ContractError):
            write_json(path, {"bad": "data"}, schema="diagnosis")

    def test_write_creates_parent_dirs(self):
        path = self._dir / "deep" / "nested" / "out.json"
        write_json(path, {"x": 1})
        self.assertTrue(path.exists())
```

- [ ] **Step 2: Correr los tests**

```bash
cd antibody/antibody
python -m unittest tests.test_schema -v
```

Esperado: todos pasan (8 tests).

- [ ] **Step 3: Commit**

```bash
git add tests/test_schema.py
git commit -m "test: add schema contract validation tests"
```

---

## Task 3: Tests de runs.py

**Files:**
- Create: `tests/test_runs.py`

**Interfaces:**
- Consumes: `antibody.runs.init_repo`, `antibody.runs.new_run`, `antibody.runs.latest_run`, `antibody.runs.log_event`, `antibody.runs.set_baseline`, `antibody.runs.run_dir`, `antibody.runs.load_config`
- Consumes: `tests.fixtures.make_temp_repo`

- [ ] **Step 1: Escribir los tests**

```python
"""Tests for antibody.runs — run lifecycle and git helpers."""
from __future__ import annotations

import shutil
import unittest

from antibody.runs import (
    antibody_root, init_repo, latest_run, load_config, log_event,
    new_run, run_dir, set_baseline,
)
from tests.fixtures import make_temp_repo


class TestInitRepo(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo()

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_creates_antibody_dirs(self):
        init_repo(self._repo)
        self.assertTrue((self._repo / ".antibody" / "runs").is_dir())
        self.assertTrue((self._repo / ".antibody" / "antibodies").is_dir())

    def test_creates_config_json(self):
        init_repo(self._repo)
        config_path = self._repo / ".antibody" / "config.json"
        self.assertTrue(config_path.exists())

    def test_idempotent(self):
        init_repo(self._repo)
        init_repo(self._repo)  # second call must not raise
        config_path = self._repo / ".antibody" / "config.json"
        self.assertTrue(config_path.exists())

    def test_not_a_git_repo_raises(self):
        import tempfile
        tmp = make_temp_repo()
        shutil.rmtree(tmp / ".git")
        with self.assertRaises(RuntimeError):
            init_repo(tmp)
        shutil.rmtree(tmp, ignore_errors=True)


class TestNewRun(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo()
        init_repo(self._repo)

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_creates_run_dirs(self):
        run_id = new_run(self._repo, "postmortem", "docs/incident-2026.md")
        rdir = run_dir(self._repo, run_id)
        self.assertTrue((rdir / "verdicts").is_dir())
        self.assertTrue((rdir / "variants").is_dir())
        self.assertTrue((rdir / "vaccine").is_dir())

    def test_run_json_has_source(self):
        import json
        run_id = new_run(self._repo, "postmortem", "incident.md", issue="#99")
        run_json = json.loads((run_dir(self._repo, run_id) / "run.json").read_text())
        self.assertEqual(run_json["source"]["type"], "postmortem")
        self.assertEqual(run_json["source"]["issue"], "#99")

    def test_run_json_has_events(self):
        import json
        run_id = new_run(self._repo, "postmortem", "x.md")
        run_json = json.loads((run_dir(self._repo, run_id) / "run.json").read_text())
        self.assertGreaterEqual(len(run_json["events"]), 1)
        self.assertEqual(run_json["events"][0]["kind"], "run_started")


class TestLatestRun(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo()
        init_repo(self._repo)

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_no_runs_raises(self):
        with self.assertRaises(FileNotFoundError):
            latest_run(self._repo)

    def test_returns_latest_alphabetically(self):
        import time
        r1 = new_run(self._repo, "postmortem", "a.md")
        time.sleep(1.1)  # ensure different timestamp
        r2 = new_run(self._repo, "postmortem", "b.md")
        self.assertEqual(latest_run(self._repo), r2)


class TestLogEventAndBaseline(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo()
        init_repo(self._repo)
        self._run_id = new_run(self._repo, "postmortem", "x.md")

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_log_event_appends(self):
        import json
        log_event(self._repo, self._run_id, "test_event", "something happened")
        run_json = json.loads((run_dir(self._repo, self._run_id) / "run.json").read_text())
        kinds = [e["kind"] for e in run_json["events"]]
        self.assertIn("test_event", kinds)

    def test_set_baseline_records(self):
        import json
        set_baseline(self._repo, self._run_id, 45.5, 3)
        run_json = json.loads((run_dir(self._repo, self._run_id) / "run.json").read_text())
        self.assertEqual(run_json["baseline"]["manual_minutes"], 45.5)
        self.assertEqual(run_json["baseline"]["manual_twins"], 3)
```

- [ ] **Step 2: Correr los tests**

```bash
cd antibody/antibody
python -m unittest tests.test_runs -v
```

Esperado: todos pasan (9 tests).

- [ ] **Step 3: Commit**

```bash
git add tests/test_runs.py
git commit -m "test: add runs lifecycle tests"
```

---

## Task 4: Tests de prove.py

**Files:**
- Create: `tests/test_prove.py`

**Interfaces:**
- Consumes: `antibody.prove.prove`, `antibody.prove.mark`
- Consumes: `tests.fixtures.make_temp_repo`, `tests.fixtures.SAMPLE_RUN_ID`

**Nota:** `prove()` corre pytest real. Para no depender de un repo externo, los tests usan la opción `--test` apuntando a un archivo de test temporal que siempre falla (fase red) o siempre pasa (fase green), creado en el propio repo temporal.

- [ ] **Step 1: Escribir los tests**

```python
"""Tests for antibody.prove — red/green evidence runner."""
from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from antibody.prove import mark, prove
from antibody.runs import init_repo, new_run, run_dir
from antibody.schema import read_json
from tests.fixtures import make_temp_repo


def _write_candidates(repo: Path, run_id: str, ids: list[str]) -> None:
    """Write a minimal candidates.json with the given ids."""
    from antibody.schema import write_json
    data = {
        "run_id": run_id,
        "search_notes": "test",
        "candidates": [
            {"id": cid, "file": "src/app.py", "line": 1,
             "snippet": "x = 1", "reasoning": "test", "confidence": "high"}
            for cid in ids
        ],
    }
    write_json(run_dir(repo, run_id) / "candidates.json", data, "candidates")


def _write_failing_test(repo: Path, rel_path: str) -> str:
    """Write a test that always fails (exit code 1). Returns repo-relative path."""
    test_path = repo / rel_path
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text("def test_always_fails():\n    assert False, 'injected failure'\n",
                         encoding="utf-8")
    return rel_path


def _write_passing_test(repo: Path, rel_path: str) -> str:
    """Write a test that always passes (exit code 0). Returns repo-relative path."""
    test_path = repo / rel_path
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text("def test_always_passes():\n    assert True\n", encoding="utf-8")
    return rel_path


class TestProveRed(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo()
        init_repo(self._repo)
        self._run_id = new_run(self._repo, "postmortem", "x.md")
        _write_candidates(self._repo, self._run_id, ["c01", "c02"])

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_red_failing_test_confirms_twin(self):
        test_file = _write_failing_test(self._repo, "tests/test_twin_c01.py")
        verdict = prove(self._repo, self._run_id, "c01", test_file, "red")
        self.assertEqual(verdict["status"], "confirmed")
        self.assertIsNotNone(verdict["red"])
        self.assertEqual(verdict["red"]["exit_code"], 1)
        self.assertEqual(verdict["red"]["recorded_by"], "antibody-cli")

    def test_red_passing_test_leaves_unproven(self):
        test_file = _write_passing_test(self._repo, "tests/test_twin_c02.py")
        verdict = prove(self._repo, self._run_id, "c02", test_file, "red")
        self.assertEqual(verdict["status"], "unproven")

    def test_red_unknown_candidate_raises(self):
        with self.assertRaises(ValueError):
            prove(self._repo, self._run_id, "c99", "tests/x.py", "red")

    def test_red_missing_test_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            prove(self._repo, self._run_id, "c01", "tests/does_not_exist.py", "red")

    def test_verdict_file_is_written(self):
        test_file = _write_failing_test(self._repo, "tests/test_twin_c01.py")
        prove(self._repo, self._run_id, "c01", test_file, "red")
        verdict_path = run_dir(self._repo, self._run_id) / "verdicts" / "c01.json"
        self.assertTrue(verdict_path.exists())
        data = read_json(verdict_path, "verdict")
        self.assertEqual(data["status"], "confirmed")


class TestProveGreen(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo()
        init_repo(self._repo)
        self._run_id = new_run(self._repo, "postmortem", "x.md")
        _write_candidates(self._repo, self._run_id, ["c01"])
        # First confirm the twin in red
        test_file = _write_failing_test(self._repo, "tests/test_twin_c01.py")
        prove(self._repo, self._run_id, "c01", test_file, "red")

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_green_requires_prior_red_confirmation(self):
        _write_candidates(self._repo, self._run_id, ["c01", "c02"])
        _write_passing_test(self._repo, "tests/test_c02.py")
        # c02 was never confirmed
        with self.assertRaises(ValueError):
            prove(self._repo, self._run_id, "c02", "tests/test_c02.py", "green")

    def test_green_passing_test_marks_fixed(self):
        test_file = _write_passing_test(self._repo, "tests/test_twin_c01_fixed.py")
        verdict = prove(self._repo, self._run_id, "c01", test_file, "green",
                        fix_summary="Use datetime.now(timezone.utc)")
        self.assertEqual(verdict["status"], "fixed")
        self.assertEqual(verdict["fix_summary"], "Use datetime.now(timezone.utc)")


class TestMark(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo()
        init_repo(self._repo)
        self._run_id = new_run(self._repo, "postmortem", "x.md")
        _write_candidates(self._repo, self._run_id, ["c01"])

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_mark_suspected(self):
        verdict = mark(self._repo, self._run_id, "c01", "suspected", "Celery task, hard to test")
        self.assertEqual(verdict["status"], "suspected")

    def test_mark_rejected(self):
        verdict = mark(self._repo, self._run_id, "c01", "rejected", "Not a twin, different pattern")
        self.assertEqual(verdict["status"], "rejected")

    def test_mark_invalid_status_raises(self):
        with self.assertRaises(ValueError):
            mark(self._repo, self._run_id, "c01", "INVALID", "reason")
```

- [ ] **Step 2: Correr los tests**

```bash
cd antibody/antibody
python -m unittest tests.test_prove -v
```

Esperado: todos pasan (8 tests). Si pytest no está instalado: `pip install pytest`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_prove.py
git commit -m "test: add prove red/green evidence tests"
```

---

## Task 5: Tests de memory.py

**Files:**
- Create: `tests/test_memory.py`

**Interfaces:**
- Consumes: `antibody.memory.finalize`, `antibody.memory.build_scoreboard`
- Consumes: `tests.fixtures.make_temp_repo`, `tests.fixtures.SAMPLE_RUN_ID`

- [ ] **Step 1: Escribir los tests**

```python
"""Tests for antibody.memory — finalize and scoreboard."""
from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from antibody.memory import build_scoreboard, finalize
from antibody.runs import run_dir
from antibody.schema import read_json
from tests.fixtures import SAMPLE_RUN_ID, make_temp_repo


class TestFinalize(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo(sample_run=True)
        # Write a minimal rule file (finalize needs an existing file)
        self._rule_path = self._repo / "rule.v2.yml"
        # Copy from the sample-run fixtures
        src = Path(__file__).parent.parent / "examples" / "sample-run" / "rule.v2.yml"
        shutil.copyfile(src, self._rule_path)

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_creates_antibody_folder(self):
        folder = finalize(self._repo, SAMPLE_RUN_ID, "naive-vs-aware-datetime",
                          str(self._rule_path.relative_to(self._repo)))
        self.assertTrue(folder.is_dir())
        self.assertTrue((folder / "manifest.json").exists())
        self.assertTrue((folder / "rule.yml").exists())
        self.assertTrue((folder / "history.md").exists())

    def test_manifest_passes_schema(self):
        folder = finalize(self._repo, SAMPLE_RUN_ID, "naive-vs-aware-datetime",
                          str(self._rule_path.relative_to(self._repo)))
        read_json(folder / "manifest.json", "manifest")  # must not raise

    def test_missing_rule_raises(self):
        with self.assertRaises(FileNotFoundError):
            finalize(self._repo, SAMPLE_RUN_ID, "slug", "nonexistent/rule.yml")

    def test_slug_appears_in_folder_name(self):
        folder = finalize(self._repo, SAMPLE_RUN_ID, "my-test-slug",
                          str(self._rule_path.relative_to(self._repo)))
        self.assertIn("my-test-slug", folder.name)


class TestBuildScoreboard(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo(sample_run=True)

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_scoreboard_json_is_written(self):
        build_scoreboard(self._repo, SAMPLE_RUN_ID, "owner/project")
        out = run_dir(self._repo, SAMPLE_RUN_ID) / "scoreboard.json"
        self.assertTrue(out.exists())

    def test_scoreboard_passes_schema(self):
        data = build_scoreboard(self._repo, SAMPLE_RUN_ID, "owner/project")
        # validate() is called inside build_scoreboard; reaching here = passed
        self.assertIn("twins", data)
        self.assertIn("rounds", data)

    def test_scoreboard_has_repo_label(self):
        data = build_scoreboard(self._repo, SAMPLE_RUN_ID, "my-org/my-repo")
        self.assertEqual(data["repo"], "my-org/my-repo")
```

- [ ] **Step 2: Correr los tests**

```bash
cd antibody/antibody
python -m unittest tests.test_memory -v
```

Esperado: todos pasan (7 tests).

- [ ] **Step 3: Commit**

```bash
git add tests/test_memory.py
git commit -m "test: add memory finalize and scoreboard tests"
```

---

## Task 6: Tests de integración CLI

**Files:**
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: `antibody.cli.main`
- Consumes: `tests.fixtures.make_temp_repo`, `tests.fixtures.SAMPLE_RUN_ID`

- [ ] **Step 1: Escribir los tests**

```python
"""Integration tests: every CLI command via main()."""
from __future__ import annotations

import json
import shutil
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from antibody.cli import main
from tests.fixtures import SAMPLE_RUN_ID, make_temp_repo


class TestCliInit(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo()

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_init_no_bob(self):
        ret = main(["--repo", str(self._repo), "init", "--no-bob"])
        self.assertEqual(ret, 0)
        self.assertTrue((self._repo / ".antibody" / "config.json").exists())

    def test_init_returns_0(self):
        ret = main(["--repo", str(self._repo), "init", "--no-bob"])
        self.assertEqual(ret, 0)


class TestCliNew(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo()
        main(["--repo", str(self._repo), "init", "--no-bob"])

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_new_postmortem_creates_run(self):
        # Write a dummy document so the path exists
        doc = self._repo / "incident.md"
        doc.write_text("# Incident\n", encoding="utf-8")
        out = StringIO()
        with patch("sys.stdout", out):
            ret = main(["--repo", str(self._repo), "new", "--document", str(doc)])
        self.assertEqual(ret, 0)
        output = out.getvalue()
        self.assertIn("run_id=", output)

    def test_new_without_required_arg_exits_nonzero(self):
        with self.assertRaises(SystemExit) as ctx:
            main(["--repo", str(self._repo), "new"])
        self.assertNotEqual(ctx.exception.code, 0)


class TestCliValidate(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo(sample_run=True)
        # Write sample diagnosis.json at a known path for testing
        self._diagnosis_path = (
            self._repo / ".antibody" / "runs" / SAMPLE_RUN_ID / "diagnosis.json"
        )

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_validate_valid_file_returns_0(self):
        ret = main(["validate", str(self._diagnosis_path), "--schema", "diagnosis"])
        self.assertEqual(ret, 0)

    def test_validate_invalid_file_returns_2(self):
        import tempfile
        tmp = Path(tempfile.mktemp(suffix=".json"))
        tmp.write_text('{"bad": "data"}', encoding="utf-8")
        ret = main(["validate", str(tmp), "--schema", "diagnosis"])
        self.assertEqual(ret, 2)
        tmp.unlink(missing_ok=True)


class TestCliStatus(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo(sample_run=True)

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_status_prints_run_id(self):
        out = StringIO()
        with patch("sys.stdout", out):
            ret = main(["--repo", str(self._repo), "status", "--run", SAMPLE_RUN_ID])
        self.assertEqual(ret, 0)
        self.assertIn(SAMPLE_RUN_ID, out.getvalue())


class TestCliMark(unittest.TestCase):

    def setUp(self):
        self._repo = make_temp_repo(sample_run=True)

    def tearDown(self):
        shutil.rmtree(self._repo, ignore_errors=True)

    def test_mark_suspected_returns_0(self):
        ret = main([
            "--repo", str(self._repo), "mark", "--run", SAMPLE_RUN_ID,
            "c05", "--suspected", "--reason", "Hard to test in isolation"
        ])
        self.assertEqual(ret, 0)

    def test_mark_rejected_returns_0(self):
        ret = main([
            "--repo", str(self._repo), "mark", "--run", SAMPLE_RUN_ID,
            "c05", "--rejected", "--reason", "Not a real twin"
        ])
        self.assertEqual(ret, 0)
```

- [ ] **Step 2: Correr los tests**

```bash
cd antibody/antibody
python -m unittest tests.test_cli -v
```

Esperado: todos pasan (8 tests).

- [ ] **Step 3: Correr el suite completo**

```bash
cd antibody/antibody
python -m unittest discover -s tests -v
```

Esperado: todos los tests pasan (40+ tests).

- [ ] **Step 4: Commit final**

```bash
git add tests/test_cli.py
git commit -m "test: add CLI integration tests — full test suite green"
```

---

## PARTE 2: CÓMO ELEGIR EL REPO DEMO Y EJECUTAR ANTIBODY

> Esta parte no es código — es el procedimiento que el equipo ejecuta durante las 48 horas del hackathon. No hay nada que implementar aquí; es una guía de uso.

### Paso C0: Elegir el repo demo (HACER ANTES DEL KICKOFF)

**Criterios del repo:**
- Python, tests con pytest, corren en < 1 minuto
- Licencia MIT, BSD o Apache 2.0
- Bug de tipo "datetime naive vs aware" (el más claro para la demo)

**Bug recomendado para buscar en GitHub:**

```bash
# En GitHub search: commits
# fix naive datetime OR timezone aware comparison OR utcnow deprecated
# En un repo elegido:
git log --oneline --grep="datetime" -i | head -20
git log -S "datetime.now(" --oneline | head -10
```

**Verificación obligatoria (requiere ≥2 gemelos):**

```bash
git clone <repo> demo-target
cd demo-target
git checkout <commit-ANTERIOR-al-fix>     # el bug debe existir aquí
# Buscar a mano otras apariciones del mismo error
# Para cada gemelo sospechado, escribir un test rápido:
python -c "import <modulo>; <llamada que deberia fallar>"
```

**Si el test falla con `TypeError: can't compare offset-naive and offset-aware` → gemelo confirmado.**

### Paso A0: Instalar y configurar

```bash
# En la máquina de cada integrante:
cd antibody/antibody
pip install -e ".[tools]"
python -m unittest discover -s tests        # debe quedar verde

# En el repo demo:
cd /ruta/al/demo-target
pip install -e ".[test]"                    # instalar el proyecto demo
pip install -e /ruta/a/antibody/antibody[tools]
antibody init                               # crea .antibody/ y .bob/
```

Luego: abrir demo-target en Bob IDE, verificar que el modo **🧬 Antibody** aparece.

### Paso A1–A2: Correr las fases 1 y 2 en Bob

```
# En Bob IDE (modo Antibody):
/antibody <sha-del-fix>
```

Bob escribe `diagnosis.json` y `candidates.json`. Para verificar:

```bash
antibody validate .antibody/runs/<run_id>/diagnosis.json --schema diagnosis
antibody validate .antibody/runs/<run_id>/candidates.json --schema candidates
antibody status
```

### Paso B1: Probar los gemelos (fase red/green)

Por cada gemelo que Bob encuentre, Bob escribe un test en `tests/antibody/test_twin_cNN.py`. Luego el CLI lo corre:

```bash
# Fase red (verificar que el bug existe):
antibody prove c01 --test tests/antibody/test_twin_c01.py --phase red

# Ver el resultado:
antibody status
# Debe mostrar: confirmed=1 o similar
```

Después de aplicar el fix al código:

```bash
# Fase green (verificar que el fix funciona):
antibody prove c01 --test tests/antibody/test_twin_c01.py --phase green \
  --fix-summary "Use datetime.now(timezone.utc)"
```

### Paso A5/B2: Vacuna

```bash
# Ronda 0: medir lo que ya tenía el repo
antibody vaccine --round 0

# Ronda 1: con la regla que Bob escribió
antibody vaccine --round 1 --rule .antibody/runs/<run_id>/rule.v1.yml

# Ver el Immunity Score:
antibody status
# Debe mostrar algo como: vaccine round 1  immunity 80% (4/5)
```

### Paso A6: Finalizar el anticuerpo

```bash
antibody finalize \
  --slug naive-vs-aware-datetime \
  --rule .antibody/runs/<run_id>/rule.v2.yml \
  --summary "Never compare aware and naive datetimes; use datetime.now(timezone.utc)" \
  --link "#412"
```

### Paso C3: Scoreboard

```bash
antibody scoreboard --repo-label owner/project
# Copia el archivo generado al repo de Antibody para el video:
cp .antibody/runs/<run_id>/scoreboard.json /ruta/a/antibody/antibody/examples/demo-run/

# Para verlo en el browser:
cd /ruta/a/antibody/antibody
python -m http.server 8000
# Abrir: http://localhost:8000/ui/scoreboard.html
# Cargar el archivo: examples/demo-run/scoreboard.json
```

---

## Self-Review

**Spec coverage:**
- ✅ Tests para `schema.py` — Task 2
- ✅ Tests para `runs.py` — Task 3
- ✅ Tests para `prove.py` — Task 4
- ✅ Tests para `memory.py` — Task 5
- ✅ Tests para CLI (`cli.py`) — Task 6
- ✅ Guía de uso completa — Parte 2
- ⚠️ `vaccine.py` no tiene tests unitarios — requiere un git repo real con patches aplicables. Se cubre mediante el sample-run en los tests de memory/scoreboard. Test unitario completo de vaccine requeriría un repo con archivos Python reales y patches válidos, lo cual está fuera del scope de las 48h del hackathon. **Mitigación:** el sample-run ya tiene `vaccine/round_0.json` hasta `round_2.json` como fixtures.

**Placeholder scan:** ninguno encontrado.

**Type consistency:** todas las llamadas a `prove()`, `mark()`, `finalize()`, `build_scoreboard()` usan las firmas exactas de los módulos fuente.
