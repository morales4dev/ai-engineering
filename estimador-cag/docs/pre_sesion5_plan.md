Cinco cortes. Tras cada uno se para a revisar. El one-shot (`POST /api/v1/estimate` + pestaña New + Recent) no se toca. El camino nuevo es aditivo.

Fuera de este plan: tests del paso 7, Camino A (Files API), persistencia de sesiones/turnos, resumen acumulativo, anclas, tier dinámico, Actor-Critic-Boss, Rails. No se copia `origin/session_5`; solo se usó como contrato cuando el enunciado callaba.

---

# Decisiones cerradas

- Cliente: Streamlit. Sin Rails. Tres pestañas: New (one-shot), **Conversational**, Recent (Postgres one-shot). `st.tabs`.
- Adjuntos: Camino B (`pypdf` + `python-docx`). Solo `.pdf` + `.docx`, por extensión del filename. Sin filename o upload vacío: se ignora. Tipos no soportados → 415. Extracción rota → 422. Concatenar con `--- attachment: filename ---`.
- `project_metadata`: extractor LLM (Instructor) + fail-open. Merge: escalares no-nulos ganan; tecnologías, unión case-insensitive.
- Extractor: `src/services/metadata_extractor.py`. Templates `src/prompts/metadata_extraction/v1/system.j2` + `user.j2`. Contexto = transcript enriquecido + `EstimationResult` + metadata previa.
- Historial assistant: JSON de `EstimationResult` (fases, totales, confidence), no solo el `summary`.
- One-shot intacto: mismas caches, guardrails, persistencia Postgres. Sin `session_id`.
- Path conversacional: caches off (`cached=false`). No se escribe en `history.py`.
- Templates estimación: bloque `<project_metadata>` en v1 y v2. El one-shot pasa metadata vacía (`StrictUndefined`).
- Cómo ve el cliente la metadata: el estimate conversacional devuelve `project_metadata` en `EstimationResponseReloaded`. No hay `GET /sessions/{id}`.
- Prefijo: `POST /sessions` y `POST /sessions/{id}/estimate` (sin `/api/v1`).
- Multipart: `transcript` (min 20, max 2000, como `description` del one-shot) + `project_type` + `detail_level` + `output_format` + `attachments` opcional. Los enums hacen falta para renderizar los templates actuales. El texto de los adjuntos va **después**, fuera de ese tope.
- Respuesta conversacional: clase `EstimationResponseReloaded` — `{ result, prompt_version, cached, project_metadata }`. `cached` siempre `false`. El one-shot sigue en `EstimationResponse`.
- `prompt_version` del estimate de sesión: default **`v2`** (como Lidr `session_5`). Acepta `?prompt_version=` (v1|v2; desconocida → 422). Streamlit conversacional: sin selector; llama sin query → v2.
- Layout: router `src/routers/sessions.py`; attachments `src/services/attachments.py`; store clase `SessionStore` **dentro** de `src/sessions.py`; orquestación `src/services/conversational.py`. No fusionar `sessions.py` con `src/services/history.py` (eso es el log Postgres).
- Wrapper: el `complete_structured` one-shot no se rompe. Método nuevo que acepta `messages[]`. `prompt_boundary` solo envuelve el user nuevo.
- Settings: `MAX_CONVERSATION_TURNS=6`, `MAX_ATTACHMENT_CHARS=60000` (truncar, no 413), `METADATA_EXTRACTOR_MODEL` default `gpt-4o-mini`.
- Streamlit: `POST /sessions` solo al estar/entrar en Conversational, y solo si no hay `session_id` en `st.session_state`. Confirmar **solo** en “Nueva conversación” (`st.dialog` / segundo clic). Salir de la pestaña no pregunta ni borra la sesión.
- Puente de cortes: **A**. El estimate de sesión nace one-shot (`complete_structured`, sin historial ni extractor). Los cortes 3–4 lo sustituyen por `messages[]` + metadata. Un rato hay ruta “muda” de memoria.

---

# Corte 1 — Estado de sesión + POST /sessions

Existe una sesión vacía direccionable. Todavía no hay LLM.

## sessions.py

- [ ] `ConversationHistory`: pares user+assistant, `max_turns` (default 6). Al pasar el límite, tira los pares más viejos. El system no se guarda; se regenera cada turno. `to_messages_list()` devuelve `[{role, content}, …]` sin system.
- [ ] `ProjectMetadata`: `project_name`, `assumed_team_size`, `mentioned_technologies`, `agreed_scope`. Todo opcional / vacío en el turno 0. `is_empty()` + `merge_with()`.
- [ ] `Session`: `session_id` (UUID v4) + history + metadata. Store = `dict` en el proceso. Docstring: volatilidad aceptada; sin BBDD/Redis de sesiones. No thread-safe; un worker.
- [ ] Setting `MAX_CONVERSATION_TURNS=6`.
- [ ] Si choca el nombre `Session` con SQLAlchemy en `history.py`, aliasar. No fusionar.

## POST /sessions

- [ ] `{"session_id": "..."}`. 201.

**Parada:** `POST /sessions` crea id. Reiniciar uvicorn vacía el dict.

---

# Corte 2 — Adjuntos Camino B + endpoint multipart

El endpoint acepta transcript + ficheros, enriquece el texto y ya llama al pipeline de estimación. Historial y metadata llegan en los cortes 3–4; aquí el modelo aún “olvida” entre turnos.

## Deps y extracción

- [ ] Declarar `pypdf`, `python-docx` y `python-multipart` (esta última hoy solo es transitiva).
- [ ] Extracción local en el servicio IA. Tipos no soportados → 415. Extracción rota → 422. Vacío se ignora.
- [ ] Concatenar con `--- attachment: filename.pdf ---`.
- [ ] Extracción en `src/services/attachments.py`. Solo `.pdf` / `.docx` por extensión. Sin filename o vacío: se ignora.
- [ ] Setting `MAX_ATTACHMENT_CHARS=60000`: truncar, no 413. El campo form `transcript` sí reutiliza el tope del one-shot (20–2000); el texto extraído va después.

## POST /sessions/{session_id}/estimate

- [ ] Router `src/routers/sessions.py`. Orquestación aún one-shot (puente A); `conversational.py` entra en 3–4.
- [ ] `multipart/form-data`: `transcript` (20–2000), los 3 enums como `Form`, `attachments` lista opcional de `UploadFile`. `?prompt_version=` (default v2).
- [ ] Sesión inexistente → 404. Input guardrail sobre el texto enriquecido → 400. Proveedor → 502.
- [ ] Caches apagadas. `cached=false`.
- [ ] No persistir en Postgres.
- [ ] Response `EstimationResponseReloaded`: `{ result, prompt_version, cached, project_metadata }` (metadata vacía / default hasta el corte 3).

**Parada:** curl multipart a una sesión existente devuelve un `EstimationResult` válido. Un PDF cambia el texto que entra al prompt (logs). Entre turnos aún no hay memoria.

---

# Corte 3 — project_metadata en el system prompt + extractor

Los hechos del proyecto viven fuera del array `messages` y se reinyectan cada turno.

## Templates y loader

- [ ] Bloque `<project_metadata>` en `system.j2` de v1 y v2. Si está vacío, el bloque lo dice (primer turno).
- [ ] `render_estimation_prompt` (one-shot) pasa metadata vacía. Mismo `StrictUndefined`.
- [ ] Render conversacional: transcript enriquecido + enums + metadata actual.

## Extractor

- [ ] `src/services/metadata_extractor.py` + templates `metadata_extraction/v1/`. Contexto: transcript enriquecido + `EstimationResult` + metadata previa.
- [ ] Segunda llamada LLM tras la respuesta del estimador. Instructor → `ProjectMetadata` parcial. Modelo `METADATA_EXTRACTOR_MODEL` (default `gpt-4o-mini`).
- [ ] Fail-open: si falla, se loguea y se conserva lo anterior.
- [ ] Merge con el previo (escalares / unión de techs).
- [ ] El estimate conversacional incluye `project_metadata` en su response. Streamlit no adivina nada.

**Parada:** segundo turno sin repetir el nombre del proyecto. La respuesta ya trae metadata no vacía.

---

# Corte 4 — Ventana deslizante + wrapper con messages

El LLM recibe historial recortado, no un one-shot disfrazado.

- [ ] Orquestación pasa a `src/services/conversational.py`. El endpoint deja de one-shotear (fin del puente A).
- [ ] `to_messages_list()`: system regenerado con metadata actual + últimos ≤ `MAX_TURNS` pares + user nuevo.
- [ ] Método nuevo en el wrapper. One-shot intacto.
- [ ] `prompt_boundary` solo en el user nuevo.
- [ ] Trim por pares, no por mensaje suelto.
- [ ] Append del turno después del filtro de salida. Assistant = `result.model_dump_json()`.

**Parada:** el 7º turno no manda más de `MAX_TURNS` pares. El system sigue ahí. El nombre del proyecto vive en metadata, no porque el turno 1 siga en el array.

---

# Corte 5 — Streamlit + README

El alumno ve la separación historial vs memoria.

## Tres pestañas

- [ ] New estimation: el formulario one-shot actual, sin cambios de contrato.
- [ ] Pestaña **Conversational**: `POST /sessions` solo al estar/entrar ahí, y solo si no hay `session_id` en `st.session_state`. Transcript + `st.file_uploader` múltiple (PDF/DOCX) + los 3 enums. Sin selector de `prompt_version` (API default v2). Submit → multipart al estimate de sesión. Pintar `result` como hoy. Guardar `project_metadata` de la respuesta en `session_state` y mostrarla en sidebar o expander (más el `session_id`).
- [ ] Recent: no se toca.
- [ ] “Nueva conversación”: confirmar (`st.dialog` / segundo clic), otro `POST /sessions`, reset de transcript / ficheros / último result / metadata pintada. Salir de la pestaña no confirma ni borra.
- [ ] Reutilizar la espera “flashy”; el POST es multipart, no JSON.
- [ ] FastAPI reinició → 404 de sesión: crear otra y avisar. No hay `DELETE /sessions`.

## README

- [ ] Camino B y por qué.
- [ ] Extractor LLM y por qué (y fail-open).
- [ ] Memoria volátil. Caches off en el path conversacional.
- [ ] Cómo levantar y un curl de dos turnos.

**Parada:** dos turnos en la UI, metadata visible, “Nueva conversación” limpia. Sin tests.

---

# Criterios que damos por hechos (sin paso 7)

- `POST /sessions` devuelve `session_id`.
- `POST /sessions/{id}/estimate` multipart → schema Pydantic de estimación + `project_metadata`.
- Varios turnos no pierden el nombre del proyecto.
- Metadata cambia entre turnos de forma visible en Streamlit.
- La ventana no crece sin techo.
- README con Camino B + método de extracción de metadata.

---

# Riesgos

- `history` (Postgres) vs historial conversacional: en UI y docs, “conversational history” vs “saved estimations”.
- Cache en el path de sesión = bug silencioso. No se enciende.
- `description` max 2000 del one-shot no vale para transcript+PDF.
- El Streamlit de Lidr `session_5` no es el modelo del paso 6; el suyo es Rails.
- Sin tests, trim y merge solo se pillan a mano.

---

# Thoughts

Los huecos de “una sesión limpia tendría que decidir” **ya están cerrados** (arriba + cortes). Esto queda como rastro de la sesión de huecos, no como lista abierta.

## Huecos, ahora cerrados

**Dónde vive cada pieza.** Router `src/routers/sessions.py`. Attachments `src/services/attachments.py`. `SessionStore` clase dentro de `src/sessions.py`. Orquestación `src/services/conversational.py`. Extractor LLM `src/services/metadata_extractor.py`. `llm_service.py` se queda en el one-shot.

**`prompt_version` del path conversacional.** Default `v2` (evidencia Lidr `session_5`). Query `?prompt_version=` sí. UI sin selector.

**Contrato fino.** Clase `EstimationResponseReloaded` (path de sesión). Shape = `EstimationResponse` + `project_metadata`. El one-shot no se toca. `transcript` 20–2000. Solo `.pdf` + `.docx` por extensión. Sin filename / vacío: ignorar.

**Settings.** Confirmados: `MAX_ATTACHMENT_CHARS=60000`, `METADATA_EXTRACTOR_MODEL` default `gpt-4o-mini`.

**Prompt del extractor.** Templates `metadata_extraction/v1/`. Contexto 1+2+3.

**Streamlit “al cargar”.** POST solo en pestaña Conversational si no hay `session_id`. Label `Conversational`. Confirm solo en “Nueva conversación”.

**Corte 2 vs 3–4.** Puente A: endpoint nace one-shot; 3–4 sustituyen por `messages[]` + extractor.

**HTTP menor.** `POST /sessions` → 201 (el enunciado no lo exige; está en el plan). 404/415/422/400/502 sí. No hay `DELETE /sessions`.

## Contexto de esta sesión (para no redescubrirlo)

**Repos.** Alumno: `ai-engineering` rama `pre-session-05`, app en `estimador-cag/`. Referencia: `ai-engineering-lidr` en `session_5` (`4a4de0d exercise session 5`). No existe `solutions/session-05`. `session_05_live` mete resumen, tiers y Actor-Critic: fuera. El checkout Lidr `session_4` está más atrás que nosotros (ellos texto libre; nosotros ya tenemos Instructor, guardrails, caches, Postgres).

**Estado actual nuestro (evidencia de código, 2026-10-04).** `POST /api/v1/estimate` JSON → `{ result, prompt_version, cached }`. Wrapper solo `system` + un `user`. `history.py` = log Postgres, no memoria. Templates sin `<project_metadata>`. Streamlit = New + Recent. Sin `pypdf` / `python-docx` en `pyproject.toml`. `python-multipart` solo transitiva en `uv.lock`. Tenemos `prompt_boundary`; Lidr `session_5` no.

**Cómo Lidr enseña la metadata (y por qué no lo copiamos).** Estimate FastAPI **no** devuelve metadata. Rails, tras cada turno, hace `GET /sessions/{id}` y guarda una foto en su tabla `chat_sessions.latest_metadata` para sobrevivir al F5. Streamlit de Lidr **no** se adaptó. Elegimos B: el estimate conversacional trae `project_metadata`; Streamlit lo guarda en `session_state`. Sin GET. `/estimate` no se toca (campo nuevo solo en el model del path de sesión).

**Historial assistant.** Confirmado: `result.model_dump_json()`, no el `summary`. El siguiente turno ve números y fases.

**Lidr extras que no arrastramos.** Paquete `sessions/` + `EstimationService` clase. Espejo Postgres en Rails. `GET /sessions`. Persistencia de cada result conversacional en Rails. Caches off en conversacional **sí** lo hacemos (misma razón: mismo transcript, distinta sesión, no es la misma llamada).

**Q3 en una frase.** El extractor escribe en RAM de FastAPI. El cliente no lo ve a menos que se lo mandemos. A = GET. B = va en la respuesta del estimate. A+B = las dos. Cerrado: B. Clase: `EstimationResponseReloaded`.

## Lo que no hay que reabrir

Tests (paso 7): no. Camino A (Files API): no. Rails: no. Persistencia de turnos/sesiones: no. GET de sesión: no. Encender caches en conversacional: no. Fusionar `sessions.py` con `history.py`: no. Romper `complete_structured` one-shot: no. Confirm al cambiar de pestaña: no. Selector de `prompt_version` en Streamlit: no.
