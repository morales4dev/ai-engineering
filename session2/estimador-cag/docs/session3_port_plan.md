# Session 3 — Port plan (LiDR → ai-engineering)

Traer las features de `ai-engineering-lidr` a `session2/estimador-cag`.
Una feature por tanda. Tras cada una: revisión, y solo entonces la siguiente.

Convención:

- **Main** = este chat (Cursor Grok 4.6). Núcleo y decisiones de adaptación.
- **Subagente + composer-2.5-fast** = piezas mecánicas, contexto aislado, modelo más barato.

El orden de la tabla es el de implementación (dependencias), no el de la lista original.

| # | Feature | Hecho | Quién | Modelo |
|---|---|---|---|---|
| 1 | LiteLLM wrapper | [x] | Main | Cursor Grok 4.6 |
| 2 | Timeout y retries configurables | [x] | Main | Cursor Grok 4.6 |
| 3 | Fallback automático de proveedor | [x] | Main | Cursor Grok 4.6 |
| 4 | Cache exact-match en Redis | [x] | Main | Cursor Grok 4.6 |
| 5 | Coste estimado (`cost_usd`) | [x] | Main | Cursor Grok 4.6 |
| 6 | Endpoint SSE `POST /api/v1/estimate/stream` | [x] | Main | Cursor Grok 4.6 |
| 7 | Streaming consciente de cache | [x] | Main | Cursor Grok 4.6 |
| 8 | Página demo SSE (`/static/sse_demo.html`) | [x] | Subagente | composer-2.5-fast |
| 9 | Streamlit como cliente HTTP/SSE de la API | [x] | Main | Cursor Grok 4.6 |
| 10 | Stack Docker Compose + Redis | [x] | Subagente | composer-2.5-fast |

## Notas por feature

1. **LiteLLM wrapper** — Un solo cliente (`complete`) en lugar de los SDK de OpenAI/Anthropic. Sin fallback ni cache todavía; esos llegan en 3 y 4.
2. **Timeout y retries** — Settings `LLM_TIMEOUT` / `LLM_RETRIES` cableados al wrapper.
3. **Fallback** — Router LiteLLM: `PRIMARY_MODEL` → `FALLBACK_MODEL`. Settings: al menos una API key.
4. **Cache Redis** — Clave SHA-256 del prompt + knobs, TTL, campo `cache_hit`.
5. **`cost_usd`** — Tabla de precios por modelo; suma el coste de preprocessing two-phase.
6. **SSE HTTP** — Endpoint público. El streaming in-process de Streamlit se deja como está hasta el 9.
7. **Streaming + cache** — Hit = un chunk; miss = stream live y luego persistir.
8. **HTML demo** — Página estática servida en `/static`. Copy/paste válido si encaja.
9. **Streamlit HTTP** — La UI pasa a consumir la API. Cuidado de no tirar la sidebar de validación/CAG que ya tienes.
10. **Docker** — Servicio `estimator` + `redis`, healthchecks, `REDIS_URL` de red interna.

## Settings que van apareciendo

`PRIMARY_MODEL`, `FALLBACK_MODEL`, `LLM_TIMEOUT`, `LLM_RETRIES`, `REDIS_URL`, `CACHE_TTL`, `ESTIMATOR_API_BASE_URL`.
Se añaden en el bullet que los necesita, no todos de golpe.
