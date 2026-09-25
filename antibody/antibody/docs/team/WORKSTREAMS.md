# Workstreams: cómo trabajamos en paralelo

El repo está armado para que tres personas avancen a la vez sin pisarse. Lo que
lo permite son dos cosas:

1. **Los contratos** (`antibody/schemas/`): cada archivo que se pasan Bob y la
   CLI tiene un esquema. Nadie depende de que el otro termine para empezar.
2. **El run de ejemplo** (`examples/sample-run/`): un run completo escrito a
   mano. A lo usa como modelo de lo que Bob debe producir, B como entrada de
   prueba para la CLI, y C como datos para el scoreboard y el video.

Regla de oro: **si cambias un contrato, avisas en el canal del equipo** y
actualizas esquema, ejemplo y tests en el mismo PR (ver `docs/CONTRACTS.md`).

---

## Quién es dueño de qué

| Workstream | Nombre | Dueño de | Resumen |
|---|---|---|---|
| **A** | Cerebro | `antibody/bob_template/**` | El modo de Bob, sus reglas, skills y el comando `/antibody` |
| **B** | Manos | `antibody/*.py`, `antibody/schemas/**`, `tests/**` | La CLI, la evidencia, la vacuna, los contratos |
| **C** | Escenario | `ui/**`, `docs/team/**`, `bob_sessions/**`, `DATA_SOURCES.md`, `README.md` | Repo demo, scoreboard, métricas, capturas, video, envío |

`examples/sample-run/` es compartido entre A y B: cualquier cambio ahí se revisa entre los dos.

**Si son 2 personas:** una hace A más B2 y B3; la otra hace B0, B1 y todo C.
**Si son 4 personas:** una cuarta persona (D) toma C0, C1, C4 y `DATA_SOURCES.md`,
y C se concentra en scoreboard, video y envío.

---

## Workstream A: Cerebro (Bob)

| Id | Tarea | Terminado cuando | Depende de |
|---|---|---|---|
| A0 | Instalar Bob IDE 2.0.2 o superior, entrar con la cuenta del hackathon (instancia `ibm-coding-challenge-uat`, región us-east), correr `antibody init` en el repo demo | El modo 🧬 Antibody y el comando `/antibody` aparecen en Bob. Si no aparecen, corregir `custom_modes.yaml` con la documentación de custom modes (nombres de grupos, formato) | B0 (CLI instalada) |
| A1 | Fase 1 sobre el bug demo | `diagnosis.json` pasa `antibody validate` y el equipo aprueba la causa raíz en una frase | C0 (bug elegido) |
| A2 | Fase 2a: búsqueda de gemelos | `candidates.json` válido y los gemelos verificados a mano por C aparecen entre los primeros | A1 |
| A3 | Fase 2b: subagentes en paralelo | Al menos 2 gemelos `confirmed` con evidencia de la CLI, y Bob lanzó un subagente por candidato. Si el modo no permite subagentes, ajustar la configuración | A2, B1 |
| A4 | Fixes y verde | Los gemelos confirmados pasan a `fixed` | A3 |
| A5 | Fase 3: vacuna | Regla v1 del equipo azul, variantes del subagente rojo (sin ver la regla), rondas 0, 1 y siguientes registradas por la CLI | A4, B2 |
| A6 | Fase 4: memoria | `antibody finalize` crea el anticuerpo y Bob imprime el ANTIBODY REPORT con números de `antibody status` | A5 |
| A7 | Robustez del prompt | El pipeline completo corre de punta a punta sin intervención más allá de las aprobaciones previstas | A6 |

Consejos: probar cada skill por separado antes de encadenarlas, y ajustar las
instrucciones en vez de corregir a Bob a mano en el chat (lo que se corrige en
el chat no queda en el producto).

## Workstream B: Manos (CLI)

| Id | Tarea | Terminado cuando | Depende de |
|---|---|---|---|
| B0 | Instalar con `pip install -e ".[tools]"`, correr `python -m unittest discover -s tests` | Tests en verde en la máquina de cada integrante | nada |
| B1 | Prueba real con pytest: en el repo demo, escribir a mano un test del gemelo y correr `antibody prove ... --phase red` y `--phase green` | Evidencia real registrada. Si el proyecto usa otro entorno, `test_command` y `--python` configurados en `.antibody/config.json` | B0, C0 |
| B2 | Prueba real con Semgrep: regla escrita a mano, una variante escrita a mano, `antibody vaccine --round 1` | La detección por regla funciona sobre el repo demo y el tiempo por ronda está medido | B1 |
| B3 | Mensajes de error pensados para Bob | Cada error que A encuentre en sus sesiones dice qué falló y qué hacer, y tiene test | A3 en adelante |
| B4 | (Extra) Guardia de CI: probar `examples/ci/antibody-guard.yml` en un fork | Un PR con el patrón queda bloqueado por la regla, con el mensaje de memoria visible | A6 |
| B5 | (Extra) Paralelizar las variantes de la vacuna | Una ronda tarda menos, con los mismos resultados | B2 |

## Workstream C: Escenario (demo, métricas, pitch)

| Id | Tarea | Terminado cuando | Depende de |
|---|---|---|---|
| C0 | Elegir repo y bug de la demo (ver `DEMO.md`) | Repo con licencia que permite uso comercial, commit de fix elegido, **al menos 2 gemelos reales verificados a mano**, fuente anotada en `DATA_SOURCES.md` | nada: idealmente antes del kickoff |
| C1 | Línea base manual | Alguien que no conoce la respuesta busca gemelos a mano con cronómetro. Resultado registrado con `antibody baseline` | C0 |
| C2 | Evidencia de Bob | Después de cada tarea de Bob de cualquier integrante, captura del resumen de sesión en `bob_sessions/` con el nombre correcto (ver `BOB_USAGE.md`) | continuo |
| C3 | Scoreboard para grabar | Se ve bien a 1920x1080, carga el `scoreboard.json` real con `?src=`, y el replay dura lo que pide el guion | nada: arranca con el ejemplo |
| C4 | Backtest | Un bug posterior del mismo patrón en la historia del repo demo, o la decisión documentada de que no existe | C0 |
| C5 | Video | Guion de `PITCH.md` grabado, editado, con subtítulos en inglés | A6, C3 |
| C6 | README y envío | Tabla de resultados completada con números medidos, envío en lablab con margen | todo |

---

## Git

- Ramas por workstream: `a/<tema>`, `b/<tema>`, `c/<tema>`.
- PR chicos contra `main`. `main` siempre en verde: `python -m unittest discover -s tests`.
- Nada de force push sobre `main`.
- Los resultados de runs reales del repo demo **no** se suben a este repo, salvo
  el `scoreboard.json` final que se usa en el video (en `examples/demo-run/`).

## Puntos de sincronización

| Momento | Qué se muestra | Quién decide |
|---|---|---|
| H+3 | Modo visible en Bob, CLI instalada en todas las máquinas, bug demo elegido | Todos |
| H+10 | Diagnóstico y candidatos del bug demo | A presenta |
| H+22 | **MVP**: gemelos probados en rojo y en verde | Todos: se aplica la regla de corte |
| H+32 | Vacuna con al menos dos rondas | Todos: se aplica la regla de corte |
| H+40 | **Congelamiento**: no entra nada nuevo | C manda desde acá |
| H+45 | Envío hecho | C |

Los horarios y las reglas de corte están en `PLAN_48H.md`.
