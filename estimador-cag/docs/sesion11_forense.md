# Sesión 11 live: guía de comprobación

Esta guía está pensada para seguirla en orden, sin necesitar el historial de
la conversación. No borra datos ni sustituye la baseline existente. Las
pruebas que llaman a modelos o generan embeddings tienen coste; se indican
antes de ejecutarlas.

**Antes de cambiar de máquina**, asegúrate de llevarte también los cambios de
código, el archivo de corpus y esta guía. Los cambios solo preparados con
`stage` o todavía sin subir **no aparecen por sí solos** en el otro equipo.
Las tablas y muestras de la baseline están versionadas, pero la base de datos
de PostgreSQL y el `.env` de cada máquina son independientes del repositorio.
No subas claves ni contraseñas a Git.

En la otra máquina, abre una terminal situada en la carpeta `estimador-cag`
del repositorio. Todos los comandos de esta guía se ejecutan desde ahí; si
abres otra terminal, sitúala también en esa carpeta. Puedes comprobarlo con:

```bash
rtk proxy pwd
```

La ruta mostrada debe terminar en `estimador-cag`. Los comandos llevan el
prefijo `rtk proxy` porque es el usado en este entorno. **Si la otra máquina
no tiene `rtk`, elimina únicamente `rtk proxy ` al principio de cada
comando**; el resto del comando es el mismo.

Necesitas Docker con Compose, `uv`, Python 3.11 o superior, conexión a
internet para el proveedor y, si aún faltan, para descargar dependencias y el
modelo de reranking. El primer arranque puede tardar. Puedes comprobar las
herramientas así:

```bash
rtk proxy docker compose version
rtk proxy uv --version
```

Si una no existe, instálala siguiendo las instrucciones de tu equipo antes
de continuar. Para `uv`, consulta su
[guía de instalación](https://docs.astral.sh/uv/getting-started/installation/).

## NUEVO CORPUS

### Qué es

[task_corpus_contradictions.json](../data/task_corpus_contradictions.json) es
nuevo de **sesión 11 live**, no del corpus de sesión 10. Añade dos proyectos
**sintéticos**, con cuatro tareas, para probar discrepancias entre horas
históricas. No hay que borrar el corpus anterior y su ingesta es opcional.

### 1. Comprobar si ya está en PostgreSQL

Primero comprueba si el PostgreSQL de este proyecto está arrancado:

```bash
rtk proxy docker compose ps
```

Debe aparecer el servicio `postgres` activo. Si no está arrancado y quieres
usar el Compose de este repositorio, arranca **solo PostgreSQL** y vuelve a
comprobarlo:

```bash
rtk proxy docker compose up -d postgres
rtk proxy docker compose ps
```

Espera a que figure como `healthy`. Este arranque utiliza el volumen de
Compose de esa máquina; que el servicio esté sano no significa que contenga
los datos de la máquina anterior. Si falla por un puerto ocupado, no detengas
otros procesos: comprueba primero qué servicio está usando el puerto.

Con PostgreSQL arrancado, ejecuta esta consulta de solo lectura.
Busca por ID de presupuesto y también por el final de la ruta de origen, para
detectar incluso una ingesta con el nombre de archivo anterior equivocado:

```bash
rtk proxy docker compose exec -T postgres psql -U postgres -d estimator -v ON_ERROR_STOP=1 <<'SQL'
WITH buscados(budget_id) AS (
  VALUES ('TASK-2023-9001'), ('TASK-2024-9002')
)
SELECT b.budget_id, d.id AS documento, d.source_path, d.document_type,
       count(c.id) FILTER (WHERE c.chunk_type = 'historical_task') AS tareas,
       count(c.embedding) FILTER (WHERE c.chunk_type = 'historical_task') AS vectores
FROM buscados b
LEFT JOIN documents d
  ON d.metadata->>'budget_id' = b.budget_id
  OR d.source_path LIKE '%::' || b.budget_id
LEFT JOIN chunks c ON c.document_id = d.id
GROUP BY b.budget_id, d.id, d.source_path, d.document_type
ORDER BY b.budget_id, d.id;
SQL
```

- Si ambos IDs salen con `documento` vacío y `tareas = 0`, no hay documentos
  coincidentes y puedes usar el comando siguiente.
- Si aparecen documentos con `historical_task`, ya hay datos para ese ID.
  Revisa su origen y que cada proyecto tenga dos tareas con sus dos vectores.
  Si aparecen varias filas para un ID, pueden existir duplicados.
- Si aparece un documento sin tareas históricas, o solo falta uno de los
  proyectos, revisa el caso antes de ingerir: el script comprueba duplicados
  por **ruta de origen**, no por ID. En particular, una ruta antigua
  `data/task_corpus_s10.json::...` o una ruta `corpus-expansion::...` no sería
  reconocida como la nueva ruta del archivo.

Si solo falta un proyecto y el otro está completo, puedes pegar únicamente
el objeto JSON del proyecto que falta —desde su `{` hasta su `}`, sin la
coma que separa los dos objetos— en la pestaña **Corpus**, seleccionando
`historical_task`, como se explica más abajo. La pantalla acepta tanto un
objeto como el array completo. Vuelve a ejecutar la consulta después.

No se ha comprobado el contenido de tu PostgreSQL durante la preparación de
esta guía. Si la consulta falla porque faltan las tablas o el servicio, detente
y revisa la instancia; no interpretes el error como «no están». Si has
confirmado que es la base nueva de este proyecto y aún no se han aplicado sus
migraciones, sigue **Preparar y comprobar los servicios** más abajo y vuelve
a ejecutar la consulta. Una base nueva no contiene automáticamente los datos
de la máquina anterior.

### 2. Ingerir solo si ambos faltan

Necesitas también la API y Redis en marcha y la clave de OpenAI configurada.
Si aún no están preparados, sigue primero **Preparar y comprobar los
servicios** en el apartado siguiente y después vuelve aquí. Luego ejecuta:

```bash
rtk proxy docker compose exec -T estimator python scripts/s09/build_task_corpus.py \
  --ingest-only --out data/task_corpus_contradictions.json
```

Esto **escribe en PostgreSQL y paga embeddings**. Añade dos documentos y cuatro
fragmentos de tipo `historical_task`; no elimina los anteriores. Repite la
consulta y comprueba los dos IDs, sus rutas correctas, dos tareas y dos
vectores por documento. Si falla a mitad, vuelve a consultar antes de repetir.
Una repetición con la misma ruta omite documentos ya ingeridos; no repara
documentos incompletos. El resultado habitual, si no existía ninguno, indica
`2 ingested, 0 already present`. Si uno aparece como presente con otra ruta
o tiene menos de dos tareas con vector, no lo borres ni fuerces una nueva
ingesta para arreglarlo: conserva el resultado y revisa ese caso.

## COMPARAR CON BASELINE

### Preparar y comprobar los servicios

La baseline propia está en [ragas_baseline_s11.json](../evals/ragas_baseline_s11.json)
y su tabla en [ragas_baseline_s11.md](../evals/ragas_baseline_s11.md). **No
sobrescribas esos archivos ni las muestras originales.**

En `estimador-cag`, revisa con tu editor el archivo `.env` de **esta máquina**.
Si ya existe, no lo sobrescribas con el ejemplo. Si no existe, crea una copia
de [.env.example](../.env.example) con el nombre `.env` y edítala. Configura
`OPENAI_API_KEY` y `ESTIMATE_API_KEY`; la primera necesita permisos y saldo
para los modelos utilizados. La segunda es la clave propia de la aplicación:
debe ser la misma para la API y Streamlit y distinta de la clave de OpenAI.
Mantén ambas privadas.

Para los comandos que se ejecutan en el host, `DATABASE_URL` y `REDIS_URL`
deben apuntar a los servicios accesibles **desde el host**, no a los nombres
internos `postgres` y `redis` de Docker. En el Compose de este proyecto, los
destinos habituales son PostgreSQL en `localhost:5432`, base `estimator`, y
Redis en `localhost:6379`. La plantilla `.env.example` contiene los valores
locales de desarrollo. Si tu instalación usa otros, adapta el `.env` con sus
datos reales; no pegues contraseñas en esta guía o en la terminal. Ten en
cuenta que una variable ya definida en el entorno de la terminal puede tener
preferencia sobre el `.env`.

Arranca o comprueba los servicios. **El arranque de la API aplica las
migraciones pendientes**, incluida la de sesión 11; si los datos importan,
asegúrate de tener una copia de seguridad antes. No lances otra migración en
paralelo ni borres volúmenes. Si ya están arrancados con el código actual,
basta con ejecutar las dos últimas comprobaciones:

```bash
rtk proxy docker compose up --build -d
rtk proxy docker compose ps
rtk proxy curl --fail-with-body --silent --show-error http://localhost:8000/health
```

Espera a que `estimator`, `postgres` y `redis` estén activos y sanos. El
último comando debe responder con `"status":"healthy"` y
`"llm_configured":true`. Si la API sigue arrancando, espera y repite `ps` y
la comprobación de salud. Si falla, consulta los logs:

```bash
rtk proxy docker compose logs --tail 100 estimator
rtk proxy docker compose logs --tail 50 postgres redis
```

No continúes hasta resolver errores de arranque o migración. `healthy` no
demuestra que la base contenga el corpus ni que la clave tenga saldo o permisos.

Ahora comprueba la configuración efectiva del **host**, sin imprimir claves:

```bash
rtk proxy env PYTHONPATH=src uv run --locked python - <<'PY'
from urllib.parse import urlsplit
from config import get_settings
from sqlalchemy.engine import make_url

s = get_settings()
db = make_url(s.DATABASE_URL) if s.DATABASE_URL else None
redis = urlsplit(s.REDIS_URL)
print("PostgreSQL:", (db.host, db.port, db.database) if db else "sin configurar")
print("Redis:", (redis.hostname, redis.port))
print("OpenAI configurado:", bool(s.OPENAI_API_KEY))
print("Estimate API key configurada:", bool(s.ESTIMATE_API_KEY))
print("Modelos:", s.REFORMULATION_MODEL, s.GENERATION_MODEL)
PY
```

En el montaje local habitual debe mostrar `localhost` o `127.0.0.1`, base
`estimator`, y `True` para ambas claves. Si muestra `postgres` o `redis` como
host, corrige el destino accesible desde el host. Un `True` solo significa
que hay un valor configurado; no comprueba que funcione.

### Comprobar el corpus de presupuestos

La evaluación busca fragmentos `budget_component`, no las tareas históricas
del primer apartado. El corpus previsto para esta evaluación contiene los
17 presupuestos de ejemplo. Comprueba qué hay en la base de esta máquina:

```bash
rtk proxy docker compose exec -T postgres psql -U postgres -d estimator -v ON_ERROR_STOP=1 <<'SQL'
SELECT d.metadata->>'budget_id' AS budget_id, d.id AS documento, d.source_path,
       count(c.id) AS fragmentos, count(c.embedding) AS vectores
FROM documents d
JOIN chunks c ON c.document_id = d.id
WHERE c.chunk_type = 'budget_component'
GROUP BY d.id, d.metadata, d.source_path
ORDER BY budget_id, d.id;
SQL
```

Para reproducir el conjunto previsto, busca una fila por cada ID desde
`BUD-2024-001` hasta `BUD-2024-017`, sin IDs adicionales ni duplicados y con
el mismo número de fragmentos y vectores en cada fila. Si faltan o sobran
datos, **no borres ni ingieras nada automáticamente**: decide primero si esta
es la base que quieres evaluar.

Si la consulta no devuelve ninguna fila y has confirmado que quieres cargar
los presupuestos de ejemplo en **esta base**, puedes ejecutar lo siguiente con
la API en marcha:

```bash
rtk proxy env ESTIMATOR_BASE_URL=http://localhost:8000 uv run --locked python scripts/query_examples.py
```

El comando **escribe en la base y paga embeddings**: carga los 17 presupuestos
de `data/budgets_sample.json` y después realiza cinco búsquedas de prueba.
Al terminar debería indicar `Corpus: 17 budgets`; repite la consulta anterior.
Si ya había filas, otros orígenes, duplicados o errores, no uses el comando
como reparación automática: el control de duplicados de este script se basa
en la ruta, no en el ID. La guía de [pretrabajo](pre_sesion11_plan.md) da más
detalles.

Aunque esta comprobación coincida, no demuestra que todo el contenido sea
idéntico al de la baseline: no se guardó una huella del corpus completo.
Cambios en el corpus pueden influir en las métricas.

### 1. Comprobar el evaluador

```bash
rtk proxy uv run --locked --script scripts/score_ragas_s11_v2.py --check-deps
```

La baseline registra `ragas 0.4.3`, `datasets 4.8.5` y
`langchain-openai 0.3.35`. Deben coincidir con la salida. Esta comprobación no
llama al juez. Usa `--locked` también al puntuar. Si las versiones no
coinciden o falla el comando, no puntúes todavía: revisa que el repositorio
incluya `scripts/score_ragas_s11_v2.py.lock` y que `uv` pueda preparar su
entorno. No actualices las dependencias de la baseline por tu cuenta.

Antes de pagar la recogida, compara los valores efectivos del host y el golden
con los registrados en la baseline:

```bash
rtk proxy env PYTHONPATH=src uv run --locked python - <<'PY'
import hashlib
import json
from pathlib import Path
from config import get_settings

baseline = json.loads(Path("evals/ragas_baseline_s11.json").read_text())
s = get_settings()
fields = {
    "reformulation_model": s.REFORMULATION_MODEL,
    "generation_model": s.GENERATION_MODEL,
    "generation_reasoning_effort": s.GENERATION_REASONING_EFFORT,
    "generation_max_tokens": s.GENERATION_MAX_TOKENS,
    "retrieval_embedding_model": s.EMBEDDING_MODEL,
    "reranker_model": s.RERANKER_MODEL,
    "top_k": s.RETRIEVAL_TOP_K,
    "recall_k": s.RETRIEVAL_RECALL_TOP_K,
    "rerank_top_n": s.RERANK_TOP_N,
    "rrf_k": s.RRF_K,
    "max_context_tokens": s.MAX_CONTEXT_TOKENS,
}
different = False
for name, current in fields.items():
    original = baseline["configuration"][name]
    same = current == original
    print(f"{name}: {'OK' if same else 'DIFERENTE'} (baseline={original}, actual={current})")
    different |= not same
golden = hashlib.sha256(Path("evals/golden_generation_s11.json").read_bytes()).hexdigest()
same = golden == baseline["golden_sha256"]
print("Golden:", "OK" if same else "DIFERENTE")
raise SystemExit(1 if different or not same else 0)
PY
```

Todas las líneas deben decir `OK`. Si alguna indica `DIFERENTE`, revisa el
`.env` y las variables de entorno antes de continuar; no des por comparable
una evaluación hecha con otra configuración. Esta comprobación no verifica el
contenido completo del corpus.

### 2. Recoger cinco muestras nuevas

Este comando activa **las dos** mejoras nuevas, preparación del contexto y
comprobación semántica. Hace llamadas de pago para reformular, buscar, generar
y, cuando corresponda, verificar evidencia:

```bash
rtk proxy uv run --locked python scripts/eval_ragas_s11.py \
  --collect-only evals/ragas_samples_s11_live.json --augment --gate
```

Las opciones son independientes: omite ambas para una recogida sin esas
mejoras, o usa solo una para estudiarla por separado. Los interruptores de
Streamlit **no sustituyen** a estos argumentos de recogida. Cada recogida
necesita otro nombre de archivo y puede tener coste.
Si cambias el nombre de las muestras, utiliza ese mismo nombre en los pasos
de inspección y puntuación que siguen.

Al terminar, comprueba las cinco muestras sin hacer nuevas llamadas:

```bash
rtk proxy uv run --locked python scripts/eval_ragas_s11_v2.py \
  --inspect-samples evals/ragas_samples_s11_live.json
```

Debe mostrar Q1–Q5 y `PASS`. Si falla la recogida, el archivo puede quedar
incompleto: consérvalo, investiga el error y utiliza otro nombre para un
intento nuevo. No se reanuda parcialmente. Revisa también en el JSON los
`citation_report` y `hallucination_report`; un `judge_error` o líneas
`unverified` no son verificaciones satisfactorias. La inspección valida las
muestras, pero no garantiza por sí sola que sus citas o juicios sean correctos.

### 3. Puntuar con V2 y generar la tabla

Esta ejecución **paga llamadas al juez y embeddings de evaluación**, pero no
regenera las estimaciones:

```bash
rtk proxy uv run --locked --script scripts/score_ragas_s11_v2.py \
  --score-file evals/ragas_samples_s11_live.json \
  --out evals/ragas_scores_s11_live.json
```

Al finalizar verás la tabla por consulta y medias. También se guardan
`evals/ragas_scores_s11_live.json` y `evals/ragas_scores_s11_live.md`. El
scorer rechaza rutas de salida ya existentes: elige nombres nuevos si repites.
Si cambias el nombre de salida, utiliza ese mismo nombre en los dos comandos
de comparación del apartado siguiente.
Si falla por permisos del proveedor, saldo, límite o tiempo de espera, conserva
el error y revisa la causa. Puedes repetir **solo la puntuación** sobre el
mismo archivo de muestras, con una salida nueva; volverá a tener coste.

### 4. Comparar y entender el resultado

Abre juntas la tabla nueva y la [tabla de baseline](../evals/ragas_baseline_s11.md).
Si prefieres ver las medias una al lado de otra, este comando no hace llamadas:

```bash
rtk proxy uv run --locked python - <<'PY'
import json
from pathlib import Path

baseline = json.loads(Path("evals/ragas_baseline_s11.json").read_text())
actual = json.loads(Path("evals/ragas_scores_s11_live.json").read_text())
print("Versiones baseline:", baseline["versions"])
print("Versiones nuevas:  ", actual["versions"])
print("| Métrica | Baseline | Nueva | Diferencia |")
print("| --- | ---: | ---: | ---: |")
for name, old in baseline["average"].items():
    new = actual["average"][name]
    print(f"| {name} | {old:.3f} | {new:.3f} | {new - old:+.3f} |")
PY
```

La diferencia es `nueva - baseline`. Comprueba que las versiones impresas
coinciden antes de interpretar los números. También puedes usar el comparador:

```bash
rtk proxy uv run --locked python scripts/eval_generation_s11.py \
  --gate evals/ragas_scores_s11_live.json
```

Muestra la media nueva y el mínimo permitido: media de baseline menos 0,05.
`FAIL` puede significar regresión o citas colgantes; no borres el resultado.
El comparador rechaza diferencias de golden, modelos, formato de respuesta y
configuración relevante, pero **no comprueba las versiones de dependencias**.
Si aparece `Reports have incompatible...`, no consideres válida la comparación:
el mensaje señala qué valor debes revisar.

El formato y las versiones registradas de la baseline se han comprobado con
el V2 actual. Eso no garantiza una comparación perfectamente controlada:
el estado histórico completo del corpus y las revisiones del proveedor no
están registrados, y los jueces pueden variar entre ejecuciones. Además,
activar las dos mejoras a la vez no permite atribuir una diferencia a una
sola de ellas. Para aislarlas mejor, recoge y puntúa configuraciones separadas
con el mismo corpus y entorno, asumiendo el coste adicional.

La recogida de evaluación no es idéntica a la llamada interactiva: usa una
búsqueda y un umbral específicos y no ejecuta el ciclo de reparación HTTP.
El `hallucination_report` se guarda aparte; V2 no lo envía como respuesta a
RAGAS. Con `--gate`, la confianza incluida en la respuesta sí puede bajar.

## PROBAR NUEVAS FUNCIONALIDADES

Para las pruebas visuales, con la API disponible, inicia Streamlit en otra
terminal desde `estimador-cag/`:

```bash
rtk proxy uv run --locked streamlit run streamlit_app.py
```

Abre la dirección que muestra Streamlit. Las claves deben estar configuradas
en el entorno o `.env`; no las copies a esta guía ni al chat. Las operaciones
de generación, búsqueda semántica y verificación pueden hacer llamadas de pago.
Si has cambiado el `.env` después de arrancar la API o Streamlit, reinicia
los procesos correspondientes para que lean los nuevos valores.

### Ajustes de las mejoras

1. En **Ajustes → Recuperación**, localiza **Evidence check**, **Context
   augmentation** y **Conflicting-source ranges**. Anota sus valores actuales.
2. Cambia uno, pulsa **Guardar recuperación** y comprueba que al volver a
   abrir Ajustes aparece el valor elegido. Repite para los demás si lo deseas.
3. Restaura los valores anotados al terminar. Son ajustes compartidos en Redis
   y afectan a las siguientes llamadas; «Por defecto» usa el valor de `.env`.

En **Ajustes**, el selector **Evidence judge** permite cambiar el modelo de
comprobación para la API interactiva: anota el valor actual, selecciona otro
modelo disponible y pulsa **Guardar** en ese formulario. Comprueba el valor
al volver a abrir Ajustes y restáuralo después. El colector de evaluación usa
su configuración y sus propios argumentos; no presupongas que copia los
interruptores de la interfaz.

### Comprobación de citas y evidencia

1. Activa **Evidence check** y guarda el ajuste.
2. En **RAG Wizard**, abre **Grounded RAG estimate**. Introduce una descripción
   de al menos 100 caracteres, por ejemplo:

   > Queremos una aplicación bancaria móvil con inicio de sesión OAuth2,
   > conexión con entidades bancarias, gestión de consentimiento, registro de
   > transacciones y notificaciones. Necesitamos una estimación por módulos y
   > fuentes históricas que expliquen el esfuerzo.

3. Pulsa **Generate grounded estimate**. Si hay contexto suficiente, revisa
   los contadores de **Citations** y **Evidence check**, las advertencias y
   las citas de cada tarea. En **Response JSON** encontrarás
   `citation_report` y `hallucination_report`, con el estado por línea.
4. Repite con **Evidence check** desactivado: si se genera una estimación,
   `hallucination_report` debe ser `null`. El contenido de la estimación puede
   variar entre llamadas; no esperes los mismos números.

`grounded` en el informe de citas comprueba la pertenencia de los IDs al
contexto, no demuestra que la evidencia sustente la tarea. El informe
semántico puede indicar `grounded`, `degraded`, `insufficient` o `unverified`;
un fallo del juez se muestra, no es una verificación positiva. Si no hay
contexto suficiente, la aplicación puede devolver directamente confianza
`insufficient` y ambos informes vacíos.

**API:** la misma funcionalidad está en `POST /v1/estimate/from-transcript`.
En `http://localhost:8000/docs`, abre el endpoint, pulsa **Try it out**, pon la
clave de estimación en el campo `X-API-Key` y sustituye el cuerpo de ejemplo
por este JSON. Pulsa **Execute** y revisa los mismos campos en la respuesta:

```json
{
  "transcript": "Queremos una aplicación bancaria móvil con inicio de sesión OAuth2, conexión con entidades bancarias, gestión de consentimiento, registro de transacciones y notificaciones. Necesitamos una estimación por módulos y fuentes históricas que expliquen el esfuerzo."
}
```

No incluyas una
`idempotency_key` al repetir con otros ajustes: una clave reutilizada puede
devolver una respuesta cacheada.

### Preparación del contexto

En **Ajustes → Recuperación**, activa o desactiva **Context augmentation** y
genera una estimación fundamentada como en el apartado anterior. El cambio
prepara el texto y el orden del contexto antes de generar; la pantalla muestra
la respuesta, **no el contexto completo**, así que ver números distintos no
demuestra por sí solo qué cambió.

Para inspeccionar contexto guardado, usa una recogida de evaluación con
`--augment` y revisa `contexts` y `context_block` en el JSON de muestras.
Para una comprobación determinista sin llamadas de pago:

```bash
rtk proxy uv run --locked pytest -q tests/test_rag_quality.py -k augmentation
```

### Rangos de horas en el Wizard

Esta prueba usa tareas históricas y, para el ejemplo concreto, el corpus
opcional del primer apartado. La búsqueda real puede devolver otros vecinos:
ingerir el fixture **no garantiza** que aparezca exactamente un rango 40–90 h.

1. Activa **Conflicting-source ranges** en **Ajustes → Recuperación**.
2. En **RAG Wizard**, inicia una ejecución, genera la estructura y, en la
   revisión, añade o edita una tarea del módulo `Notifications` con nombre
   `Real-time notifications delivery service`.
3. Pulsa **Estimate hours**. En **Task hours**, revisa **Neighbors** y, si los
   vecinos encontrados superan el umbral de dispersión, la advertencia con
   rango y motivo. La estimación puntual sigue visible.
4. Desactiva **Conflicting-source ranges** y vuelve a estimar: el campo
   `hours_range` no debe mostrarse. Restaura el ajuste después.

Si no aparece un rango con la opción activa, revisa vecinos, distancias,
umbral y contenido ingerido antes de concluir que falla. La búsqueda usa
embeddings de pago. La prueba automatizada sin llamadas externas está en
[test_task_hours.py](../tests/test_task_hours.py).

**API:** `POST /v1/estimate/tasks/hours` acepta `X-API-Key` y, por ejemplo,
este cuerpo en `/docs`. La respuesta contiene `tasks`, `neighbors`,
`dispersion` y `hours_range`:

```json
{
  "modules": [
    {
      "name": "Notifications",
      "tasks": [{"name": "Real-time notifications delivery service"}]
    }
  ]
}
```

### Pestaña Corpus y API de indexación

Esta pantalla puede **añadir datos y pagar embeddings**. Antes de usarla,
comprueba el primer apartado y decide si quieres modificar el corpus.

1. En **Corpus**, comprueba el total, las filas por tipo y el estado de HNSW.
2. Para probar una ingesta nueva, si los dos IDs del primer apartado faltan y
   quieres incorporarlos, selecciona `historical_task`, pega el array de
   [task_corpus_contradictions.json](../data/task_corpus_contradictions.json)
   y pulsa **Add to corpus**. Esta es una **alternativa** al comando de ingesta
   anterior: no ejecutes ambos sin volver a comprobar la base.
3. Observa estado, progreso, documentos indexados u omitidos, fragmentos,
   estadísticas antes/después e historial. Un fallo debe aparecer como `failed`
   con su error; un reinicio de la API puede dejar un trabajo sin terminar.
4. Repite la consulta SQL del primer apartado para verificar lo persistido.
   Si vuelves a enviar el mismo array desde esta pantalla, los IDs existentes
   del mismo tipo deberían aparecer como omitidos.

**API:** en `/docs`, los endpoints protegidos con `X-API-Key` son
`GET /embeddings/index/stats`, `POST /embeddings/index/runs`,
`GET /embeddings/index/runs` y `GET /embeddings/index/runs/{job_id}`. El POST
recibe `{"documents": [...], "chunk_type": "historical_task"}` y responde
`202` con un trabajo; consulta su estado hasta `completed` o `failed`.
Las estadísticas cuentan la tabla compartida `chunks` por tipo; no son tres
tablas separadas.

### Si una prueba falla

- **401 en la API o en Streamlit:** comprueba que `ESTIMATE_API_KEY` esté
  configurada y coincida en ambos procesos; después de cambiar `.env`,
  reinícialos. No pegues la clave en logs ni en capturas.
- **422:** revisa el JSON enviado y el detalle de validación que devuelve
  `/docs`. En la estimación fundamentada, el texto necesita al menos 100
  caracteres.
- **502 o 503:** consulta `docker compose logs --tail 100 estimator` y guarda
  el `X-Request-ID` si aparece en la respuesta. Comprueba también PostgreSQL,
  Redis y la configuración del proveedor.
- **Error de cuota, permisos o timeout del proveedor:** revisa el mensaje y
  la cuenta antes de repetir. No repitas en bucle: algunas llamadas anteriores
  pueden haber tenido coste incluso si el proceso terminó con error.
- **Resultados distintos de los esperados:** conserva el JSON, los ajustes y
  el estado del corpus; los modelos y la búsqueda no garantizan resultados
  idénticos en cada ejecución. Distingue una advertencia o un rango no
  observado de un error real del proceso.
