Cuatro cortes. Tras cada uno se para a revisar. El camino del enunciado (formulario HTTP → `POST /estimate`) no queda mudo entre cortes. Las puertas que aún mandan `transcription` se recuperan en el último.

Fuera de este plan: tests de template, `reference_projects`, log/hash del render, JSON forzado, guardrails, cache semántico.

---

# Templates y loader

Nadie los llama todavía. Chat, `POST /estimate` y SSE siguen con el contrato de la sesión 03.

## Templates Jinja2 v1

- [x] `prompts/estimation/v1/system.j2` — rol, `{% if %}` por `output_format` y `detail_level`, `{% include %}` de ejemplos.
- [x] `prompts/estimation/v1/user.j2` — envuelve `description` (`<project_description>` o heading markdown).
- [x] `prompts/estimation/v1/examples.j2` — dos o tres few-shot inventados, no copiados del enunciado.

## Loader

- [x] `render_estimation_prompt(request, version="v1") -> (system, user)`.
- [x] Jinja2 con `StrictUndefined`, `trim_blocks`, `lstrip_blocks`. Cambiar de versión no toca el resto del código.

---

# Contrato, endpoint y formulario

Los tres aterrizan juntos. Es el cambio de contrato: el servicio deja de aceptar `transcription` en `POST /estimate` y el cliente HTTP deja de ser un chat.

## Schemas

- [ ] Entrada: `description` (20–2000), `project_type`, `detail_level`, `output_format` (enums; en JSON los strings `mobile_app`, no `MOBILE_APP`).
- [ ] Salida: `{ text, prompt_version }`. Texto libre.

## POST /estimate

- [ ] Body del schema nuevo. Llama al loader, manda `role: system` y `role: user` por separado al wrapper de la sesión 03.
- [ ] Responde `prompt_version="v1"`. Modelo por defecto el que ya tengamos (`gpt-4o-mini` / Haiku).

## Formulario Streamlit HTTP

- [ ] En `streamlit_app.py`, `st.form` en lugar del chat. El submit arma el request y hace `POST /estimate`. Se pinta el `text`.

Al parar aquí el formulario HTTP funciona. Quedan descolgadas las puertas que aún hablan `transcription` (siguiente corte no; el último).

---

# Segunda versión del prompt

Aditivo. Si no mandas query, el formulario de arriba sigue igual.

## v2 y query param

- [ ] `prompts/estimation/v2/` con una variación deliberada (tono o ejemplos).
- [ ] `POST /estimate?prompt_version=v2`. Default `v1`.

---

# Puertas del contrato viejo

Mismo schema y mismo loader. No se mantienen dos contratos.

## POST /estimate/stream

- [ ] Body alineado al `EstimationRequest` nuevo. Loader → `complete_stream`.

## HTML SSE

- [ ] El demo estático manda `description` + enums (o defaults) en lugar de `{ transcription }`.

## Streamlit in-process

- [ ] Mismo formulario que el HTTP. Estimación en bloque: `estimate(request)`.
- [ ] Si se quiere seguir streameando tokens: `complete_stream` + loader, no `EstimationTokenStream` / CAG de la sesión 03.
