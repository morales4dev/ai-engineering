# CAG Stress Test — Informe

Ejecución en vivo contra `gpt-4o-mini` (solo OpenAI). CSV: 851 filas (848 ok + 3 errores).
`contradiction` se relanzó tras un corte de DNS de Docker (`Temporary failure in name resolution` → 502). Esos 502 **no** son un fallo del CAG.

**Parámetros de la ejecución**

| Ajuste | Valor |
|---------|--------|
| Modelo | `gpt-4o-mini` (`PRIMARY_MODEL`) |
| Escenarios | growing, pivot, contradiction |
| Tamaños de adjunto (KB) | 0, 5, 20, 50, 100 |
| Repeticiones por celda | 3 (excepto `pivot` × 100 KB: 8 turnos ok, luego DNS 502) |
| Presupuesto de latencia | 8000 ms |
| Presupuesto de coste por turno | $0.02 |
| Turnos observados | 848 ok (suelo ≥50). `turn_index` se estanca en 7 cuando se llena la ventana; las curvas usan **N secuencial** (orden de fila en la sesión). |
| Suma de tiempo de petición (`wall_clock_ms`) | ~198 min. Primera pasada ~5 h hasta que murió el DNS; `contradiction` fue una segunda ejecución. |
| Hit rate de caché exacta / semántica | **0% / 0%** (`cache_hit_kind=none` en cada fila ok). Medición, no un bug: el camino conversacional tiene las cachés apagadas. |
| Dashboard de OpenAI (primera pasada) | $3.43. El `cost_usd` del CSV es solo la llamada de estimate (extractor + summarizer van aparte). |

Celdas de 100 KB: `attachments_total_chars=60000` (`MAX_ATTACHMENT_CHARS`). Régimen truncado, no 100 KB literales.

`pivot` × 100 KB es la única celda incompleta. La curva de adjunto de 100 KB ya está completa en `growing` y `contradiction`. La historia única de `pivot` (nombre `Helios`, cambio de stack en el turno 5) está medida por completo en 0 / 5 / 20 / 50 KB. Sin relanzar.

---

## 1. Tabla resumen

Una fila por `(escenario, KB)`. P50/P95 = `latency_ms`. Total $ = suma de la celda. Drift = el nombre del turno 1 sigue en el metadata de `GET /sessions/{id}` (`Nimbus` / `Helios` / `Atlas`). Los hit rates de caché son 0% en todas las filas (omitidos como columna).

| Escenario | KB | n | P50 ms | P95 ms | Total $ | Drift pass % | Lat budget % |
|----------|---:|--:|-------:|-------:|--------:|-------------:|-------------:|
| growing | 0 | 60 | 4915 | 6863 | 0.049 | 100.0 | 95.0 |
| growing | 5 | 60 | 6654 | 16791 | 0.102 | 100.0 | 61.7 |
| growing | 20 | 60 | 9419 | 21710 | 0.245 | 100.0 | 38.3 |
| growing | 50 | 60 | 8799 | 17398 | 0.531 | 100.0 | 41.7 |
| growing | 100 | 60 | 9307 | 22316 | 0.612 | 100.0 | 30.0 |
| pivot | 0 | 60 | 3894 | 5020 | 0.048 | 100.0 | 100.0 |
| pivot | 5 | 60 | 4402 | 11160 | 0.101 | 100.0 | 86.7 |
| pivot | 20 | 60 | 4912 | 9612 | 0.244 | 100.0 | 93.3 |
| pivot | 50 | 60 | 7572 | 16975 | 0.531 | 100.0 | 56.7 |
| pivot | 100 | 8 | 8999 | 14419 | 0.061 | 100.0 | 37.5 |
| contradiction | 0 | 60 | 3319 | 5030 | 0.047 | 100.0 | 100.0 |
| contradiction | 5 | 60 | 3583 | 4660 | 0.100 | 100.0 | 100.0 |
| contradiction | 20 | 60 | 4197 | 8704 | 0.244 | 100.0 | 93.3 |
| contradiction | 50 | 60 | 6134 | 9310 | 0.530 | 100.0 | 85.0 |
| contradiction | 100 | 60 | 7129 | 11240 | 0.613 | 100.0 | 68.3 |

Presupuesto de coste: **0 fails / 848**. Totales por escenario (filas ok): growing **$1.54**, contradiction **$1.53**, pivot **$0.99** (falta el 100 KB). MemoryDrift medio en todos los turnos puntuados: **100%** (805/805). `anchors_count=0` en cada fila ok.

---

## 2. Tres curvas (como tablas)

### 2a. Latencia vs `tokens_in` (848 filas ok)

| Cubo de `tokens_in` | Latencia mediana (ms) | P95 ms | n |
|--------------------|--------------------:|-------:|--:|
| 0–999 | — | — | 0 |
| 1000–2999 | 3585 | 5223 | 27 |
| 3000–6999 | 3995 | 6760 | 192 |
| 7000–14999 | 4604 | 14889 | 183 |
| 15000+ | 7156 | 17911 | 446 |

### 2b. $ acumulado vs N secuencial (size = 0; media de 3 repeticiones)

| Turno N | growing $ | pivot $ | contradiction $ |
|-------:|----------:|--------:|----------------:|
| 1 | 0.000689 | 0.000490 | 0.000488 |
| 5 | 0.003176 | 0.003000 | 0.002967 |
| 10 | 0.007245 | 0.007423 | 0.007066 |
| 15 | 0.011670 | 0.011652 | 0.011350 |
| 20 | 0.016448 | 0.016068 | 0.015655 |

Una sesión de 20 turnos sin PDF cuesta **~$0.016**. Turno 20 vs turno 1: growing **×1.4**, pivot **×1.9**, contradiction **×1.8**.

Con PDFs (growing, T1 → T20 media): 5 KB **×3.1** tokens **×3.8**; 20 KB **×4.5** / **×5.3**; 50 KB **×5.6** / **×6.1**; 100 KB **×5.8** / **×6.2** (12.7 k → 78.5 k `tokens_in`). Misma forma en contradiction 100 KB (×5.6 coste, ×6.2 tokens).

### 2c. MemoryDrift vs N secuencial (size = 0; tres escenarios, 3 repeticiones)

| Turno N | Drift pass rate (%) | n |
|-------:|--------------------:|--:|
| 2 | 100.0 | 9 |
| 5 | 100.0 | 9 |
| 10 | 100.0 | 9 |
| 15 | 100.0 | 9 |
| 20 | 100.0 | 9 |

100% también en cada celda medida con PDF. El runner solo comprueba `metadata.project_name`. Eso no es “el resumen conservó el brief del primer turno”.

---

## 3. Lectura: dónde empieza a romperse el CAG

**Párrafo 1 — el modo de fallo dominante**

Este CAG no olvida el nombre del proyecto. `Nimbus`, `Helios` y `Atlas` siguen en `metadata.project_name` en el turno secuencial 20 siempre que la sesión terminó (MemoryDrift 100%, 805/805 turnos puntuados). Tampoco promociona nunca ese primer turno a ancla (`anchors_count=0` en las 848 filas ok). Lo que se rompe es el **presupuesto de latencia de 8 s**, y se rompe en cuanto el mismo PDF se reinyecta en cada turno. Size 0 se queda dentro del SLA: growing P95 6.9 s (95% pass), pivot / contradiction P95 ~5.0 s (100% pass). A 5 KB, el P95 de growing ya es **16.8 s** (62% pass). A 20 KB+ growing falla el presupuesto en el **58–70%** de los turnos; el propio P50 se sitúa en 8.8–9.4 s. Contradiction, en una ejecución posterior más tranquila, es más amable (100 KB P95 11.2 s, 68% pass) pero la pendiente es la misma. El coste nunca se pasa de $0.02/turno — una sesión size-0 es **$0.016**; una de 100 KB es **~$0.20** (celda growing $0.612 / 3 repeticiones). Los dólares escalan; el contrato que incumplimos es el tiempo.

**Párrafo 2 — qué implica esto para la decisión de RAG**

El caso a favor de RAG es el adjunto, no el guion de 20 turnos. Size 0 crece en tokens solo 1.8–2.4× hacia el turno 20; 100 KB crece **×6.2** porque 60 k caracteres extraídos viajan en cada POST. Por encima de 15 k `tokens_in` (446 de 848 filas) la latencia mediana es 7.2 s y el P95 es **18 s**. Si RAG recuperara ≤2 k tokens de ese brief por turno, esas filas caerían en el cubo 3–7 k (mediana 4.0 s, P95 6.8 s) — el último cubo que todavía parece size 0. Solo rastreamos el nombre del turno 1, así que esta ejecución **no** demuestra que un pivot a Flutter o una sobrescritura de presupuesto 80 k sobrevivieran en el resumen. Sí demuestra que el CAG vale para un chat corto sin archivo, y que ya es la arquitectura equivocada en el momento en que un brief ≥5 KB hay que reenviarlo en cada turno. El agujero de 502 en `pivot` 100 KB fue DNS de Docker, no el modelo; no necesitábamos esa celda para ver la curva de 100 KB.

---

## 4. Cuatro afirmaciones que defender

1. Mi CAG empieza a degradarse entre los turnos **6 y 7** (ventana llena, summarizer encendido) **y en el turno 1** cuando se adjunta un PDF ≥5 KB, porque la **latencia** se pasa de 8 s mientras el recall del nombre se queda en 100%.
2. El coste por turno crece con **O(adjunto)** más que con O(historial): size 0 es ×1.4–1.9 hacia el turno 20; 100 KB es **×5.8**, porque cada turno reinyecta el texto extraído (tope de 60 k caracteres).
3. El cuello de botella dominante de latencia son los **tokens del adjunto en la llamada de estimate** (15 k+ tokens → mediana 7.2 s, P95 18 s). El wall-clock es peor (size 0 growing, wall P50 ya 13 s) porque extractor + summarizer son llamadas LLM extra que no están en `latency_ms`.
4. Para recortar el contexto un 50% sin perder *este* recall, primero dejaría de **reenviar el PDF entero en cada turno**. El nombre ya sobrevive en `ProjectMetadata`; la celda growing de 100 KB es ~12× la de size-0 en $ total y ~3× en latencia P95.

---

## 5. Reproducibilidad

```bash
cd estimador-cag
PYTHONPATH=src:. uv run python -m evals.stress.fixtures.build_pdfs
docker compose up --build -d
curl -sf http://localhost:8000/health

PYTHONPATH=src:. uv run python -m evals.stress.run \
    --http http://localhost:8000 \
    --scenarios growing,pivot,contradiction \
    --attachment-sizes 0,5,20,50,100 \
    --repeats 3 \
    --output evals/stress/results.csv
```

Si una celda da 502 por DNS, relanza solo los `--scenarios` que falten a un segundo CSV y concatena (no sobrescribas). En ejecuciones largas, mejor Compose `dns: [8.8.8.8, 1.1.1.1]`.

`results.csv` está en gitignore. Este `REPORT.md` es el artefacto del directo.
