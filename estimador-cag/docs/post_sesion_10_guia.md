# Después de la sesión 10: guía de uso y comprobación

Esta guía recorre las funcionalidades de la sesión 10 en nuestro proyecto:
estimación por tareas y horas desde **Streamlit**, recuperación de antecedentes
con **FastAPI** y persistencia en **PostgreSQL**.

Cada prueba indica qué hacer, qué comprobar y dónde está el código. Las llamadas
a modelos y embeddings pueden tardar y tienen coste. Los resultados del modelo
y las búsquedas pueden variar: utiliza los ejemplos para observar el proceso y
revisar las cifras y el orden obtenidos.

## 1. Antes de arrancar

- Necesitas Docker con Compose, Python 3.11 o superior, `uv` y acceso a los
  modelos configurados y a la API de embeddings de OpenAI.
- Desde una terminal, entra en el proyecto:

  ```bash
  cd /home/basf/wsTakeoff/ai-engineering/estimador-cag
  ```

- Revisa tu `.env` y conserva sus valores actuales. Necesitas `OPENAI_API_KEY`,
  `ESTIMATE_API_KEY` y `RETRIEVAL_API_KEY`. Las dos últimas son claves propias
  de la aplicación y deben ser distintas entre sí y de la clave de OpenAI.
  `ESTIMATE_API_KEY` debe estar disponible también para el proceso de
  Streamlit. Consulta [.env.example](../.env.example) para los nombres y los
  modelos configurados. Mantén las claves privadas y fuera del repositorio.
- **Haz una copia de seguridad de PostgreSQL si sus datos importan.** Al
  arrancar, Compose ejecuta las migraciones pendientes automáticamente. La
  migración de sesión 10 conserva las ejecuciones anteriores en días y las
  marca como `legacy`. El wizard muestra las ejecuciones de sesión 10.
- Antes de cargar el corpus nuevo, revisa y elimina de la base el corpus
  sintético de tareas de sesión 9 siguiendo el paso 3. Sus ejemplos pueden
  influir en las horas y en la puntuación de similitud.

## 2. Arrancar y comprobar

- **API, PostgreSQL y Redis**

  ```bash
  docker compose up -d --build
  docker compose ps
  docker compose exec -T estimator alembic current
  curl --fail-with-body http://localhost:8000/health
  ```

  Si utilizas `docker-compose` con guion, sustituye `docker compose` por
  `docker-compose` en los comandos de esta guía.

  **Comprueba:** los tres servicios están activos, `/health` responde y la
  revisión de Alembic es `0006_session10_wizard` o una posterior. La
  documentación de la API está en <http://localhost:8000/docs>.
  Si algo falla, revisa `docker compose logs estimator`.

  **Código:** [docker-compose.yml](../docker-compose.yml) arranca los servicios
  y aplica las migraciones; [0006_session10_wizard.py](../alembic/versions/0006_session10_wizard.py)
  añade los campos del nuevo wizard.

- **Interfaz Streamlit**

  En otra terminal, desde `estimador-cag`, ejecuta:

  ```bash
  uv run --locked streamlit run streamlit_app.py
  ```

  **Comprueba:** abre la dirección indicada por Streamlit, normalmente
  <http://localhost:8501>, y localiza las pestañas **RAG Wizard** y **Ajustes**.
  El primer arranque puede necesitar descargar dependencias. Si cambias el
  `.env`, recrea el servicio de la API y reinicia Streamlit.

  **Código:** [streamlit_app.py](../streamlit_app.py) conecta la interfaz con la
  API; [wizard_ui.py](../src/wizard_ui.py) dibuja el nuevo wizard.

## 3. Preparar los datos

Las migraciones preparan las estructuras de la base. Una vez arrancados los
servicios, revisa el corpus anterior antes de cargar el nuevo.

- **Revisar y retirar el corpus sintético de tareas de sesión 9.**

  Los comandos siguientes seleccionan los documentos `historical_task_breakdown`
  cuyo origen es `data/task_corpus.json`, la ruta usada para ese corpus. El
  corpus de sesión 10 tiene el origen `data/task_corpus_s10.json`; los
  presupuestos y las demás colecciones tienen sus propios orígenes y tipos.

  1. **Haz una copia de seguridad** desde `estimador-cag`:

     ```bash
     backup="backup-antes-s10-$(date +%Y%m%d-%H%M%S).dump"
     ( set -o noclobber; docker compose exec -T postgres pg_dump -U postgres -d estimator -Fc > "$backup" )
     ```

     Comprueba que el comando termina correctamente y que la copia se puede
     leer:

     ```bash
     docker compose exec -T postgres pg_restore -l < "$backup"
     ```

  2. **Revisa los documentos y el número de fragmentos afectados:**

     ```bash
     docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d estimator -c \
       "SELECT d.id, d.source_path, count(c.id) AS fragmentos
        FROM documents d LEFT JOIN chunks c ON c.document_id = d.id
        WHERE d.document_type = 'historical_task_breakdown'
          AND split_part(d.source_path, '::', 1) = 'data/task_corpus.json'
        GROUP BY d.id, d.source_path ORDER BY d.id;"
     ```

     **Comprueba:** la lista contiene los documentos que quieres retirar. Si
     devuelve cero filas, este corpus ya está ausente con esa ruta. Si aparecen
     otros orígenes que también quieras limpiar, identifícalos por separado.

  3. **Cuando hayas revisado la lista y la copia, elimina esos documentos:**

     ```bash
     docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres -d estimator -c \
       "DELETE FROM documents
        WHERE document_type = 'historical_task_breakdown'
          AND split_part(source_path, '::', 1) = 'data/task_corpus.json'
        RETURNING id, source_path;"
     ```

     PostgreSQL elimina también los `chunks` asociados a cada documento. El
     comando muestra los IDs y orígenes eliminados. Repite la consulta del
     paso 2 y comprueba que devuelve cero filas. El archivo JSON del repositorio
     permanece disponible.

  **Código:** [models.py](../src/generation/rag/store/models.py) define la
  relación entre documentos y chunks con borrado en cascada;
  [task_hours.py](../src/generation/rag/task_hours.py) usa las tareas
  históricas al calcular las horas.

Ahora comprueba el conjunto de datos antes de ingerir:

```bash
docker compose exec -T postgres psql -U postgres -d estimator -c \
  "SELECT document_type, count(*) FROM documents GROUP BY 1 ORDER BY 1;"
docker compose exec -T postgres psql -U postgres -d estimator -c \
  "SELECT chunk_type, count(*) FROM chunks GROUP BY 1 ORDER BY 1;"
docker compose exec -T postgres psql -U postgres -d estimator -c \
  "SELECT count(*) AS proyectos_s10 FROM documents
   WHERE source_path LIKE 'data/task_corpus_s10.json::%';"
```

- **Corpus de tareas para estimar horas.** Es el más importante para el wizard.
  El archivo [task_corpus_s10.json](../data/task_corpus_s10.json) ya existe:
  contiene 60 proyectos y 1.543 tareas **sintéticas** en ocho sectores.
  Para cargar el archivo incluido:

  ```bash
  docker compose exec -T estimator python scripts/s09/build_task_corpus.py --ingest-only
  ```

  **Comprueba:** el script informa de proyectos ingeridos o ya presentes;
  la consulta `proyectos_s10` anterior debe mostrar 60 tras una carga completa.
  La tabla `chunks` debe contener entradas `historical_task`. Si ya había
  tareas antiguas, el total de ese tipo puede ser mayor que 1.543.

  **Código:** [build_task_corpus.py](../scripts/s09/build_task_corpus.py) lee
  el JSON y envía cada proyecto a la API de ingesta. Los fragmentos se guardan
  en nuestra tabla `chunks`. Ingerir genera embeddings y puede tener coste.
  Una ejecución posterior omite los proyectos identificados como ya cargados.

- **Presupuestos, reuniones y documentación técnica para búsqueda avanzada.**
  Para probar las tres colecciones y la evaluación, carga los ejemplos:

  ```bash
  docker compose exec -T estimator python scripts/build_advanced_corpus.py
  ```

  **Comprueba:** el resumen indica cuántos presupuestos, transcripciones y
  documentos se crearon o se omitieron. La carga completa desde una base vacía
  aporta 17 presupuestos, 5 transcripciones y 4 documentos técnicos. En las
  consultas anteriores busca `historical_budget`, `meeting_transcript` y
  `technical_doc`, y sus chunks `budget_component`, `meeting_segment` y
  `doc_section`. Si ya había datos, los totales pueden ser mayores.

  **Código:** [build_advanced_corpus.py](../scripts/build_advanced_corpus.py)
  lee [budgets_sample.json](../data/budgets_sample.json),
  [transcripts_sample.json](../data/transcripts_sample.json) y
  [technical_docs_sample.json](../data/technical_docs_sample.json). Divide
  reuniones en segmentos y documentos en secciones; usa `documents` y `chunks`
  para las tres colecciones. Esta carga también genera embeddings y puede
  tener coste; al repetirla omite los documentos ya detectados.

- **Archivos de entrada.** Los corpus anteriores son JSON incluidos en el
  repositorio y se cargan con los comandos indicados. El wizard acepta pegar
  una conversación o subir un `.txt` UTF-8 para iniciar una ejecución.

## 4. Probar el wizard de horas en Streamlit

Abre **RAG Wizard**. Puedes usar una conversación como esta:

> Queremos una tienda online con catálogo de productos, carrito y checkout.
> Necesitamos pagos mediante una pasarela, acceso seguro de clientes, gestión
> de pedidos y una interfaz web. El equipo y la fecha de entrega están
> pendientes de definir.

- **Reformular la conversación.**
  - **Haz:** pega el texto y pulsa **Start guided estimation**. También puedes
    subir un `.txt` UTF-8 de entre 100 y 50.000 caracteres.
  - **Comprueba:** aparece una ejecución con número y la sección
    **1. Reformulation**, con el objeto y el texto de búsqueda. Compara el
    resultado con la conversación: revisa los detalles aportados y los
    aspectos pendientes de definir.
  - **Código:** [query_reformulator.py](../src/generation/rag/query_reformulator.py)
    reformula; [rag_runs.py](../src/services/rag_runs.py) crea la ejecución y
    guarda el resultado.

- **Generar la estructura.**
  - **Haz:** pulsa **Generate / regenerate structure** y espera.
  - **Comprueba:** aparecen módulos y tareas en **3. Review structure**,
    junto con la confianza, el razonamiento y posibles supuestos. Esta etapa
    genera la estructura; las horas se estiman después. Si el contexto es
    insuficiente, puede aparecer una explicación en lugar de una estructura.
  - **Código:** [structure.py](../src/generation/rag/structure.py) pide al
    modelo los módulos y tareas; [rag_runs.py](../src/services/rag_runs.py) guarda
    la respuesta.

- **Revisar módulos y tareas.**
  - **Haz:** cambia el nombre o la descripción de una tarea, añade una fila o
    elimina otra en la tabla. Para un mismo módulo, mantén la misma descripción
    en todas sus filas.
  - **Comprueba:** el botón **Estimate hours** valida que haya nombres de
    módulo y tarea y que cada tarea tenga un nombre único dentro del módulo.
    La estructura revisada se guarda al estimar las horas; la confirmación se
    realiza en el paso de horas y tarifas.
  - **Código:** [_modules](../src/wizard_ui.py) convierte y valida las filas;
    [wizard.py](../src/generation/rag/wizard.py) valida la petición en la API.

- **Estimar horas con tareas parecidas.**
  - **Haz:** pulsa **Estimate hours** con el corpus de tareas ya ingerido.
    En **Task search settings** puedes activar **Override retrieval settings
    for this estimation** para cambiar vecinos, distancia, búsqueda o
    reranking solo para esta estimación.
  - **Comprueba:** cada tarea muestra horas y `similarity/agreement`, o un aviso
    **no matching task**. Abre **Neighbors** para ver los IDs, presupuestos,
    horas y distancias usadas. Una distancia menor indica mayor cercanía.
    La puntuación es un indicador heurístico de cercanía y acuerdo entre horas;
    interpretarla como probabilidad requeriría una calibración.
  - **Prueba del umbral:** con la opción de override, pon **Maximum cosine
    distance** en `0.0` y vuelve a estimar. Las tareas cuyas coincidencias
    tengan una distancia mayor que cero quedarán con horas pendientes. Una
    coincidencia exacta puede conservar su estimación; revisa cada resultado.
    Después restaura el umbral o desactiva el override.
  - **Código:** [task_hours.py](../src/generation/rag/task_hours.py) busca
    `historical_task`, selecciona candidatos con distancia vectorial real y
    calcula un promedio ponderado por distancia. Cuando faltan coincidencias
    devuelve `has_match=false` y deja las horas pendientes de revisión.

- **Corregir y confirmar horas y tarifas.**
  - **Haz:** en **5. Confirm hours and rates**, introduce manualmente las
    horas que falten y modifica una tarifa. La tarifa inicial es 75 EUR/h.
    Usa números enteros mayores o iguales a cero y pulsa **Confirm and save**.
  - **Comprueba:** la confirmación requiere completar todas las horas y tarifas.
    **Current total** debe ser la suma de horas y de `horas × tarifa` por
    tarea; tras guardar aparece **Confirmed** con la fecha. Una hora o tarifa
    cero es válida, pero debe ser una decisión tuya.
  - **Código:** [wizard_ui.py](../src/wizard_ui.py) valida y muestra el total;
    [rag_runs.py](../src/services/rag_runs.py) recalcula y guarda el total en
    el servidor a partir de las horas y tarifas.

- **Reabrir y repetir etapas.**
  - **Haz:** en **Execution history**, selecciona la ejecución y pulsa
    **Open**. Después prueba **Generate / regenerate structure** o
    **Re-run reformulation**.
  - **Comprueba:** al reabrir ves lo guardado. Al repetir una etapa anterior
    con éxito se limpian de esa ejecución los resultados posteriores. El
    historial muestra como máximo las 20 ejecuciones recientes de sesión 10.
  - **Código:** [estimation_runs.py](../src/services/estimation_runs.py)
    persiste y filtra por versión; [rag_runs.py](../src/services/rag_runs.py)
    limpia los resultados posteriores.

## 5. Probar la búsqueda avanzada y los ajustes

Las búsquedas siguientes llaman a embeddings y pueden usar modelos adicionales.
Para los ejemplos con `curl`, prepara las claves de la aplicación en **esa
terminal**, usando los valores de tu `.env`:

```bash
read -rs -p "Clave RETRIEVAL_API_KEY: " RETRIEVAL_API_KEY; echo
read -rs -p "Clave ESTIMATE_API_KEY: " ESTIMATE_API_KEY; echo
```

Los comandos usan `--fail-with-body` para mostrar el error si la API devuelve
un HTTP 4xx/5xx. En <http://localhost:8000/docs> también puedes probarlos
indicando el `X-API-Key` correspondiente.

- **Búsqueda en varias colecciones y routing.**
  - **Haz:** con los corpus avanzados cargados, ejecuta:

    ```bash
    curl --silent --show-error --fail-with-body \
      http://localhost:8000/v1/retrieval/advanced-search \
      -H "X-API-Key: $RETRIEVAL_API_KEY" \
      -H 'Content-Type: application/json' \
      -d '{
        "query_text": "Show the meeting transcript and budget for Stripe Connect checkout and seller onboarding and webhook reconciliation.",
        "top_k": 5,
        "distance_threshold": 2.0,
        "search_mode": "hybrid",
        "rerank": false,
        "routing_enabled": true,
        "query_transform_enabled": false,
        "temporal_decay_enabled": false
      }'
    ```

  - **Comprueba:** la respuesta incluye `routing` con `level`, `targets` y
    `reason`; también `chunks`, `cardinality`, `technique` y `subqueries`.
    En esta consulta, las palabras `meeting`, `transcript` y `budget` permiten
    comprobar las reglas de selección. Mira el `collection`, `source_id` y
    contenido de cada resultado. Puede haber entre cero y cinco; revisa
    los datos y filtros si ocurre. `2.0` es un umbral permisivo para explorar;
    revisa la relevancia de los resultados.
  - **Código:** [retrieval_advanced.py](../src/routers/retrieval_advanced.py)
    recibe la petición; [router.py](../src/generation/rag/retrieval/router.py)
    selecciona colecciones y [collections.py](../src/generation/rag/retrieval/collections.py)
    las relaciona con nuestros tipos de documento y chunk.

- **Búsqueda vectorial, híbrida y reranker.**
  - **Haz:** repite la petición anterior cambiando `search_mode` entre
    `"vector"` y `"hybrid"`; después prueba `"rerank": true`. Mantén el resto
    igual para poder comparar.
  - **Comprueba:** compara IDs, contenido, orden y número de
    resultados. El híbrido combina búsquedas vectoriales y por palabras; el
    reranker vuelve a ordenar candidatos. Los resultados **pueden coincidir**:
    para comprobar que el modelo de reranking carga, ejecuta:

    ```bash
    docker compose exec -T estimator python -m generation.rag.retrieval.verify_reranker
    ```

    Debe mostrar `Reranker loaded:`. La primera carga puede descargar pesos
    desde Hugging Face y tardar; mantén activada la verificación TLS.
  - **Código:** [search_pipeline.py](../src/generation/rag/retrieval/search_pipeline.py)
    recupera candidatos; [fusion.py](../src/generation/rag/retrieval/fusion.py)
    combina rankings y [reranker.py](../src/generation/rag/retrieval/reranker.py)
    carga y aplica el modelo.

- **Transformar una consulta y aplicar antigüedad.**
  - **Haz:** repite la petición con `"query_transform_enabled": true` y observa
    `technique` y `subqueries`. Después prueba también
    `"temporal_decay_enabled": true`.
  - **Comprueba:** la transformación puede expandir la consulta o dividirla en
    varias búsquedas. Si falla la llamada al modelo, el sistema registra un
    aviso y vuelve a una consulta `direct`: revisa los logs si esperabas otra
    técnica. El decay reduce el peso de documentos antiguos con fecha;
    los documentos con fecha desconocida conservan su peso. Compara `document_date`,
    `relevance_score` y orden; el resultado dependerá de los documentos.
  - **Código:** [query_transform.py](../src/generation/rag/retrieval/query_transform.py)
    elige y genera las consultas; [advanced_search_pipeline.py](../src/generation/rag/retrieval/advanced_search_pipeline.py)
    coordina las etapas y [temporal.py](../src/generation/rag/retrieval/temporal.py)
    aplica el peso temporal.

- **Filtros por colección.**
  - **Haz:** en la misma petición, añade `"collections": ["technical_doc"]`
    y `"doc_version": "v3.2"`. Para otra prueba usa
    `"collections": ["transcript"]` y `"min_date": "2024-01-01"`.
  - **Comprueba:** `routing.level` indica selección explícita y los resultados
    pertenecen a la colección solicitada. El filtro de versión se aplica a
    documentación técnica; el de fecha, a reuniones y presupuestos. Los
    filtros de sector y tecnología se aplican a presupuestos.
  - **Código:** [collections.py](../src/generation/rag/retrieval/collections.py)
    construye los filtros según el tipo de colección.

- **Cambiar ajustes en caliente.**
  - **Haz:** en Streamlit abre **Ajustes → Recuperación**. Cambia, por ejemplo,
    `Task-hours top_k` o el umbral y pulsa **Guardar recuperación**. Para
    modificar un valor numérico que esté en modo default, desmarca primero
    su casilla de default y guarda; después introduce el valor y vuelve a
    guardar. También puedes cambiar búsqueda híbrida, reranking, routing,
    transformación y decay.
  - **Comprueba:** vuelve a abrir **Ajustes** y revisa el valor efectivo.
    Las nuevas estimaciones de horas usan el ajuste global por defecto; el
    override del wizard permite elegir otro valor. En `advanced-search`, omite
    la opción correspondiente del JSON para usar el ajuste global: un valor
    explícito en la petición tiene prioridad. Al terminar, vuelve a
    **Por defecto** y guarda.
  - **Código:** [config.py](../src/routers/config.py) expone
    `GET/PUT /api/v1/config/retrieval`; [runtime_config.py](../src/services/runtime_config.py)
    guarda overrides en Redis. La clave exigida es `ESTIMATE_API_KEY`. Si
    Redis falla, las lecturas usan los defaults y las escrituras devuelven 503.

## 6. Probar las API de estimación

- **Estimar horas mediante la API independiente.**
  - **Haz:** con el corpus de tareas cargado:

    ```bash
    curl --silent --show-error --fail-with-body \
      http://localhost:8000/v1/estimate/tasks/hours \
      -H "X-API-Key: $ESTIMATE_API_KEY" \
      -H 'Content-Type: application/json' \
      -d '{
        "modules": [{
          "name": "Checkout & Cart",
          "tasks": [{"name": "Cart & checkout flow"}]
        }],
        "top_k": 5,
        "distance_threshold": 0.45,
        "search_mode": "vector",
        "rerank": false
      }'
    ```

  - **Comprueba:** la respuesta contiene `tasks`; cada resultado indica
    `has_match`, horas, puntuación y vecinos cuando hay coincidencia. Cuando
    falta una coincidencia cercana, `estimated_hours` es `null`. La respuesta
    se devuelve directamente al cliente.
  - **Código:** [rag_runs.py de rutas](../src/routers/rag_runs.py) expone el
    endpoint; [task_hours.py](../src/generation/rag/task_hours.py) calcula las
    horas. El wizard usa una ruta adicional que sí guarda la ejecución.

- **Comprobar que sigue disponible el endpoint antiguo en días.**
  - **Haz:** con presupuestos históricos cargados:

    ```bash
    curl --silent --show-error --fail-with-body \
      http://localhost:8000/v1/estimate/from-transcript \
      -H "X-API-Key: $ESTIMATE_API_KEY" \
      -H 'Content-Type: application/json' \
      -d '{
        "transcript": "Queremos una tienda online con catálogo, carrito y checkout, integración de pagos, acceso seguro para clientes y un panel de gestión de pedidos."
      }'
    ```

  - **Comprueba:** la respuesta tiene `total_engineer_days` y `confidence`.
    Cuando la evidencia es insuficiente, los días pueden ser `null` y la
    confianza `insufficient`. Interpreta el resultado en días de ingeniero.
  - **Código:** [rag_estimate.py](../src/routers/rag_estimate.py) conserva la
    ruta independiente; [estimator.py](../src/generation/rag/estimator.py)
    ejecuta su flujo de estimación en días.

- **Comprobar las claves.**
  - **Haz:** prueba la clave de búsqueda en el endpoint de estimación y la
    clave de estimación en `/v1/retrieval/advanced-search`.
  - **Comprueba:** la API debe responder **401** en ambos casos. Cada endpoint
    protegido requiere la clave correspondiente.
  - **Código:** [security.py](../src/routers/security.py) comprueba las claves
    independientes.

## 7. Comparar y ejecutar pruebas automatizadas

- **Evaluación de recuperación.**
  - **Haz:** con los tres corpus avanzados cargados y la API/servicios en marcha:

    ```bash
    docker compose exec -T estimator python scripts/eval_retrieval_s10.py
    ```

  - **Comprueba:** se imprimen las configuraciones A–H, precisión por
    configuración y consulta, y latencia media. La evaluación incluye
    embeddings y, según la configuración, llamadas al modelo; realiza un
    calentamiento y tres ejecuciones medidas por consulta y configuración.
    Puede tardar y generar coste. Una advertencia de cero resultados exige
    revisar la ingesta. Compara las métricas de las distintas configuraciones.
  - **Código:** [eval_retrieval_s10.py](../scripts/eval_retrieval_s10.py)
    ejecuta la comparación; [golden_retrieval.json](../evals/golden_retrieval.json)
    contiene las consultas y fuentes consideradas relevantes.

- **Tests locales con dobles para las dependencias externas.**
  - **Haz:** desde `estimador-cag`:

    ```bash
    uv run --locked pytest tests/test_wizard_ui.py tests/test_task_hours.py \
      tests/test_estimate_runs_http.py tests/test_advanced_pipeline.py \
      tests/test_advanced_retrieval_http.py tests/test_retrieval_runtime_config.py -q
    ```

  - **Comprueba:** pytest termina con todos los casos seleccionados aprobados.
    Estas pruebas usan dobles para las partes externas; comprueba también tu
    PostgreSQL, Redis, claves y proveedores mediante las pruebas anteriores.
  - **Código:** los archivos de [tests](../tests) muestran ejemplos concretos
    de los contratos y casos límite.

## 8. Datos antiguos y cierre

- Para **revisar** qué ejecuciones anteriores quedaron marcadas como `legacy`:

  ```bash
  docker compose exec -T postgres psql -U postgres -d estimator -c \
    "SELECT id, status, created_at FROM estimation_runs
     WHERE workflow_version = 'legacy' ORDER BY id;"
  ```

  Si sigues queriendo eliminarlas, hazlo tú después de revisar los registros y
  la copia de seguridad. El endpoint antiguo en días permanece disponible como
  llamada independiente.
- Si aparecen errores, revisa `docker compose logs estimator`, el estado de
  Redis/PostgreSQL, las claves y si los corpus están realmente ingeridos. Una
  respuesta vacía puede deberse al umbral, a los filtros o a la ausencia de
  antecedentes.
- La integración se ha comprobado con tests automatizados y SQL de migración
  generado offline. Quedan pendientes la migración real, las ingestas y una
  prueba completa con modelos, PostgreSQL y Redis reales.
