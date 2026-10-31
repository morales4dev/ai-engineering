# Sesión 8 live — barrido de `ef_search`

Números de **este** stack (`sweep_ef_search_s08.py` sobre el corpus engordado). No son los de Lidr.

Referencia sin índice (seq scan forzado, recall = 1.0): **277.4 ms**.

| ef_search | avg_latency_ms | avg_recall | recommendation (script) |
|---|---|---|---|
| 10 | 3.73 | 0.880 | fast / low quality |
| 20 | 4.78 | 0.880 | fast / low quality |
| 40 | 2.56 | 0.960 | good (pgvector default) |
| 80 | 2.79 | 0.960 | good |
| 120 | 257.49 | 1.000 | ★ recommended |
| 200 | 259.78 | 1.000 | diminishing returns |

10–80 viven en 2.5–5 ms. 120 y 200 saltan a ~258 ms: casi el seq scan (277 ms). El último 0.04 de recall cuesta ~100× de latencia; el índice deja de servir.

El script marca ★ en 120 porque es el primer valor con recall ≥ 0.99. Esa regla no mira lo que se paga.

**Valor adoptado: `ef_search = 40`.**

- Frente a 10/20: recall 0.88 → 0.96. Latencia sigue en pocos milisegundos.
- Frente a 80: mismo recall 0.96, 80 no aporta nada y no es más rápido.
- Frente a 120/200: 1.00 de recall a precio de no tener índice. No merece la pena.

40 es el default de pgvector y, en esta tabla, el punto en el que el recall ya es alto y la latencia sigue siendo la del HNSW.
