# Plan de 48 horas

El hackathon dura 48 horas, del 25 al 27 de septiembre de 2026. Los tiempos van
en horas relativas al kickoff (**H0**), porque cada integrante puede estar en
una zona horaria distinta. Ajusten H0 a la hora real del kickoff.

## Antes del kickoff (lo más importante de todo el plan)

- [ ] **Repo y bug de la demo elegidos** y gemelos verificados a mano (C0, ver `DEMO.md`). Sin gemelos reales no hay demo.
- [ ] Todos se registraron en lablab y tienen IBMid con el mail del registro.
- [ ] Todos clonaron este repo y corrieron `python -m unittest discover -s tests`.
- [ ] Todos leyeron `WORKSTREAMS.md` y saben qué tareas son suyas.

## Bloques

| Bloque | A: Cerebro | B: Manos | C: Escenario | Checkpoint |
|---|---|---|---|---|
| **H0 a H3** | Aceptar invitación de Bob, instalar Bob IDE 2.0.2+, A0 | B0 en todas las máquinas, ayudar con instalación | Confirmar bug demo, abrir `DATA_SOURCES.md`, revisar el formulario de envío de lablab | **H+3:** modo visible en Bob, CLI en todas las máquinas |
| **H3 a H10** | A1 y A2 sobre el bug demo | B1: prove real con pytest en el repo demo | C1: línea base manual. C2: primeras capturas | **H+10:** diagnóstico y candidatos |
| **H10 a H22** | A3 y A4: subagentes, rojo y verde | B2: vacuna real con Semgrep. B3 según lo que encuentre A | C3: scoreboard con datos reales. C4: buscar backtest | **H+22: MVP completo** |
| **H22 a H32** | A5: equipo azul y equipo rojo, rondas | B3, B5 si sobra tiempo | C3 y guion del video listo | **H+32:** vacuna con 2+ rondas |
| **H32 a H40** | A6 y A7: memoria, reporte, robustez. **Corrida de grabación** | B4 si todo lo anterior está estable | Grabación de pantalla de la corrida | **H+40: congelamiento** |
| **H40 a H45** | Apoyo al video, limpiar el modo | README técnico, limpieza del repo | C5 y C6: edición, subtítulos, README de resultados, envío | **H+45: enviado** |
| **H45 a H48** | Margen para imprevistos | Margen | Margen | Nada se envía en la última hora |

Duerman. Un equipo descansado a H+30 rinde más que uno que no durmió.

## Reglas de corte (se aplican sin discusión)

- **H+22 sin MVP** (gemelos en rojo y verde): la vacuna se reduce a una ronda 0 y una ronda 1, sin iteración. Todo el esfuerzo va al núcleo.
- **H+32 sin vacuna funcionando**: se presenta el MVP y la vacuna aparece en el video como siguiente paso, con un solo ejemplo mostrado desde la CLI.
- **H+40**: congelamiento. No entra ninguna funcionalidad nueva. Solo se arreglan errores que rompen la demo.
- **Bobcoins en 70% del total del equipo antes de H+32**: se deja de construir con Bob y se reserva el resto para la corrida de grabación (ver `BOB_USAGE.md`).

## Prioridades si falta tiempo

1. Fase 2 (gemelos probados) sobre el bug real. Con esto ya hay proyecto.
2. Fase 3 (vacuna) con al menos una ronda que muestre algo escapando.
3. Scoreboard con datos reales para el video.
4. Fase 4 (memoria): es barata, conviene hacerla aunque sea mínima.
5. Backtest, guardia de CI, entrada por postmortem: solo si todo lo anterior está listo.

## Checklist de entrega

- [ ] Repositorio público con este README completo y la tabla de resultados con números medidos.
- [ ] Carpeta `bob_sessions/` con las capturas de **cada integrante**, en PNG, con nombres `equipo_taskNN_descripcion.png`.
- [ ] `DATA_SOURCES.md` con todos los repos y sitios usados.
- [ ] Video de 3 minutos en inglés con subtítulos.
- [ ] `examples/demo-run/scoreboard.json` de la corrida real que aparece en el video.
- [ ] Ningún nombre ni mail de autores de commits visible en el video ni en los archivos.
- [ ] Formulario de lablab completo, revisado por dos personas.
