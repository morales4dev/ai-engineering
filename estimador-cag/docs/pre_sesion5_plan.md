Cinco cortes. Tras cada uno se para a revisar. El one-shot (`POST /api/v1/estimate` + pestaña New + Recent) no se toca. El camino nuevo es aditivo.

Fuera de este plan: tests del paso 7, Camino A (Files API), persistencia de sesiones/turnos, resumen acumulativo, anclas, tier dinámico, Actor-Critic-Boss, Rails. No se copia `origin/session_5`; solo se usó como contrato cuando el enunciado callaba.

---

# Decisiones cerradas

- Cliente: Streamlit. Sin Rails. Tres pestañas: New (one-shot), Conversational (nuevo), Recent (Postgres one-shot).
- Adjuntos: Camino B (`pypdf` + `python-docx`). Texto extraído concatenado con `--- attachment: filename ---`.
- `project_metadata`: extractor LLM (Instructor) + fail-open. Merge: escalares no-nulos ganan; tecnologías, unión case-insensitive.
- Historial assistant: JSON de `EstimationResult` (fases, totales, confidence), no solo el `summary`.
- One-shot intacto: mismas caches, guardrails, persistencia Postgres. Sin `session_id`.
- Path conversacional: caches off (`cached=false`). No se escribe en `history.py`.
- Templates: bloque `<project_metadata>` en v1 y v2. El one-shot pasa metadata vacía (`StrictUndefined`).
- Cómo ve el cliente la metadata: el estimate conversacional devuelve `project_metadata` en un response model propio. No hay `GET /sessions/{id}`.
- Prefijo: `POST /sessions` y `POST /sessions/{id}/estimate` (sin `/api/v1`).
- Multipart: `transcript` + `project_type` + `detail_level` + `output_format` + `attachments` opcional. Los enums hacen falta para renderizar los templates actuales.
- Módulo: `src/sessions.py` (un archivo, como el enunciado). No fusionar con `src/services/history.py` (eso es el log Postgres).
- Wrapper: el `complete_structured` one-shot no se rompe. Método nuevo que acepta `messages[]`. `prompt_boundary` solo envuelve el user nuevo.

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
- [ ] Setting `MAX_ATTACHMENT_CHARS` (propuesta 60000): truncar, no 413. Este path no reutiliza `EstimationRequest.description` (max 2000).

## POST /sessions/{session_id}/estimate

- [ ] `multipart/form-data`: `transcript` (min 20), los 3 enums como `Form`, `attachments` lista opcional de `UploadFile`.
- [ ] Sesión inexistente → 404. Input guardrail sobre el texto enriquecido → 400. Proveedor → 502.
- [ ] Caches apagadas. `cached=false`.
- [ ] No persistir en Postgres.
- [ ] Response model propio (corte 3 le añade `project_metadata`; aquí puede ir vacío / default).

**Parada:** curl multipart a una sesión existente devuelve un `EstimationResult` válido. Un PDF cambia el texto que entra al prompt (logs). Entre turnos aún no hay memoria.

---

# Corte 3 — project_metadata en el system prompt + extractor

Los hechos del proyecto viven fuera del array `messages` y se reinyectan cada turno.

## Templates y loader

- [ ] Bloque `<project_metadata>` en `system.j2` de v1 y v2. Si está vacío, el bloque lo dice (primer turno).
- [ ] `render_estimation_prompt` (one-shot) pasa metadata vacía. Mismo `StrictUndefined`.
- [ ] Render conversacional: transcript enriquecido + enums + metadata actual.

## Extractor

- [ ] Segunda llamada LLM tras la respuesta del estimador. Instructor → `ProjectMetadata` parcial. Modelo barato (`METADATA_EXTRACTOR_MODEL`, default `gpt-4o-mini`).
- [ ] Fail-open: si falla, se loguea y se conserva lo anterior.
- [ ] Merge con el previo (escalares / unión de techs).
- [ ] El estimate conversacional incluye `project_metadata` en su response model. Streamlit no adivina nada.

**Parada:** segundo turno sin repetir el nombre del proyecto. La respuesta ya trae metadata no vacía.

---

# Corte 4 — Ventana deslizante + wrapper con messages

El LLM recibe historial recortado, no un one-shot disfrazado.

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
- [ ] Conversational (nueva): al cargar, `POST /sessions` y `session_id` en `st.session_state`. Transcript + `st.file_uploader` múltiple (PDF/DOCX) + los 3 enums. Submit → multipart al estimate de sesión. Pintar `result` como hoy. Guardar `project_metadata` de la respuesta en `session_state` y mostrarla en sidebar o expander (más el `session_id`).
- [ ] Recent: no se toca.
- [ ] “Nueva conversación”: otro `POST /sessions`, reset de transcript / ficheros / último result / metadata pintada.
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

Huecos y contexto de la sesión de planificación. **No son decisiones.** Una implementación limpia tiene que resolverlos o preguntar. No convertir esto en “el plan dice X” sin pasar por el usuario.

## Lo que una sesión limpia tendría que decidir

**Dónde vive cada pieza.** El enunciado solo nombra `src/sessions.py`. No dice: router nuevo vs meterlo en `estimations.py`; extractor PDF/Word en el mismo archivo vs `attachments.py` / `services/`; store como clase vs `dict` a pelo; orquestación conversacional (`estimate_conversational` o el nombre que sea) en `llm_service.py` vs otro sitio. Hoy one-shot vive en `estimate()` + `routers/estimations.py` + `dependencies.py`. Seguir ese estilo es razonable, no está escrito.

**`prompt_version` del path conversacional.** El bloque `<project_metadata>` va en v1 y v2. No está dicho cuál es el default del estimate de sesión ni si admite `?prompt_version=`. El one-shot default es `v1`. Lidr usó v2 como prompt conversacional; **nuestro v2 ya es otro tono**, no un prompt “de sesión”. No copiar ese switch sin mirar.

**Contrato fino del estimate conversacional.** El plan dice “response model propio” con `project_metadata`. No nombra la clase. Lo no escrito, que yo daría por hecho y no debo: mismos `result`, `prompt_version`, `cached` que `EstimationResponse`. Tampoco hay max de `transcript` (Lidr: 80_000; nuestro `description` one-shot: 2000 — no reutilizar ese tope). Tipo de Word: ¿solo `.docx`? ¿también `.doc`? ¿detección por extensión o por `content-type`? Fichero sin `filename`: ¿saltar?

**Settings.** `MAX_CONVERSATION_TURNS=6` está en el enunciado. `MAX_ATTACHMENT_CHARS=60000` y el nombre `METADATA_EXTRACTOR_MODEL` (default `gpt-4o-mini`) los propuse yo; no están confirmados. Truncar vs 413 sí está decidido (truncar).

**Prompt del extractor.** Segunda llamada + Instructor + fail-open sí. No: ¿templates `prompts/metadata_extraction/v1/` o un string en código? ¿contexto = transcript + `EstimationResult` + metadata previa? Lidr hace eso último; no es obligación.

**Streamlit “al cargar”.** Cada clic rerunea el script. `POST /sessions` en cada rerun quema sesiones. Lo no escrito: crear solo si no hay `session_id` en `st.session_state`. ¿Al cargar la app o solo al entrar en la pestaña Conversational? Si el usuario solo usa New, crear sesión es ruido. Nombre de la pestaña: el plan dice “Conversational (nueva)”, no el label final.

**Corte 2 vs 3–4.** El corte 2 “ya llama al pipeline” pero historial/metadata entran después. ¿El endpoint nuevo one-shotea con `complete_structured` y luego se sustituye por `messages[]` + extractor? Hay que decidir el puente al implementar; el plan no lo nombra.

**HTTP menor.** `POST /sessions` → 201 en el plan (el enunciado no exige 201). 404/415/422/400/502 sí están. No hay `DELETE /sessions`: el botón solo pide otro POST.

## Contexto de esta sesión (para no redescubrirlo)

**Repos.** Alumno: `ai-engineering` rama `pre-session-05`, app en `estimador-cag/`. Referencia: `ai-engineering-lidr` en `session_5` (`4a4de0d exercise session 5`). No existe `solutions/session-05`. `session_05_live` mete resumen, tiers y Actor-Critic: fuera. El checkout Lidr `session_4` está más atrás que nosotros (ellos texto libre; nosotros ya tenemos Instructor, guardrails, caches, Postgres).

**Estado actual nuestro (evidencia de código, 2026-10-04).** `POST /api/v1/estimate` JSON → `{ result, prompt_version, cached }`. Wrapper solo `system` + un `user`. `history.py` = log Postgres, no memoria. Templates sin `<project_metadata>`. Streamlit = New + Recent. Sin `pypdf` / `python-docx` en `pyproject.toml`. `python-multipart` solo transitiva en `uv.lock`. Tenemos `prompt_boundary`; Lidr `session_5` no.

**Cómo Lidr enseña la metadata (y por qué no lo copiamos).** Estimate FastAPI **no** devuelve metadata. Rails, tras cada turno, hace `GET /sessions/{id}` y guarda una foto en su tabla `chat_sessions.latest_metadata` para sobrevivir al F5. Streamlit de Lidr **no** se adaptó. Elegimos B: el estimate conversacional trae `project_metadata`; Streamlit lo guarda en `session_state`. Sin GET. `/estimate` no se toca (campo nuevo solo en el model del path de sesión).

**Historial assistant.** Confirmado: `result.model_dump_json()`, no el `summary`. El siguiente turno ve números y fases.

**Lidr extras que no arrastramos.** Paquete `sessions/` + `EstimationService` clase. Espejo Postgres en Rails. `GET /sessions`. Persistencia de cada result conversacional en Rails. Caches off en conversacional **sí** lo hacemos (misma razón: mismo transcript, distinta sesión, no es la misma llamada).

**Q3 en una frase.** El extractor escribe en RAM de FastAPI. El cliente no lo ve a menos que se lo mandemos. A = GET. B = va en la respuesta del estimate. A+B = las dos. Cerrado: B.

## Lo que no hay que reabrir

Tests (paso 7): no. Camino A: no. Rails: no. Persistencia de turnos/sesiones: no. GET de sesión: no. Encender caches en conversacional: no. Fusionar `sessions.py` con `history.py`: no. Romper `complete_structured` one-shot: no.
