# CAG Stress Test — Draft reading (not the deliverable)

Source: `evals/stress/results.csv` (566 rows: **548 ok + 18 errors**).
Scratch copy so you can write `REPORT.md` yourself.

**Run parameters**

| Setting | Value |
|---------|--------|
| Model | `gpt-4o-mini` |
| Planned | growing, pivot, contradiction × {0,5,20,50,100} KB × 3 repeats × 20 turns = 900 |
| Actually measured | `growing` 300/300; `pivot` 248/300; `contradiction` 0/300 |
| Errors | 18 × `502 Bad Gateway` (API died mid-`pivot` 100 KB). Runner aborted each session and kept going. |
| OpenAI dashboard | **$3.43** (CSV `cost_usd` sums to $2.53 — estimate-call only; extractor + summarizer are extra) |
| Latency / cost budgets | 8000 ms / $0.02 per turn |
| Cache | 100% `none` (0% exact, 0% semantic) |
| `turn_index` | plateaus at 7. Curves use **sequential N** (row order in the session). |

`attachments_total_chars`: 0 → 0; 5 KB → 5454; 20 KB → 20731; 50 KB → 51285; 100 KB → **60000** (cap `MAX_ATTACHMENT_CHARS`). The 100 KB column is the truncated regime.

---

## 1. Summary table

P50/P95 of `latency_ms`. Total $ = sum of the cell. Drift = turn-1 name still in `GET /sessions/{id}` metadata.

| Scenario | KB | n | P50 ms | P95 ms | Total $ | Exact % | Semantic % | Drift % | Lat budget % |
|----------|---:|--:|-------:|-------:|--------:|--------:|-----------:|--------:|-------------:|
| growing | 0 | 60 | 4915 | 6863 | 0.049 | 0 | 0 | 100 | 95.0 |
| growing | 5 | 60 | 6654 | 16791 | 0.102 | 0 | 0 | 100 | 61.7 |
| growing | 20 | 60 | 9419 | 21710 | 0.245 | 0 | 0 | 100 | 38.3 |
| growing | 50 | 60 | 8799 | 17398 | 0.531 | 0 | 0 | 100 | 41.7 |
| growing | 100 | 60 | 9307 | 22316 | 0.612 | 0 | 0 | 100 | 30.0 |
| pivot | 0 | 60 | 3894 | 5020 | 0.048 | 0 | 0 | 100 | 100.0 |
| pivot | 5 | 60 | 4402 | 11160 | 0.101 | 0 | 0 | 100 | 86.7 |
| pivot | 20 | 60 | 4912 | 9612 | 0.244 | 0 | 0 | 100 | 93.3 |
| pivot | 50 | 60 | 7572 | 16975 | 0.531 | 0 | 0 | 100 | 56.7 |
| pivot | 100 | 8 | 8999 | 14419 | 0.061 | 0 | 0 | 100 | 37.5 |
| contradiction | all | 0 | — | — | — | — | — | — | — |

`pivot` 100 KB: one session, 8 turns, then 502. Do not treat that P95 as stable. `contradiction` (`Atlas`) never produced a turn.

---

## 2. Three curves (as tables)

### 2a. Latency vs `tokens_in` (548 ok rows)

| `tokens_in` bucket | Median latency (ms) | P95 ms | n |
|--------------------|--------------------:|-------:|--:|
| 0–999 | — | — | 0 |
| 1000–2999 | 4246 | 6046 | 18 |
| 3000–6999 | 4339 | 7065 | 129 |
| 7000–14999 | 5372 | 15627 | 120 |
| 15000+ | 8182 | 19245 | 281 |

Past ~7 k tokens the median is still near the 8 s budget; P95 is already double. Past 15 k (every 20/50/100 KB turn after the first few) the median itself **misses** the SLA.

### 2b. Cumulative $ vs sequential N (size = 0; mean of 3 repeats)

| Turn N | growing $ | pivot $ | contradiction $ |
|-------:|----------:|--------:|----------------:|
| 1 | 0.000689 | 0.000490 | — |
| 5 | 0.003176 | 0.003000 | — |
| 10 | 0.007245 | 0.007423 | — |
| 15 | 0.011670 | 0.011652 | — |
| 20 | 0.016448 | 0.016068 | — |

Same shape, no PDF: a 20-turn session is **~$0.016**. Turn 20 is only **×1.4** (growing) / **×1.9** (pivot) the first turn.

With PDFs, growing T1 → T20 mean cost: 5 KB **×3.1**; 20 KB **×4.5**; 50 KB **×5.6**; 100 KB **×5.8** ($0.0021 → $0.0120). Still under the $0.02/turn budget. **0 cost-budget fails in 548 turns.**

### 2c. MemoryDrift vs sequential N (size = 0; `Nimbus` + `Helios`)

| Turn N | Drift pass rate (%) | n |
|-------:|--------------------:|--:|
| 2 | 100.0 | 6 |
| 5 | 100.0 | 6 |
| 10 | 100.0 | 6 |
| 15 | 100.0 | 6 |
| 20 | 100.0 | 6 |

Same 100% on every measured cell with a PDF. `anchors_count` was **0 on all 548 ok rows**. The name lives in `metadata.project_name`, not in the window.

---

## 3. Reading: where the CAG starts to break

**Paragraph 1 — the dominant failure mode**

This CAG does not drop the project name. `Nimbus` and `Helios` are still in metadata at turn 20 whenever we have a full session (100% MemoryDrift). It also never promotes that first turn to an anchor. What breaks is the **latency contract**, and it breaks as soon as we re-inject a PDF. Size 0 stays inside 8 s: growing P95 6.9 s (95% pass), pivot P95 5.0 s (100% pass). At 5 KB, growing P95 is already **16.8 s** (62% pass). At 20 KB and above, growing fails the budget on **58–70%** of turns; P50 itself sits at 8.8–9.4 s. Tokens tell the same story: 0 KB grows 1.8× by turn 20 (2889 → 5182); 100 KB grows **6.2×** (12692 → 78522) because 60 k extracted chars ride every POST. Cost is loud in the CSV ($0.05 per size-0 cell vs $0.61 per 100 KB cell) and quiet against the $0.02/turn budget — the SLA we miss is time, not dollars.

**Paragraph 2 — what this implies for the RAG decision**

The case for RAG is the attachment, not the 20-turn script. A size-0 session costs ~$0.016 and keeps the name; the six-turn window plus summarizer (N=7 onward, `messages_in_window` stuck at 12) does not blow the 8 s budget. The same session with a 20 KB brief ends at ~30 k `tokens_in` and a growing P95 of **22 s**. Retrieving ≤2 k tokens of that brief per turn would sit in the 3–7 k bucket (median ~4.3 s, P95 ~7 s) — the last bucket that still looks like size 0. We did **not** measure whether a stack pivot or a budget contradiction survives in metadata (`contradiction` is empty; `Flutter` was never scored, only `Helios`). So the live-session claim is: CAG is fine for short chat with no file; it is already the wrong architecture the moment the brief is ≥5 KB and must be resent every turn.

The run itself also died: after ~140 min of summed wall-clock the API returned **502** on `pivot` 100 KB and every `contradiction` cell. That is an ops failure, not a memory failure — but it is what a long CAG session with fat prompts looks like from the client.

---

## 4. Four claims (from this CSV)

1. My CAG starts degrading between turns **6 and 7** (window full, summarizer on) **and on turn 1** when a ≥5 KB PDF is attached, because **latency** misses 8 s while recall of the name stays 100%.
2. Cost per turn grows with **O(attachment)** more than O(history): size 0 is ×1.4–1.9 by turn 20; 100 KB is **×5.8**, because each turn re-injects the extracted text (capped at 60 k chars).
3. The dominant latency bottleneck is **attachment tokens in the estimate call** (15 k+ tokens → median 8.2 s, P95 19 s). Wall-clock is worse still (size 0 wall P50 already 13 s) because extractor + summarizer are extra LLM calls not in `latency_ms`.
4. To cut context by 50% without losing *this* recall, I would stop **re-sending the full PDF every turn** first. The name already survives in `ProjectMetadata`; the 100 KB cell is ~12× the size-0 cell in total $ and ~3× in P95 latency.

---

## 5. Caveats

- **`contradiction` is missing.** No reading on “30 k vs 80 k budget”. Do not invent one.
- **`pivot` 100 KB is 8 turns.** Flutter/React coexistence was not measured; we only tracked `Helios` in metadata.
- MemoryDrift 100% ≠ “the summary kept the first brief”. It means the extractor kept `project_name`.
- `turn_index` cannot plot 8–20. Use row order.
- Observation `$` undercounts OpenAI ($2.53 vs $3.43 dashboard).
- 502s are in the CSV as error rows with empty telemetry. They count toward 566, not toward P50.
