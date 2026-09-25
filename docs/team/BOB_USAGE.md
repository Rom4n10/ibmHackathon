# Uso de Bob: Bobcoins y evidencia

Resumen de lo que dice la guía oficial del hackathon y cómo lo aplicamos.

## Lo que exige la guía

- **Bob IDE es obligatorio** y tiene que ser un componente central del proyecto.
  Bob Shell es opcional.
- Hay que usar la **cuenta provista por el hackathon**, no una personal. En Bob
  IDE: Settings > General > seleccionar la instancia `ibm-coding-challenge-uat`
  (región us-east).
- Versión: las versiones 1.0.3 y 2.0.0 del IDE dejan de funcionar el 30 de
  septiembre. Instalar 2.0.2 o superior desde el principio.
- **Cada integrante** debe subir capturas de los resúmenes de sesión de sus
  tareas de Bob a la carpeta `bob_sessions/` del repo final.

## Bobcoins: el recurso más escaso

Cada integrante recibe **40 Bobcoins**. Cuando se gastan, **no hay más**. La
guía recomienda planificar en equipo para aprovechar el total de todos.

No sabemos de antemano cuánto cuesta cada tarea. Por eso:

1. **Medir temprano.** Después de las primeras dos o tres tareas, cada uno
   revisa su consumo (Settings > General en Bob IDE, o el dashboard de
   administración) y lo anota en el canal del equipo.
2. **Presupuesto orientativo por persona**, a ajustar con esa medición:

| Uso | Parte del presupuesto |
|---|---|
| Construir el producto con Bob (skills, reglas, código) | cerca de la mitad |
| Corridas del pipeline de Antibody sobre el repo demo | cerca de un tercio |
| Reserva para la corrida de grabación y emergencias | el resto, que no se toca antes de H+32 |

3. **Regla de corte**: si el equipo llega al 70% de sus Bobcoins antes de H+32,
   se deja de construir con Bob y se protege la reserva.

## Cómo gastamos menos sin perder evidencia

- **La CLI hace el trabajo pesado.** Correr tests, Semgrep y rondas de vacuna no
  consume Bobcoins porque lo hace la CLI, no Bob. Esa es una decisión de diseño
  del producto, no solo de ahorro.
- **Presupuestos en `.antibody/config.json`**: `max_candidates`, `max_variants`
  y `max_vaccine_rounds` limitan cuántos subagentes se lanzan. Para los ensayos,
  bajarlos (por ejemplo 3 candidatos y 3 variantes). Para la grabación, subirlos.
- **Ensayar por partes.** Las partes deterministas se ensayan llamando a la CLI
  a mano. El pipeline completo con Bob se corre pocas veces: un ensayo
  integrado cerca de H+22 y una o dos corridas de grabación.
- **El video usa la corrida grabada.** El scoreboard reproduce la corrida desde
  su `scoreboard.json` con el botón Replay, sin volver a llamar a Bob.
- **Un objetivo por tarea.** Tareas cortas y enfocadas gastan menos contexto y
  además dan capturas más claras. Abrir una tarea nueva cuando cambia el tema.
- **Plan mode para diseñar, Agent mode para implementar**, como recomienda la
  documentación de Bob.
- **Repo demo chico.** Menos archivos que leer, menos contexto que pagar.

## Capturas de sesión (obligatorio, cada integrante)

Hacerlo **después de cada tarea**, no el domingo a la noche:

1. En el chat de Bob IDE, seleccionar **Tasks** para ver la lista de tareas.
2. Abrir la tarea (si hay varios workspaces, seleccionar **All**).
3. Seleccionar el encabezado de la tarea: aparece el resumen de consumo de la sesión.
4. Captura en **PNG**.
5. Nombre: `<equipo>_task<NN>_<descripcion-corta>.png`, por ejemplo
   `antibody_task07_vaccine_round2_summary.png`.
6. Subirla a `bob_sessions/` y agregar una línea en la tabla de
   `bob_sessions/README.md`.

Las tareas más valiosas como evidencia son las que muestran planificación,
subagentes en paralelo y el ciclo completo del pipeline. Nombren esas tareas
de forma clara desde el principio.

## watsonx (opcional, no planificado)

La guía permite usar watsonx Orchestrate y watsonx.ai de forma opcional. No
forman parte del plan: agregarían alcance sin sumar al criterio central, que
es el uso de Bob. Solo se consideran si se agotan los Bobcoins y hace falta
seguir trabajando.
