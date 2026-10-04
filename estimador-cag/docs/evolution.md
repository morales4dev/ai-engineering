# Evolución del estimador-cag

Cronología de cambios de producto/arquitectura, leída desde `main` y las ramas auxiliares que acabaron mergeadas ahí. HEAD de referencia: `964841c` (2026-10-04).

| Columna | Significado |
|---|---|
| Entró en | Rama o evento en el que aterrizó el cambio |
| Vigente | `[x]` si el cambio (o su sucesor directo e inequívoco) sigue en el HEAD de `main` hoy. `[]` si se retiró o se sustituyó por otro contrato |
| Cambio | Qué se añadió o cambió |
| Retirado en | Solo si `Vigente` es `[]`: rama o evento que lo quitó |

Nombres de evento (como en las ramas, salvo `v2` y `sesion-02`, que no fueron rama propia):

- `sesion-02` — primer commit + prototipo + FastAPI (`f15d32b` … `e59ca40`)
- `v2` — `v2 ready` / `v2 revised` (`cd9145e`, `5a5da23`)
- `sesion_03_entrega_20260921` — Streamlit y niveles CAG del ejercicio
- `sesion_03_post` — port de la sesión 3 (LiteLLM, Redis, SSE, Compose)
- `sesion_03_forense` — endurecimiento del port
- `pre_sesion_04` — templates Jinja, contrato tipado, Streamlit HTTP, limpieza SSE
- `session_04_forense` — port live de la sesión 4 (Instructor, guardrails, caches, historial)

No entra `session1/` (ejercicios sueltos, no son el estimador).

| Entró en | Vigente | Cambio | Retirado en |
|---|---|---|---|
| sesion-02 | [x] | Scaffold del servicio: `pyproject.toml`, Settings, layout FastAPI (`main`, routers, services) | |
| sesion-02 | [x] | `GET /health` y `POST /api/v1/estimate` | |
| sesion-02 | [] | Contrato de entrada `transcription` (acta de reunión) y salida markdown libre | pre_sesion_04 |
| sesion-02 | [] | Few-shot CAG en Python (`src/context/examples.py`) inyectado en el system prompt | session_04_forense |
| sesion-02 | [] | Llamada LiteLLM directa desde `llm_service` (Anthropic) | sesion_03_post |
| sesion-02 | [x] | FastAPI “de verdad”: Pydantic Settings, structlog, lifespan, schemas propios | |
| sesion-02 | [] | Knobs de request CAG: `preprocessing` (none / inline_cleaning / two_phase), `example_format`, `num_examples`, `use_examples`, override de modelo | pre_sesion_04 |
| v2 | [] | Catálogo canónico de ejemplos (dataclass + markdown/json/narrative) y two-phase (`extract_requirements` + estimación) | session_04_forense |
| v2 | [] | `evaluation.py` / `StructureCheck`: score estructural del markdown (título, tabla, totales) | session_04_forense |
| v2 | [] | CORS abierto (`allow_origins=["*"]` + `allow_credentials=True`) | sesion_03_forense |
| sesion_03_entrega_20260921 | [x] | Primera UI Streamlit de estimación (`streamlit_app.py`) | |
| sesion_03_entrega_20260921 | [] | Streamlit in-process: la UI llama al LLM/SDK en el mismo proceso (`EstimationTokenStream`, luego `streamlit_inprocess.py`) | pre_sesion_04 |
| sesion_03_entrega_20260921 | [] | `simple_chat.py` (playground Streamlit, no el formulario) | session_04_forense |
| sesion_03_entrega_20260921 | [] | Niveles 1–2–3 CAG (`build_cag_context`, sidebar con el system prompt activo) | session_04_forense |
| sesion_03_post | [x] | Wrapper LiteLLM único (`LLMWrapper`) en lugar de SDKs sueltos | |
| sesion_03_post | [x] | Timeout configurable (`LLM_TIMEOUT`) | |
| sesion_03_post | [] | Retries configurables (`LLM_RETRIES`) en el wrapper de texto | session_04_forense |
| sesion_03_post | [] | Fallback automático `PRIMARY_MODEL` → `FALLBACK_MODEL` | session_04_forense |
| sesion_03_post | [x] | Cache exact-match en Redis (fail-open, TTL). La clave original era hash del prompt | |
| sesion_03_post | [] | `cost_usd` en la respuesta (tabla de precios; luego `None` si el modelo no está) | session_04_forense |
| sesion_03_post | [] | `POST /api/v1/estimate/stream` (SSE) y `complete_stream` | pre_sesion_04 |
| sesion_03_post | [] | Streaming consciente de cache (hit = un chunk; miss = stream y persistir) | pre_sesion_04 |
| sesion_03_post | [] | Demo HTML SSE (`/static/sse_demo.html`) | pre_sesion_04 |
| sesion_03_post | [x] | Streamlit como cliente HTTP de la API (deja de ser el runtime del LLM) | |
| sesion_03_post | [x] | Docker Compose: servicio `estimator` + Redis | |
| sesion_03_forense | [x] | La API arranca sin API keys; `/health` siempre 200 con `llm_configured`; `/estimate` → 503 si faltan | |
| sesion_03_forense | [x] | Fallos de proveedor genéricos en el borde HTTP (502, `detail` fijo; bugs a 500; sin `except Exception`) | |
| sesion_03_forense | [x] | Frontera de prompt: el user es dato; delimitador por request (`prompt_boundary`) | |
| sesion_03_forense | [] | `cost_usd: null` si el modelo no está en la tabla de precios (el campo luego desaparece) | session_04_forense |
| sesion_03_forense | [] | `max_length=50_000` en `transcription` | pre_sesion_04 |
| sesion_03_forense | [x] | CORS abierto desactivado (middleware comentado; no hay cliente browser cross-origin) | |
| sesion_03_forense | [x] | Handler de `/estimate` síncrono (`def`): LiteLLM no bloquea el event loop | |
| pre_sesion_04 | [x] | Templates Jinja2 `prompts/estimation/v1/` + loader (`render_estimation_prompt`) | |
| pre_sesion_04 | [x] | Contrato tipado: `description` (20–2000) + `project_type` / `detail_level` / `output_format` | |
| pre_sesion_04 | [] | Salida libre `{ text, prompt_version }` | session_04_forense |
| pre_sesion_04 | [x] | Streamlit pasa a formulario HTTP (`st.form` → `POST /estimate`) | |
| pre_sesion_04 | [x] | Prompt v2 (`prompts/estimation/v2/`) y query `?prompt_version=` (default `v1`) | |
| pre_sesion_04 | [x] | Reorden: `session2/estimador-cag/` → `estimador-cag/` en la raíz del repo | |
| session_04_forense | [x] | `EstimationResult` + Instructor: `/estimate` devuelve `{ result, prompt_version, cached }` validado | |
| session_04_forense | [x] | Guardrails de entrada (moderación, injection, PII → 400) y de salida (filtro out-of-scope) | |
| session_04_forense | [x] | Cache exact-match recableado a clave `estimation:v2:` sobre el request tipado (las claves hash-de-prompt de la sesión 3 ya no pegan) | |
| session_04_forense | [x] | Cache semántico (bucket + cosine, Redis Stack / RediSearch) | |
| session_04_forense | [x] | Historial persistente en Postgres: `GET /api/v1/estimations` y `GET /api/v1/estimations/{id}`; pestaña Recent en Streamlit | |
| session_04_forense | [x] | Espera “flashy” en Streamlit: rota etiquetas de fase mientras `/estimate` está en vuelo (no es SSE) | |
| session_04_forense | [x] | Limpieza del path vivo: fuera leftovers CAG/`transcription` (`examples.py`, `evaluation.py`, `simple_chat`, `complete()` de texto). Queda FastAPI + Streamlit HTTP | |
