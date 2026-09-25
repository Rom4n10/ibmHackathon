# La demo: repo, bug, grabación

La demo es el proyecto. Si no hay gemelos reales en el repo elegido, no hay
nada que mostrar. Esta guía es para hacer esa elección bien y antes del kickoff.

## 1. Reglas de datos del hackathon (aplican a la demo)

La guía oficial pide traer nuestros propios datos y cumplir esto:

- Datos de sitios públicos solo si sus términos permiten **uso comercial**, y
  hay que **llevar una lista** de los sitios usados: eso es `DATA_SOURCES.md`.
- Nada confidencial, nada de clientes, nada sin permiso del dueño.
- **Nada con información personal**: la historia de git tiene nombres y mails
  de autores. Antibody no los guarda, pero cuidado con lo que se ve en pantalla
  (`git log`, `git blame`, paneles del IDE) durante la grabación.
- Nada obtenido de redes sociales.

Consecuencia práctica: elegir repos open source con licencia **MIT, BSD o
Apache 2.0**. Si se quiere usar un postmortem como entrada, escribir uno propio
sobre el bug de la demo en lugar de copiar uno publicado por una empresa.

## 2. Criterios para el repo

- Python, tests con pytest que corran en menos de un minuto.
- Tamaño mediano: suficiente para que buscar a mano sea tedioso, no tanto como
  para que Bob gaste contexto de más.
- Historia con commits de fix bien descritos y, si es posible, issues enlazados.
- Instalación simple en un entorno virtual, sin servicios externos.

## 3. Patrones de bug que se demuestran bien con un test

| Patrón | Por qué funciona en la demo |
|---|---|
| Datetime con y sin zona horaria mezclados | Falla con `TypeError`, un test de dos líneas lo demuestra |
| Argumento por defecto mutable (`def f(x=[])`) | El estado se filtra entre llamadas, se ve en dos llamadas seguidas |
| Modificar una colección mientras se itera | Error o resultado incorrecto, fácil de reproducir |
| Comparar floats con `==` | Falla con valores concretos y conocidos |
| Request HTTP sin timeout | Muy fácil de explicar, pero el test necesita un servidor falso lento: más trabajo |

## 4. Cómo encontrar el bug

Buscar en GitHub commits de fix con el patrón. Ideas de búsqueda:

- En commits: `fix naive datetime`, `timezone aware comparison`, `utcnow deprecated`,
  `mutable default argument`, `can't compare offset-naive`.
- En el repo elegido: `git log --oneline --grep="fix" -i` y
  `git log -S "datetime.now(" --oneline` para ver dónde entró y salió el patrón.

## 5. Verificación manual (obligatoria)

1. Clonar el repo y hacer checkout del **commit anterior al fix** (`<fix>^`).
   Ahí el bug original todavía existe.
2. Buscar a mano otras apariciones del mismo error. No confiar en grep: leer.
3. Para al menos **dos** de ellas, escribir un test rápido y comprobar que falla
   por la razón correcta.
4. Si hay al menos dos gemelos reales: repo elegido. Anotar en `DATA_SOURCES.md`.
5. Si no los hay: cambiar de commit o de repo, no de idea.

**Plan B honesto**: si después de buscar no aparece ningún caso natural, usar
un fork con gemelos sembrados a mano, y **decirlo en el video y en el README**.
La transparencia suma; un engaño descubierto hunde el proyecto.

## 6. Preparar el repo para la corrida

```bash
git clone <repo> demo-target && cd demo-target
git checkout -b antibody-demo <fix-sha>     # partir del commit del fix
python -m venv .venv && . .venv/bin/activate
pip install -e ".[test]"                     # o lo que use el proyecto
pip install -e /ruta/a/antibody[tools]
antibody init
```

Si el proyecto necesita otro comando para sus tests, ajustar `test_command` en
`.antibody/config.json` (por ejemplo `["uv", "run", "pytest", "-q"]`).

## 7. Backtest (la mejor prueba de ROI)

Buscar en la historia del repo un bug **posterior** del mismo patrón, arreglado
en otro archivo. Si Antibody, corriendo sobre el fix anterior, encuentra ese
lugar como gemelo, la frase del pitch es: "si el equipo hubiera tenido Antibody
en su momento, este bug posterior no habría existido".

Cómo buscarlo: `git log -S "<fragmento del patrón>" --oneline` después de la
fecha del fix, o buscar en los issues cerrados el mismo mensaje de error.

## 8. Grabación

1. Bajar los presupuestos para el último ensayo, subirlos para la grabación.
2. Correr `/antibody <fix-sha>` en Bob IDE con grabación de pantalla activa.
3. Al terminar: `antibody scoreboard --repo-label <owner/project>` y copiar el
   `scoreboard.json` a `examples/demo-run/` en este repo.
4. Grabar el scoreboard con **Replay run**, a 1920x1080.
5. Tomar las capturas de sesión de Bob de esa corrida para `bob_sessions/`.
6. Revisar el video completo buscando nombres o mails de autores antes de publicarlo.
