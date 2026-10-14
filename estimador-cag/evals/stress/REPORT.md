# CAG Stress Test — Report

Live run against `gpt-4o-mini` (OpenAI only). CSV: 851 rows (848 ok + 3 errors).
`contradiction` was re-run after a Docker DNS outage (`Temporary failure in name resolution` → 502). Those 502s are **not** a CAG failure.

**Run parameters**

| Setting | Value |
|---------|--------|
| Model | `gpt-4o-mini` (`PRIMARY_MODEL`) |
| Scenarios | growing, pivot, contradiction |
| Attachment sizes (KB) | 0, 5, 20, 50, 100 |
| Repeats per cell | 3 (except `pivot` × 100 KB: 8 ok turns, then DNS 502) |
| Latency budget | 8000 ms |
| Cost budget per turn | $0.02 |
| Turns observed | 848 ok (floor ≥50). `turn_index` plateaus at 7 after the window fills; curves use **sequential N** (row order in the session). |
| Request-time sum (`wall_clock_ms`) | ~198 min. First pass ~5 h until DNS died; `contradiction` was a second run. |
| Exact / semantic cache hit rate | **0% / 0%** (`cache_hit_kind=none` on every ok row). Measurement, not a bug: conversational path has caches off. |
| OpenAI dashboard (first pass) | $3.43. CSV `cost_usd` is the estimate call only (extractor + summarizer extra). |

100 KB cells: `attachments_total_chars=60000` (`MAX_ATTACHMENT_CHARS`). Truncated regime, not literal 100 KB.

`pivot` × 100 KB is the only incomplete cell. The 100 KB attachment curve is already complete on `growing` and `contradiction`. `pivot`'s unique story (name `Helios`, stack change at turn 5) is fully measured at 0 / 5 / 20 / 50 KB. No re-run.

---

## 1. Summary table

One row per `(scenario, KB)`. P50/P95 = `latency_ms`. Total $ = sum of the cell. Drift = turn-1 name still in `GET /sessions/{id}` metadata (`Nimbus` / `Helios` / `Atlas`). Cache hit rates are 0% on every row (omitted as a column).

| Scenario | KB | n | P50 ms | P95 ms | Total $ | Drift pass % | Lat budget % |
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

Cost budget: **0 fails / 848**. Scenario totals (ok rows): growing **$1.54**, contradiction **$1.53**, pivot **$0.99** (100 KB missing). Mean MemoryDrift across all scored turns: **100%** (805/805). `anchors_count=0` on every ok row.

---

## 2. Three curves (as tables)

### 2a. Latency vs `tokens_in` (848 ok rows)

| `tokens_in` bucket | Median latency (ms) | P95 ms | n |
|--------------------|--------------------:|-------:|--:|
| 0–999 | — | — | 0 |
| 1000–2999 | 3585 | 5223 | 27 |
| 3000–6999 | 3995 | 6760 | 192 |
| 7000–14999 | 4604 | 14889 | 183 |
| 15000+ | 7156 | 17911 | 446 |

### 2b. Cumulative $ vs sequential N (size = 0; mean of 3 repeats)

| Turn N | growing $ | pivot $ | contradiction $ |
|-------:|----------:|--------:|----------------:|
| 1 | 0.000689 | 0.000490 | 0.000488 |
| 5 | 0.003176 | 0.003000 | 0.002967 |
| 10 | 0.007245 | 0.007423 | 0.007066 |
| 15 | 0.011670 | 0.011652 | 0.011350 |
| 20 | 0.016448 | 0.016068 | 0.015655 |

A 20-turn session with no PDF costs **~$0.016**. Turn 20 vs turn 1: growing **×1.4**, pivot **×1.9**, contradiction **×1.8**.

With PDFs (growing, T1 → T20 mean): 5 KB **×3.1** tokens **×3.8**; 20 KB **×4.5** / **×5.3**; 50 KB **×5.6** / **×6.1**; 100 KB **×5.8** / **×6.2** (12.7 k → 78.5 k `tokens_in`). Same shape on contradiction 100 KB (×5.6 cost, ×6.2 tokens).

### 2c. MemoryDrift vs sequential N (size = 0; three scenarios, 3 repeats)

| Turn N | Drift pass rate (%) | n |
|-------:|--------------------:|--:|
| 2 | 100.0 | 9 |
| 5 | 100.0 | 9 |
| 10 | 100.0 | 9 |
| 15 | 100.0 | 9 |
| 20 | 100.0 | 9 |

100% on every measured cell with a PDF as well. The runner only checks `metadata.project_name`. That is not “the summary kept the first brief”.

---

## 3. Reading: where the CAG starts to break

**Paragraph 1 — the dominant failure mode**

This CAG does not forget the project name. `Nimbus`, `Helios` and `Atlas` are still in `metadata.project_name` at sequential turn 20 whenever the session finished (100% MemoryDrift, 805/805 scored turns). It also never promotes that first turn to an anchor (`anchors_count=0` on all 848 ok rows). What breaks is the **8 s latency budget**, and it breaks as soon as the same PDF is re-injected every turn. Size 0 stays inside the SLA: growing P95 6.9 s (95% pass), pivot / contradiction P95 ~5.0 s (100% pass). At 5 KB, growing P95 is already **16.8 s** (62% pass). At 20 KB+ growing fails the budget on **58–70%** of turns; P50 itself sits at 8.8–9.4 s. Contradiction on a later, quieter run is kinder (100 KB P95 11.2 s, 68% pass) but the slope is the same. Cost never misses $0.02/turn — a size-0 session is **$0.016**; a 100 KB session is **~$0.20** (growing cell $0.612 / 3 repeats). Dollars scale; the contract we miss is time.

**Paragraph 2 — what this implies for the RAG decision**

The case for RAG is the attachment, not the 20-turn script. Size 0 grows tokens only 1.8–2.4× by turn 20; 100 KB grows **×6.2** because 60 k extracted chars ride every POST. Past 15 k `tokens_in` (446 of 848 rows) median latency is 7.2 s and P95 is **18 s**. If RAG retrieved ≤2 k tokens of that brief per turn, those rows would sit in the 3–7 k bucket (median 4.0 s, P95 6.8 s) — the last bucket that still looks like size 0. We tracked only the turn-1 name, so this run does **not** prove that a Flutter pivot or an 80 k budget overwrite survived in the summary. It does prove that CAG is fine for short chat with no file, and already the wrong architecture the moment a ≥5 KB brief must be resent every turn. The 502 hole on `pivot` 100 KB was Docker DNS, not the model; we did not need that cell to see the 100 KB curve.

---

## 4. Four claims to defend

1. My CAG starts degrading between turns **6 and 7** (window full, summarizer on) **and on turn 1** when a ≥5 KB PDF is attached, because **latency** misses 8 s while recall of the name stays 100%.
2. Cost per turn grows with **O(attachment)** more than O(history): size 0 is ×1.4–1.9 by turn 20; 100 KB is **×5.8**, because each turn re-injects the extracted text (capped at 60 k chars).
3. The dominant latency bottleneck is **attachment tokens in the estimate call** (15 k+ tokens → median 7.2 s, P95 18 s). Wall-clock is worse (size 0 growing wall P50 already 13 s) because extractor + summarizer are extra LLM calls not in `latency_ms`.
4. To cut context by 50% without losing *this* recall, I would stop **re-sending the full PDF every turn** first. The name already survives in `ProjectMetadata`; the 100 KB growing cell is ~12× the size-0 cell in total $ and ~3× in P95 latency.

---

## 5. Reproducibility

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

If a cell 502s on DNS, re-run only the missing `--scenarios` into a second CSV and concatenate (do not overwrite). Prefer Compose `dns: [8.8.8.8, 1.1.1.1]` on long runs.

`results.csv` is gitignored. This `REPORT.md` is the directo artefact.
