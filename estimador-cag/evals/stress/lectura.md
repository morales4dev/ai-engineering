# Column glossary

One row per column. Name, then what it means. No numbers here — those live in `results.csv` and `REPORT.md`.

---

## results.csv

One row = one turn of one session (or a 502 that aborted that session).

- **scenario** — Which scripted conversation this turn belongs to: `growing`, `pivot`, or `contradiction`. Same 20-turn story every time; only the PDF size and the repeat change.
- **attachment_size_kb** — Planned PDF size for that cell (`0`, `5`, `20`, `50`, `100`). A label, not the bytes on the wire. `100` is truncated to 60 000 extracted characters.
- **repeat** — Which of the three identical replays this session is (`1`–`3`). Same script, same size, fresh session.
- **turn_index** — The server’s conversation-turn counter after this estimate. It rises with the window and then sits at `7` once the cap is full. For “turn 15 of 20”, use row order in the session, not this field.
- **session_id** — Id of the chat this turn was posted to. All 20 turns of one replay share one id.
- **enriched_transcript_chars** — Character count of the user text after the runner stitches in the attachment extract. How fat the prompt *input side* was, in characters, not tokens.
- **attachments_total_chars** — Characters taken from the PDF(s) on this request. `0` with no file; `60000` on the `100` KB cells because of `MAX_ATTACHMENT_CHARS`.
- **messages_in_window** — How many messages still sit in the live sliding window after this turn. After the cap, this stops growing (pairs of user + assistant).
- **anchors_count** — How many messages the compressor promoted to verbatim anchors. In this run it stayed `0`: the first turn was never pinned.
- **summary_chars** — Length of the cumulative summary, if the window has already overflowed. `0` until compression starts; then a growing blob, not the summary text itself.
- **tokens_in** — Prompt tokens billed on the estimate call only. Extractor and summarizer are extra LLM calls and are not in this number.
- **tokens_out** — Completion tokens billed on that same estimate call.
- **cost_usd** — Dollar estimate for that estimate call (`MODEL_COSTS` × those tokens). Not the OpenAI dashboard total; not extractor or summarizer.
- **latency_ms** — Server-side time for the estimate call, in milliseconds. This is what the 8 s budget judges.
- **wall_clock_ms** — Client-side time for the whole turn: estimate + `GET /sessions/{id}` + any extra work. Usually larger than `latency_ms`.
- **cache_hit_kind** — Whether a cache answered this turn: `none`, `exact`, or `semantic`. Conversational path has caches off, so this run is `none` on every ok row.
- **last_resolved_tier** — Complexity tier the session resolver picked after this turn (or empty if none). Context for the estimate; not a pass/fail.
- **latency_budget_passed** — `True` if `latency_ms` ≤ 8000. The time SLA for that single turn.
- **cost_budget_passed** — `True` if `cost_usd` ≤ 0.02. The money SLA for that single turn, not the session total.
- **memory_drift_passed** — `True` / `False` if the turn-1 project name (`Nimbus` / `Helios` / `Atlas`) is still in `metadata.project_name`. Empty on turn 1 (the name was just born) and on error rows. Does not score Flutter or the 80k budget.
- **tracked_fact** — The string MemoryDrift is looking for. Always the turn-1 name of that scenario.
- **error** — Empty on success. On failure, a short exception (in this run: HTTP 502 after Docker DNS). The rest of that session is not continued.

---

## 1. Summary table

One row per `(scenario, KB)` cell, across the three repeats.

- **Scenario** — Which of the three scripts this cell is. Same meaning as `scenario` in the CSV.
- **KB** — Planned attachment size for the cell. Same meaning as `attachment_size_kb`.
- **n** — How many ok turns landed in the cell. A full cell is 60 (20 turns × 3 repeats). `pivot` × 100 KB is 8 because DNS cut the run.
- **P50 ms** — Median `latency_ms` in the cell. Half the turns were faster than this.
- **P95 ms** — 95th-percentile `latency_ms` in the cell. The slow tail; this is what an 8 s SLA feels like to the unlucky user.
- **Total $** — Sum of `cost_usd` over the ok turns in the cell. Three full sessions if `n` is 60; not a per-turn average.
- **Drift pass %** — Share of scored turns where MemoryDrift passed. Scored turns skip turn 1 and errors. 100% means the project name survived; not that Flutter or 80k did.
- **Lat budget %** — Share of ok turns with `latency_budget_passed`. 100% means every turn in the cell stayed under 8 s.

---

## 2a. Latency vs `tokens_in`

```
  Es la tabla que responde: cuando el prompt tiene tantos tokens, ¿cuánto tarda el estimate?

  • Latency = latency_ms de esa llamada (lo que juzga el presupuesto de 8 s).
  • vs tokens_in = ordenado por cuántos tokens de entrada llevó esa llamada, no por escenario, ni por KB, ni por turno.

  No hay una fila por historia. Hay cubos (0–999, 1000–2999, 3000–6999, …). Todas las filas ok del CSV se tiran juntas; cada turno cae en un cubo según sus tokens_in.

  En cada cubo: mediana, P95 y n (cuántos turnos cayeron ahí). El cubo 15 000+ es el gordo porque los PDF grandes hinchan el prompt.

  Lectura práctica: a más tokens de entrada, más lento. Por encima de 15 k la mediana ya es ~7.2 s y el P95 ~18 s — ahí se rompe el SLA de 8 s.
```

Ok rows only, pooled across scenarios, sizes, and repeats. Each row is a token bucket, not a cell.

- **`tokens_in` bucket** — Range of prompt tokens on the estimate call. A bin so you can read latency as the prompt gets fatter.
- **Median latency (ms)** — Median `latency_ms` of rows that fell in that bin. Empty (`—`) if the bin has no rows.
- **P95 ms** — 95th-percentile `latency_ms` in that same bin. The slow tail at that prompt size.
- **n** — How many ok turns landed in the bin. The 15 000+ bin is most of the run because large PDFs dominate.


## 2b. Cumulative $ vs sequential N

```
  Es la tabla que responde: sin PDF, ¿cuánto dinero llevamos gastado al llegar al turno N?

  • Cumulative $ = dólares acumulados. No el coste de ese turno, sino la suma desde el turno 1 hasta el N (cost_usd + cost_usd + …).
  • vs sequential N = dibujado contra el número de turno real (1, 5, 10, 15, 20: el orden en el chat). No contra turn_index, que se queda en 7.

  Cada fila es un momento de la sesión. Cada columna (growing $, pivot $, contradiction $) es esa historia, size 0, media de las 3 repeticiones.

  Ejemplo: en growing, turno 20, pone 0.016448. Eso no es “el turno 20 costó 1.6 céntimos”. Es “después de 20 turnos sin PDF, esa sesión Nimbus llevaba unos 1.6 céntimos en total”.

  Sirve para ver si el chat largo, solo por historial, se encarece. Spoiler de esa tabla: casi no. Un size-0 de 20 turnos son ~$0.016. El salto gordo de coste no está aquí; está cuando hay PDF.
```


Size 0 only (no PDF). Each value is the mean, over the three repeats, of the running sum of `cost_usd` from turn 1 through turn N.

- **Turn N** — Sequential turn in the session (1…20, row order). Not `turn_index`, which plateaus at 7.
- **growing $** — Mean dollars spent so far in the `growing` script, no attachment, after N turns.
- **pivot $** — The same running total for the `pivot` script.
- **contradiction $** — The same running total for the `contradiction` script.

---

## 2c. MemoryDrift vs sequential N

```
  Es la tabla que responde: sin PDF, en el turno N, ¿sigue el nombre del proyecto?

  • MemoryDrift = el sí/no de memoria: ¿Nimbus / Helios / Atlas sigue en metadata.project_name?
  • vs sequential N = lo mismo de antes: el turno real del chat (2, 5, 10, 15, 20), no el turn_index que se queda en 7. El turno 1 no aparece: ahí el nombre acaba de
    nacer y no se puntúa.

  Cada fila es un momento. Drift pass rate (%) es el porcentaje de “sí” en ese N. n es cuántos turnos entran en esa media: 9 = 3 historias × 3 repeticiones, size 0.

  En tu run todas las filas son 100.0. Lectura: al turno 20, sin adjunto, las 9 sesiones seguían teniendo el nombre. No dice nada de Flutter ni de los 80k.
```

Size 0 only, all three scripts, three repeats. Turn 1 is omitted because the metric is not scored there.

- **Turn N** — Sequential turn in the session (row order), from 2 onward.
- **Drift pass rate (%)** — Share of those turns where the turn-1 name was still in `metadata.project_name`. `n = 9` is 3 scenarios × 3 repeats. Still only the name, not Flutter or 80k.
- **n** — How many scored turns sit in that row. Nine when every size-0 session reached that N.
