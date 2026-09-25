# Pitch

## Frases clave

- **Tagline:** *Your team already paid for every bug. Antibody makes sure you never pay twice.*
- **Gancho:** *Your immune system doesn't stop you from getting sick. It stops you from getting sick twice from the same thing. Your codebase doesn't have one.*
- **Diferencial en una frase:** *Antibody doesn't just find copies of a bug. It proves each one with a failing test, and then attacks its own defense until it holds.*

## Elevator pitch (30 segundos)

**English:** When your team fixes a bug, it fixes one copy. The same mistake is
usually hiding somewhere else in the code, waiting. Antibody uses IBM Bob to
find those copies, prove each one with a failing test and fix them. Then it
writes a permanent defense and tests it the hard way: a red-team agent that
never sees the defense tries to sneak the bug back in. It's an immune system
for your repository.

**Español:** Cuando tu equipo arregla un bug, arregla una copia. El mismo error
suele estar escondido en otros lugares del código, esperando. Antibody usa IBM
Bob para encontrar esas copias, demostrar cada una con un test que falla y
arreglarlas. Después escribe una defensa permanente y la pone a prueba de
verdad: un agente atacante que nunca ve la defensa intenta volver a meter el
bug. Es un sistema inmune para tu repositorio.

## Guion del video (3 minutos, en inglés con subtítulos)

Grabar primero la pantalla y poner la voz después. Nada de demo en vivo dentro del video.

| Tiempo | En pantalla | Voz |
|---|---|---|
| 0:00 a 0:20 | Negro, texto simple | "Your immune system doesn't stop you from getting sick. It stops you from getting sick twice from the same thing. Your codebase doesn't have one." |
| 0:20 a 0:45 | El diff del fix real en el repo demo | "This team fixed this bug. But the same mistake was still hiding in other files. Nobody looked." (con backtest: "Months later, it came back.") |
| 0:45 a 1:40 | Bob IDE: `/antibody <sha>`, la causa raíz, los subagentes en paralelo, los tests en rojo y luego en verde | "Antibody reads the fix, understands the mistake, not the file, and searches the whole codebase by meaning. Every twin must be proven with a failing test. No proof, no report." |
| 1:40 a 2:15 | Scoreboard con Replay: la placa se llena ronda por ronda | "How do we know the defense works? A red-team agent that never sees the rule attacks it with realistic variants. Some get through. Bob hardens the rule and attacks again, until nothing escapes." |
| 2:15 a 2:35 | Un PR nuevo bloqueado por la regla, con el mensaje de memoria | "Months later, the rule doesn't just say no. It tells the next developer what happened last time." |
| 2:35 a 3:00 | Capturas de las sesiones de Bob y la tabla de resultados medidos | Los números reales. Cierre: "Your team already paid for every bug. Antibody makes sure you never pay twice." |

## ROI: cómo lo demostramos sin inventar cifras

Tres mediciones propias, hechas durante el fin de semana:

1. **Búsqueda manual contra Antibody.** Alguien que no conoce la respuesta
   busca gemelos a mano con cronómetro (`antibody baseline --minutes M --twins N`).
   Se compara con la duración de la corrida y los gemelos probados.
2. **Backtest.** Si existe un bug posterior del mismo patrón en la historia del
   repo demo y Antibody lo encuentra desde el fix anterior, es evidencia directa.
3. **Immunity Score.** De la ronda 0 (defensas que ya existían) a la última ronda.

Para el discurso de negocio, una fórmula que cada equipo completa con sus datos:

> Ahorro mensual ≈ gemelos encontrados × probabilidad de que exploten × costo medio de un bug en producción + horas de búsqueda manual evitadas

Nunca poner porcentajes de la industria sin fuente.

## Cómo se ve contra cada criterio de evaluación

| Criterio | Lo que mostramos |
|---|---|
| Aplicación de la tecnología | Modo custom, skills, subagentes en paralelo, equipo azul y rojo, document understanding del fix y del issue, capturas en `bob_sessions/` |
| Business value | Bugs repetidos cuestan diagnóstico y downtime; números medidos y backtest |
| Originalidad | La vacuna: una defensa atacada por un agente que no la ve, con un puntaje de inmunidad medido |
| Presentación y prototipo | Scoreboard con replay, repo con tests, video con la corrida real |

## Preguntas probables de los jueces

**"Isn't this just Semgrep or CodeQL?"**
Semgrep is the engine our rules run on, but someone has to write those rules.
Antibody writes them from your own bugs, proves the copies that already exist,
fixes them, and verifies the rule by attacking it.

**"What about false positives?"**
It's the core design principle: we only report what the CLI can demonstrate
with a failing test. Anything else is shown separately as suspected.

**"What if the bug can't be unit tested?"**
Then it stays suspected. Today Antibody is strongest on logic and API-misuse
bugs. We'd rather show fewer twins than unproven ones.

**"Couldn't Bob just write a rule that passes its own test?"**
That's why the red team is a separate subagent that never reads the rule, and
the first rule is written before any attack exists. The CLI runs every attack;
Bob can't report a score it didn't earn.

**"Why does this need Bob instead of any LLM?"**
Finding the same mistake written differently needs the whole repository in
context, and proving many candidates at once needs parallel subagents with
their own context. Bob gives us both, plus custom modes and skills so the whole
workflow installs in a repo with one command.

**"Would a real team use this?"**
It triggers on something teams already do every day: fixing bugs. No servers,
no dashboards: everything lives in the repo, is reviewed as code, and humans
approve every fix.
