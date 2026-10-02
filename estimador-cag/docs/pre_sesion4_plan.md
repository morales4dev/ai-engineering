Cuatro cortes. Tras cada uno se para a revisar. El camino del enunciado (formulario HTTP → `POST /estimate`) no queda mudo entre cortes. Las puertas que aún mandan `transcription` se recuperan en el último.

Fuera de este plan: tests de template, `reference_projects`, log/hash del render, JSON forzado, guardrails, cache semántico.

---

# Templates y loader

El loader ya lo llama `POST /estimate`. SSE e in-process siguen con el contrato de la sesión 03 (`transcription`) hasta el último corte.

## Templates Jinja2 v1

- [x] `prompts/estimation/v1/system.j2` — rol, `{% if %}` por `output_format` y `detail_level`, `{% include %}` de ejemplos.
- [x] `prompts/estimation/v1/user.j2` — envuelve `description` en `<project_description>`.
- [x] `prompts/estimation/v1/examples.j2` — few-shot de la rama `session_4` del repo de referencia (préstamos, meal-prep, assets).

## Loader

- [x] `render_estimation_prompt(request, version="v1") -> (system, user)`.
- [x] Jinja2 con `StrictUndefined`, `trim_blocks`, `lstrip_blocks`. Cambiar de versión no toca el resto del código.

---

# Contrato, endpoint y formulario

Los tres aterrizan juntos. Es el cambio de contrato: el servicio deja de aceptar `transcription` en `POST /estimate` y el cliente HTTP deja de ser un chat.

## Schemas

- [x] Entrada: `description` (20–2000), `project_type`, `detail_level`, `output_format` (enums; en JSON los strings `mobile_app`, no `MOBILE_APP`).
- [x] Salida: `{ text, prompt_version }`. Texto libre.

## POST /estimate

- [x] Body del schema nuevo. Llama al loader, manda `role: system` y `role: user` por separado al wrapper de la sesión 03.
- [x] Responde `prompt_version="v1"`. Modelo por defecto el que ya tengamos (`gpt-4o-mini` / Haiku).

## Formulario Streamlit HTTP

- [x] En `streamlit_app.py`, `st.form` en lugar del chat. El submit arma el request y hace `POST /estimate`. Se pinta el `text`.

Al parar aquí el formulario HTTP funciona. Quedan descolgadas las puertas que aún hablan `transcription` (siguiente corte no; el último).

---

# Segunda versión del prompt

Aditivo. Si no mandas query, el formulario de arriba sigue igual.

## v2 y query param

- [x] `prompts/estimation/v2/` con una variación deliberada (tono o ejemplos).
- [x] `POST /estimate?prompt_version=v2`. Default `v1`.

---

# Puertas del contrato viejo

Mismo schema y mismo loader. No se mantienen dos contratos.

## POST /estimate/stream

- [x] Eliminado (endpoint, `complete_stream`, `StreamEstimationRequest`, `sse-starlette`). En `session_4_live` tampoco está.

## HTML SSE

- [x] Eliminada (`sse_demo.html` + mount `/static`). Lidr también la borra.

## Streamlit in-process

- [x] Eliminado (`streamlit_inprocess.py` + `EstimationTokenStream` / SDKs). Lidr no lo tenía.
