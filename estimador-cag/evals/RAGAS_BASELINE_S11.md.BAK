# Sesión 11: preparación de la baseline del alumno

## Estado real

**No se ha medido todavía una baseline.** No se han ejecutado servicios,
ingestas ni llamadas al generador o al juez durante la implementación.
No hay números propios que comparar y no se copian las métricas de LIDR.

La [guía manual](../docs/pre_sesion11_plan.md#101-guía-manual-empezar-aquí)
explica el recorrido completo, incluidos fallos, resultados esperados y costes.
Empieza por la preparación de dependencias, no por generación.

## Configuración preparada

- Referencia: instructor `session_11`, commit `3292744`, solo pre-work.
- [Golden de generación](golden_generation_s11.json): copia literal de Q1-Q5
  enriquecidas por LIDR. Consultas iguales a las de
  [recuperación](golden_retrieval.json); Q6-Q8 permanecen intactas.
- Referencias contrastadas offline con componentes y horas de los presupuestos.
  No se afirma que un experto del alumno las haya validado. Se conservan las
  [aproximaciones conocidas](../docs/sesion11_porting_drift.md).
- Juez: `gpt-4o-mini`; embeddings del evaluador: `text-embedding-3-small`.
- Generador/reformulador: los configurados en la aplicación, registrados al
  recoger muestras; no se presupone que coincidan con el juez.
- Generador fundamentado: Responses API nativa mediante `litellm.responses`
  desde el wrapper compartido, con esquema estricto y validación Pydantic local.
  El reformulador sigue con Instructor/LiteLLM. Las muestras registran
  `generation_api` y `generation_client`.
- Recuperación del harness: híbrida, reranking, umbral 1.2, solo
  `budget_component`, sin filtro sectorial ni recuperación avanzada.
- Generación del harness: una respuesta y auditoría, sin autorreparación HTTP.
- Respuesta para RAGAS: JSON completo de `Estimate`, sin ocultar cifras,
  descripciones, evidencia, asunciones ni alcance sin soporte.

Estas decisiones no reproducen todos los defaults del endpoint ni garantizan
comparabilidad numérica con otra configuración. Una nueva representación de la
respuesta o un nuevo golden exige identificar otra ejecución.

## Comprobaciones offline realizadas

- Pruebas dirigidas de citación, truncado, reintentos, caché, Streamlit y
  evaluación, con conexiones de red/servicios bloqueadas en el proceso de prueba.
- Demo determinista: una línea fundamentada, una con ID inventado y una sin
  datos; se detecta `invented` y el comando termina con `PASS`.
- Comparación literal del golden con el instructor: sin diferencias.
- Contraste del corpus: Q1 480 h; Q2 460 h; Q3 560 h; Q4 500 h; Q5 600 h.
- Lint dirigido: ver comando y resultado en el cierre offline del plan.
- Revalidación del agregador: 98 tests superados, incluidos LiteLLM real
  con HTTP en memoria y validación Pydantic, métodos anteriores del wrapper, generador,
  evaluación, Wizard y smoke de conversaciones con runtime Redis aislado.
  Dos avisos de deprecación de LangChain; Ruff dirigido sin errores.
  No es una comprobación del proveedor real ni una ejecución de RAGAS.

Las pruebas con dobles comprueban contratos, persistencia de tabla y rechazo de
NaN; **no** demuestran que un juez real devuelva métricas ni que RAGAS importe.

### Dependencias pendientes de comprobar

En la comprobación de dependencias faltaban `ragas` y `datasets`. El intento
`uv lock --offline --script scripts/score_ragas_s11.py` falla porque `ragas` no
está en caché. No se descargó nada ni se escribió un lock ficticio.

El LangChain instalado incluye `langchain-community` 0.4.2, sin la ruta
`chat_models.vertexai` mencionada por el problema de LIDR. El scorer declara un
entorno aislado con RAGAS 0.4.3 y LangChain anterior a 0.4, sin shims ni cambios
en las dependencias de la API. **Ese conjunto aún debe resolverse y probarse.**

## Comandos preparados, no ejecutados online

Desde el proyecto, después de la preparación y comprobaciones de la guía:

```bash
rtk proxy env DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/estimator REDIS_URL=redis://127.0.0.1:6379 uv run --locked python scripts/eval_ragas_s11.py --collect-only evals/ragas_samples_s11.json

rtk proxy uv run --locked python scripts/eval_ragas_s11.py --inspect-samples evals/ragas_samples_s11.json

rtk proxy uv run --locked --script scripts/score_ragas_s11.py --score-file evals/ragas_samples_s11.json --out evals/ragas_baseline_s11.json
```

La recolección conserva cada consulta terminada si una posterior falla, pero una
colección parcial no se puede puntuar como baseline de cinco consultas.
No se pisan muestras ni informes previos. Repetir scoring no regenera respuestas,
pero vuelve a pagar las llamadas del juez.

## Tabla propia y nota: pendientes de ejecución manual

El scorer escribirá `ragas_baseline_s11.json` y `ragas_baseline_s11.md`, con Q1-Q5,
las cuatro métricas y la media aritmética. No existen todavía: no usar una tabla
de ceros ni la del instructor como sustituto.

Después de medir, anotar aquí comando real, configuración efectiva,
versiones y enlace a la tabla. Añadir 2-3 frases sobre una anomalía observada,
citando consulta, métrica y contenido concreto de su muestra. La plantilla
para hacerlo sin IA está en el paso I de la guía.

## Límites aceptados

- Responses API en el generador fundamentado; el esquema estricto y los
  validadores se prueban offline, pero falta la generación con el modelo real.
- Se usa `litellm.responses`, no el método literal `client.responses.parse` del
  enunciado; se conserva el agregador y se valida explícitamente con Pydantic.
- Citas persistentes visibles como warning/confianza baja, no rechazo HTTP.
- El verificador prueba pertenencia del chunk, no identidad documental ni
  literalidad o veracidad semántica de la evidencia.
- Cero IDs colgantes no garantiza faithfulness alta.
