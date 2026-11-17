# Pre-sesión 10: guía de comprobación manual

El objetivo es comprobar la búsqueda por palabras, su combinación con la búsqueda
vectorial y la segunda selección del reranker. Cada punto indica **qué hacer**,
**qué comprobar** y **qué código lo permite**. No hace falta generar estimaciones
para comparar la recuperación.

## Preparación

- **Arrancar el entorno y verificar el reranker antes de continuar.**

  Desde `estimador-cag`, revisa tu `.env` sin sobrescribirlo. Necesitas
  `OPENAI_API_KEY` para los embeddings, `RETRIEVAL_API_KEY` para la API de búsqueda
  y `ESTIMATE_API_KEY` para el wizard. Los valores de referencia están en
  [.env.example](../.env.example).

  ```bash
  docker compose up -d --build
  docker compose ps
  docker compose exec -T estimator python -m generation.rag.retrieval.verify_reranker
  ```

  **Comprueba:** la API responde en <http://localhost:8000/health> y el verificador
  termina mostrando `Reranker loaded:` seguido del nombre del modelo. La primera
  descarga puede tardar; necesita acceso a Hugging Face.

  **Código:** [pyproject.toml](../pyproject.toml) incorpora las dependencias del
  cross-encoder; [reranker.py](../src/generation/rag/retrieval/reranker.py) carga el
  modelo en CPU cuando se necesita y lo reutiliza dentro del mismo proceso.
  [verify_reranker.py](../src/generation/rag/retrieval/verify_reranker.py) comprueba
  la carga, no la calidad de los resultados. Al ejecutarse en un proceso separado,
  no deja caliente el modelo de la API, aunque sí puede dejar descargados sus pesos.

  **Si falla:** detén aquí las pruebas, como pide el ejercicio. Ante un error TLS,
  revisa la confianza de certificados y la red de esa máquina; no desactives la
  verificación TLS. Reiniciar o recrear el contenedor puede requerir otra descarga,
  porque no hemos añadido un volumen persistente para la caché del modelo.

- **Comprobar que hay presupuestos para recuperar.**

  ```bash
  docker compose exec -T postgres psql -U postgres -d estimator -c \
    "SELECT document_type, count(*) FROM documents GROUP BY 1 ORDER BY 1;"
  docker compose exec -T postgres psql -U postgres -d estimator -c \
    "SELECT chunk_type, count(*) FROM chunks GROUP BY 1 ORDER BY 1;"
  ```

  **Comprueba:** existen documentos `historical_budget` y chunks
  `budget_component`. Si falta el corpus de presupuestos, cárgalo:

  ```bash
  docker compose exec -T estimator python scripts/query_examples.py
  ```

  Ese script también ejecuta búsquedas de la sesión 8; esas salidas **no son**
  la evaluación A/B/C/D. La carga completa del dataset aporta 17 presupuestos y
  omite los documentos ya ingeridos. Crear sus embeddings tiene coste de OpenAI.

  **Código:** [query_examples.py](../scripts/query_examples.py) carga
  [budgets_sample.json](../data/budgets_sample.json). Esta carga ya existía;
  la sesión 10 utiliza sus fragmentos y vectores, no exige regenerarlos.

## Base de datos y búsqueda por palabras

- **Comprobar que la migración ha preparado el buscador léxico.**

  La API aplica las migraciones al arrancar. Compruébalo:

  ```bash
  docker compose exec -T estimator alembic current
  docker compose exec -T postgres psql -U postgres -d estimator -c \
    "SELECT column_name, is_generated, generation_expression
     FROM information_schema.columns
     WHERE table_schema = 'public' AND table_name = 'chunks'
       AND column_name = 'content_tsv';"
  docker compose exec -T postgres psql -U postgres -d estimator -c \
    "SELECT indexname, indexdef FROM pg_indexes
     WHERE schemaname = 'public' AND tablename = 'chunks'
       AND indexname = 'ix_chunks_content_tsv';"
  ```

  **Comprueba:** la revisión actual es `0005_session10_fts`, la columna aparece
  como generada `ALWAYS`, su expresión usa `english` y el índice usa `gin`.
  Si la revisión está atrasada, revisa primero los logs de arranque.

  **Código:** [0005_session10_fts.py](../alembic/versions/0005_session10_fts.py)
  añade una representación buscable de cada texto y su índice. PostgreSQL calcula
  también la columna para los chunks existentes y la mantiene cuando cambia
  `content`. No cambia los textos ni sus embeddings.

- **Entender qué normaliza FTS y comprobar una búsqueda sin embeddings.**

  ```bash
  docker compose exec -T postgres psql -U postgres -d estimator -c \
    "SELECT to_tsvector('english', 'payment payments') AS indexed_words,
            plainto_tsquery('english', 'payments') AS search_words;"
  docker compose exec -T postgres psql -U postgres -d estimator -c \
    "SELECT id, metadata->>'budget_id' AS budget_id,
            ts_rank_cd(content_tsv, plainto_tsquery('english', 'transaction ledger')) AS rank,
            left(content, 220) AS preview
     FROM chunks
     WHERE chunk_type = 'budget_component'
       AND content_tsv @@ plainto_tsquery('english', 'transaction ledger')
     ORDER BY rank DESC, id
     LIMIT 5;"
  ```

  **Comprueba:** `payment` y `payments` se reducen a la misma raíz. La segunda
  consulta devuelve fragmentos con las palabras de búsqueda normalizadas y una
  puntuación. Lee el contenido completo de algún ID si el recorte no muestra
  ambas palabras.

  La coincidencia decide quién entra; `ts_rank_cd` ordena los que entraron usando
  la distribución y cercanía de las palabras. No descubre sinónimos por significado.
  El índice acelera la búsqueda; en un corpus pequeño PostgreSQL puede preferir
  leer toda la tabla, así que no exijas que cada consulta use el índice GIN.

  **Código:** [search_lexical](../src/generation/rag/store/repository.py) ejecuta
  esta búsqueda. `plainto_tsquery` exige **todas las palabras significativas**
  de la consulta, no solo una de ellas. Una descripción muy larga puede no tener
  coincidencias léxicas aunque exista un presupuesto relevante.

  Usamos `english` porque el corpus real está en inglés, pese a lo que dice el
  enunciado. El wizard reformula las peticiones a inglés antes de buscar. FTS no
  traduce; la API de búsqueda independiente recibe el texto tal como lo envías.

## Comparar las cuatro configuraciones

- **Probar A: búsqueda vectorial sin reranker, como referencia.**

  Puedes usar <http://localhost:8000/docs> o copiar los siguientes comandos en
  una terminal. Define una vez la clave de búsqueda (no la de OpenAI):

  ```bash
  RETRIEVAL_API_KEY='demo-retrieval-key'
  ```

  Sustituye ese valor de ejemplo por el de tu `.env` si es distinto. Esta variable
  solo prepara los comandos: no cambia la configuración del servidor.
  `--fail-with-body` conserva el mensaje de error y hace fallar el comando ante
  un HTTP 4xx/5xx; `--write-out` muestra el código HTTP y el tiempo total del cliente.
  Ese tiempo incluye el embedding y, cuando procede, la carga inicial del modelo:
  no es la misma medida que la latencia del benchmark.

  **Petición A:**

  ```bash
  curl --silent --show-error --fail-with-body \
    --request POST 'http://localhost:8000/v1/retrieval/search' \
    --header 'Content-Type: application/json' \
    --header "X-API-Key: $RETRIEVAL_API_KEY" \
    --write-out '\nHTTP %{http_code} | Total: %{time_total}s\n' \
    --data-raw '{
      "query_text": "Headless e-commerce storefront with a product catalog, shopping cart checkout and personalized product recommendations.",
      "top_k": 5,
      "distance_threshold": 2.0,
      "search_mode": "vector",
      "rerank": false,
      "chunk_types": ["budget_component"]
    }'
  ```

  **Comprueba:** recibes un HTTP 200 y hasta cinco chunks. Anota sus `id`,
  `budget_id`, contenido y orden. Sin resultados, revisa la carga del corpus.
  Usamos `2.0` para que el umbral no descarte candidatos durante la comparación;
  no es una recomendación para producción.

  **Código:** [search_chunks](../src/generation/rag/retriever.py) conserva el
  recorrido vectorial cuando ambos extras están desactivados.
  [retrieval.py](../src/routers/retrieval.py) acepta los controles y devuelve los
  resultados sin generar una estimación. La llamada sí consume un embedding.

- **Probar B: búsqueda híbrida sin reranker.**

  **Petición B, con la misma consulta que A:**

  ```bash
  curl --silent --show-error --fail-with-body \
    --request POST 'http://localhost:8000/v1/retrieval/search' \
    --header 'Content-Type: application/json' \
    --header "X-API-Key: $RETRIEVAL_API_KEY" \
    --write-out '\nHTTP %{http_code} | Total: %{time_total}s\n' \
    --data-raw '{
      "query_text": "Headless e-commerce storefront with a product catalog, shopping cart checkout and personalized product recommendations.",
      "top_k": 5,
      "distance_threshold": 2.0,
      "search_mode": "hybrid",
      "rerank": false,
      "chunk_types": ["budget_component"]
    }'
  ```

  Para observar mejor la rama léxica, compara también A y B con una consulta corta.
  Este bloque ejecuta ambas peticiones:

  ```bash
  for mode in vector hybrid; do
    curl --silent --show-error --fail-with-body \
      --request POST 'http://localhost:8000/v1/retrieval/search' \
      --header 'Content-Type: application/json' \
      --header "X-API-Key: $RETRIEVAL_API_KEY" \
      --write-out "\nMode: $mode | HTTP %{http_code} | Total: %{time_total}s\n" \
      --data-raw "{
        \"query_text\": \"transaction ledger\",
        \"top_k\": 5,
        \"distance_threshold\": 2.0,
        \"search_mode\": \"$mode\",
        \"rerank\": false,
        \"chunk_types\": [\"budget_component\"]
      }" || break
  done
  ```

  **Comprueba:** obtienes una lista única, sin IDs duplicados. Compara el orden
  con A y lee si los nuevos resultados son útiles. No es obligatorio que cambie:
  las dos búsquedas pueden coincidir, o la rama léxica puede devolver cero hits.

  ```bash
  docker compose logs --tail=100 estimator
  ```

  Busca `rag_retrieve_done`: muestra `search_mode`, `vector_hits`, `lexical_hits`,
  `results` y `search_time_ms`. Para demostrar que participó FTS, comprueba
  `lexical_hits` mayor que cero, no solo que la petición diga `hybrid`.

  **Código:** [search_pipeline.py](../src/generation/rag/retrieval/search_pipeline.py) recupera
  hasta 50 candidatos por rama y [fusion.py](../src/generation/rag/retrieval/fusion.py)
  los combina con RRF. Cada posición aporta apoyo; aparecer bien colocado en ambas
  listas suma más. `RRF_K=60` suaviza la diferencia entre posiciones.

  **Importante:** en híbrida, `distance` no es la puntuación final de RRF. Un chunk
  encontrado solo por palabras lleva `1.0` como valor de compatibilidad, no como
  distancia calculada. No juzgues el orden híbrido ordenando esa columna.

- **Probar C y D: activar la segunda selección del reranker.**

  **Petición C: vectorial con reranker.**

  ```bash
  curl --silent --show-error --fail-with-body \
    --request POST 'http://localhost:8000/v1/retrieval/search' \
    --header 'Content-Type: application/json' \
    --header "X-API-Key: $RETRIEVAL_API_KEY" \
    --write-out '\nHTTP %{http_code} | Total: %{time_total}s\n' \
    --data-raw '{
      "query_text": "Headless e-commerce storefront with a product catalog, shopping cart checkout and personalized product recommendations.",
      "top_k": 5,
      "distance_threshold": 2.0,
      "search_mode": "vector",
      "rerank": true,
      "chunk_types": ["budget_component"]
    }'
  ```

  **Petición D: híbrida con reranker.**

  ```bash
  curl --silent --show-error --fail-with-body \
    --request POST 'http://localhost:8000/v1/retrieval/search' \
    --header 'Content-Type: application/json' \
    --header "X-API-Key: $RETRIEVAL_API_KEY" \
    --write-out '\nHTTP %{http_code} | Total: %{time_total}s\n' \
    --data-raw '{
      "query_text": "Headless e-commerce storefront with a product catalog, shopping cart checkout and personalized product recommendations.",
      "top_k": 5,
      "distance_threshold": 2.0,
      "search_mode": "hybrid",
      "rerank": true,
      "chunk_types": ["budget_component"]
    }'
  ```

  Ejecuta cada variante una segunda vez: la primera llamada con reranker puede
  incluir la carga del modelo y no representa la latencia habitual.

  **Comprueba:** recibes hasta cinco resultados. Compara sus IDs y su orden con
  A/B; lee si responden mejor a lo pedido. En los logs, `rerank=true` confirma el
  modo y `reranker_loaded` permite identificar la carga inicial. El orden puede
  coincidir con el anterior; eso por sí solo no demuestra un fallo.

  **Código:** [search_pipeline.py](../src/generation/rag/retrieval/search_pipeline.py) entrega
  hasta `RETRIEVAL_RECALL_TOP_K=50` candidatos a
  [reranker.py](../src/generation/rag/retrieval/reranker.py). El cross-encoder
  evalúa cada pareja consulta-fragmento y conserva `RERANK_TOP_N=5`. Si falla,
  se devuelve un error: no se sustituye silenciosamente por búsqueda sin reranker.
  Sus puntuaciones no están expuestas en la respuesta; `distance` sigue siendo
  la distancia vectorial original o el valor de compatibilidad, no su puntuación.

## Integración en Streamlit

- **Comprobar que los controles llegan al backend y al contexto.**

  En otra terminal, desde `estimador-cag`:

  ```bash
  uv sync --locked
  uv run --locked streamlit run streamlit_app.py
  ```

  Abre **RAG Wizard** y empieza una ejecución con este texto:

  > Queremos una plataforma de comercio electrónico con catálogo de productos,
  > carrito, checkout y recomendaciones personalizadas. Necesitamos una interfaz
  > web y una API para gestionar el catálogo y los pedidos.

  **Comprueba:** el `Search text` reformulado está en inglés. En **Retrieval**,
  fija `top_k=5`, conserva los mismos filtros y prueba las cuatro combinaciones
  de **Search mode** y **Rerank top candidates**. Pulsa **Run / re-run retrieval**
  después de cada cambio; cambiar un control sin enviar el formulario no ejecuta
  una búsqueda.

  **Código:** [streamlit_app.py](../streamlit_app.py) incorpora los controles;
  [rag_runs.py](../src/services/rag_runs.py) los guarda con la recuperación y los
  transmite a `search_chunks`. Los filtros de sector/año ya existían: no son una
  funcionalidad añadida en este ejercicio. El sector del brief puede aplicarse
  por defecto, así que esta prueba del wizard no replica exactamente el benchmark.

  Pulsa **Assemble context** y verifica que sus fuentes pertenecen a los resultados
  seleccionados. Repite la búsqueda: el contexto anterior debe desaparecer y
  tendrás que ensamblarlo de nuevo. Si decides pulsar **Generate estimate**,
  comprueba sus citas, pero recuerda que tarda y consume llamadas adicionales al
  LLM. No necesitas hacerlo cuatro veces para medir la recuperación.

  **Código:** el coordinador limpia los pasos posteriores al repetir la búsqueda;
  el ensamblador ya existente usa los chunks que entrega el nuevo ranking.
  El ranking no garantiza por sí solo una estimación correcta.

## Medir y decidir

- **Revisar las etiquetas y ejecutar el golden set.**

  Lee las cinco consultas de [golden_retrieval.json](../evals/golden_retrieval.json)
  y sus `relevant_budget_ids`. Abre los presupuestos indicados en el corpus y
  comprueba que estás de acuerdo con su relevancia. Una etiqueta a nivel de
  presupuesto considera relevantes todos sus chunks, aunque un componente
  concreto pueda ser menos útil para esa consulta.

  Desde `estimador-cag`, ejecuta el benchmark **en el host**, donde también está
  disponible la carpeta `evals`:

  ```bash
  uv run --locked python scripts/eval_retrieval_s10.py
  ```

  Tu `.env` debe tener `DATABASE_URL` apuntando al PostgreSQL accesible desde el
  host, normalmente `localhost:5432`, y `OPENAI_API_KEY`. El hostname `postgres`
  es para la red de Compose, no para este comando en el host.

  **Comprueba:** imprime cuatro filas:

  | Configuración | Búsqueda | Reranker |
  | --- | --- | --- |
  | A | Vectorial | No |
  | B | Híbrida | No |
  | C | Vectorial | Sí |
  | D | Híbrida | Sí |

  Cada fila incluye `Precision@5` entre 0 y 1 y latencia media en milisegundos.
  Por ejemplo, tres chunks relevantes entre cinco dan `0.60`. Los chunks del
  mismo presupuesto cuentan por separado: no es precisión sobre cinco presupuestos
  distintos. Si hay menos de cinco hits, los huecos cuentan como no relevantes.

  **Código:** [eval_retrieval_s10.py](../scripts/eval_retrieval_s10.py) usa las
  mismas cinco consultas en las cuatro variantes, solo chunks `budget_component`
  y umbral `2.0`. Calcula sus embeddings una vez, carga el modelo, calienta cada
  consulta/configuración y mide tres repeticiones. La precisión es la media de
  las cinco consultas; la latencia es la media de las quince mediciones por variante.

  La latencia medida **excluye reformulación, embeddings, carga inicial y generación**:
  mide recuperación y, cuando procede, reranking. El script no reformula las
  consultas inglesas y no guarda automáticamente la tabla. Copia su salida para
  el entregable. Si B se parece a A, revisa también si las consultas largas están
  dejando la rama léxica sin coincidencias; no presupongas una mejora.

- **Elegir con números, no por el nombre de la técnica.**

  Compara cuánto sube `Precision@5` y cuántos milisegundos añade cada variante.
  Escribe una conclusión breve: cuál usarías y por qué esa mejora compensa, o no,
  la espera adicional para estimar proyectos. D no tiene por qué ganar.

  **Estado de verificación:** esta guía describe comprobaciones pendientes en un
  entorno real. Los tests de código pasaron, pero no sustituyen la carga efectiva
  del modelo, la migración en PostgreSQL ni la tabla A/B/C/D. No hay métricas reales
  aportadas todavía; no interpretes ejemplos o resultados esperados como mediciones.
