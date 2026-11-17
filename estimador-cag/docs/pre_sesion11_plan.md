# Pre-sesión 11: plan de implementación y relevo de sesión

## 0. Estado y cómo utilizar este documento

Este documento es el entregable de planificación solicitado por el usuario. Debe
permitir continuar en otra sesión sin disponer del historial del chat.

**Estado: pendiente de revisión del usuario. No comenzar la implementación hasta
que lo apruebe o indique sus correcciones.** Las propuestas de diseño de este
documento no deben confundirse con decisiones ya aprobadas.

Antes de aprobar la implementación hay que cerrar todas las decisiones de
diseño y preparación con el usuario. Preguntar de una en una, explicar en
palabras llanas qué significa cada opción, recomendar una y justificarla,
esperar su respuesta y registrarla aquí antes de continuar. No aplazar esas
decisiones a la sesión de implementación ni interpretar una aprobación parcial
como aprobación del plan completo.

Al redactarlo, el 17 de noviembre de 2026:

- Solo se han inspeccionado archivos y el historial de Git. No se han ejecutado
  tests, llamadas a modelos, ingestas, migraciones, instalaciones ni servicios.
- No se ha implementado el ejercicio ni generado una baseline propia.
- No se ha creado ningún commit.
- El único archivo nuevo que se pretende dejar en esta sesión es este plan.
- Las referencias de líneas siguientes corresponden al estado inspeccionado y
  pueden desplazarse durante la implementación.

Orden para retomar:

1. [ ] Leer este documento completo.
2. [ ] Leer la respuesta del usuario a su revisión. Si no está disponible, pedirla.
3. [ ] Comprobar ramas, commits y estado de ambos repositorios, sin cambiar nada.
4. [ ] Implementar únicamente el alcance aprobado.
5. [ ] Completar la fase 1 offline, incluidas todas las validaciones que no
   requieran servicios, y entregar la guía autónoma de la fase 2.
6. [ ] Confirmar al cerrar que no se han hecho commits sin autorización explícita.

### 0.1 Seguimiento persistente y verificable por una persona

Todas las casillas empiezan vacías, incluidas las comprobaciones que habrá que
repetir en la sesión de implementación. Las evidencias históricas de este
documento no significan que esos pasos futuros estén completados.

- Usar `[ ]` para pendiente y `[x]` únicamente para completado y comprobado.
- Actualizar este mismo archivo al completar cada subpaso o validar cada
  criterio, no solo al terminar una fase o al cerrar la sesión.
- Marcar la casilla de un paso completo únicamente cuando todos sus subpasos y
  comprobaciones aplicables hayan terminado.
- Una implementación escrita no demuestra que su criterio de validación pase:
  marcar cada criterio solo después de comprobarlo.
- Junto a cada elemento marcado, añadir evidencia concreta: archivo y símbolo,
  comando y resultado, ruta del informe o comprobación humana realizada.
  No basta con escribir «hecho» o «validado».
- En las ejecuciones manuales del usuario, este registrará la salida o
  confirmación antes de marcar la casilla. No depender de una IA presente
  para avanzar ni copiar secretos en las evidencias.
- Si algo falla o queda a medias, mantener la casilla vacía y anotar debajo
  `En curso:` o `Bloqueado:`, lo ya realizado y la siguiente acción exacta.
- Si un subpaso condicional no aplica, dejar su casilla vacía y anotar
  `No aplica:` con motivo y evidencia. El paso padre puede cerrarse cuando los
  demás subpasos estén comprobados y esa exclusión esté justificada.
- Al retomar, localizar el primer elemento aplicable sin marcar, leer sus
  evidencias/notas y confirmar las dependencias antes de continuar.
- Las decisiones, hechos históricos y exclusiones de alcance no son tareas:
  mantienen su formato informativo, sin casillas de ejecución.

### 0.2 Dos fases de trabajo: offline y online

Acuerdo del 17 de noviembre de 2026: la separación depende de si se necesitan
servicios levantados, no de si se ejecutan comandos.

**Fase 1 — Implementación completa y validación offline**

- Implementar todo el alcance aprobado: código, configuración, pruebas y
  documentación; no dejar implementación pendiente para la fase 2.
- Ejecutar todas las validaciones aplicables que no necesiten contenedores,
  servicios, bases de datos ni llamadas externas: revisión estática, formato,
  lint, tipos, contratos, fixtures, pruebas aisladas y demo determinista.
- No ejecutar Docker, builds, arranques de servicios, migraciones, ingestas,
  consultas a servicios ni llamadas a modelos. No utilizar servicios aunque
  ya estén levantados. No confundir pruebas de integración con dobles locales
  con pruebas que necesitan infraestructura real.
- Revisar antes de ejecutar que los comandos, imports, fixtures y hooks no
  arrancan servicios ni conectan con infraestructura. Usar el entorno local
  disponible; si falta una dependencia o se requiere red, dejar el bloqueo
  documentado para la preparación manual de la fase 2, sin instalar ni
  descargar automáticamente.
- Registrar comandos, resultados y límites de lo comprobado. No declarar
  verificado un comportamiento online mediante una prueba con mocks.
- Entregar una guía completa y autónoma para la fase 2 antes de cerrar esta
  fase. La fase 2 no se ejecuta automáticamente al terminar la fase 1.

**Fase 2 — Ejecución manual y validación online, sin IA**

- Reservar para esta fase los builds y arranques necesarios, las comprobaciones
  con API, PostgreSQL, Redis y Streamlit reales, las migraciones del arranque,
  la ingesta si procede, las llamadas a modelos y la evaluación real.
- El usuario decidirá cuándo iniciarla y ejecutará todos los pasos manualmente,
  sin asistencia de IA ni necesidad de consultar el historial del chat.
- No repetir por defecto las validaciones ya superadas offline. Incluir las
  bloqueadas por dependencias únicamente si no pudieron resolverse en fase 1,
  explicando el motivo; no convertir la fase 2 en una lista de pruebas
  offline aplazadas por comodidad.
- Para cada paso, documentar: objetivo, requisitos y dependencias, directorio y
  terminal, comando exacto listo para copiar, valores que deban sustituirse y
  cómo obtenerlos sin revelar secretos, resultado esperado, criterio medible
  de éxito, evidencia que guardar y siguiente paso.
- Para cada fallo previsible, indicar diagnóstico y acción concreta, cuándo
  detenerse, qué no repetir y cómo recuperar el estado anterior si corresponde.
  Advertir antes de cambios de datos, migraciones, costes o impacto en servicios
  compartidos; no proponer borrados ni reinicios como arreglo genérico.
- No usar instrucciones vagas como «comprobar que funciona», marcadores sin
  resolver, selección de comandos a criterio de una IA ni pasos que requieran
  «pegar la salida al asistente para continuar».
- Comprobar offline la coherencia de la guía con el código final, los scripts,
  sus argumentos y la configuración. Identificar expresamente los comandos
  online aún no ejecutados; una revisión documental no demuestra que funcionen.

Mantener separados el cierre offline y el cierre global: terminar la fase 1 no
implica que la fase 2 se haya ejecutado ni que exista una baseline propia.

## 1. Contexto, repositorios y corrección del alcance

### 1.1 Ubicaciones

```text
Repositorio alumno:
/home/basf/wsTakeoff/ai-engineering

Proyecto alumno:
/home/basf/wsTakeoff/ai-engineering/estimador-cag

Repositorio instructor:
/home/basf/wsTakeoff/ai-engineering-lidr

Proyecto Python instructor:
/home/basf/wsTakeoff/ai-engineering-lidr/estimator
```

La rama del alumno comprobada es `session-11/pre-work`.

El estado inicial del alumno contiene un archivo no rastreado ajeno al trabajo:
[src/alembic.ini](../src/alembic.ini). No borrarlo, incluirlo en cambios ni
sobrescribirlo. Volver a comprobar el estado antes de editar por si hay cambios
adicionales del usuario.

### 1.2 La referencia correcta es session_11, no la sesión completa

Inicialmente el usuario indicó el commit
`8695e8b5a95658b2ccfdd4ec14edcf6a9c70d3ae`, cuyo mensaje es
`session 11 completed`. Después corrigió esa indicación y cambió personalmente
el checkout del instructor a la rama `session_11`.

**Referencia definitiva, comprobada tras la corrección:**

```text
branch: session_11
commit: 3292744c12c69f88b10ed8c851ae9fb733e2667d
message: solved pre exercise session 11
```

El usuario explicó que ambos proyectos ya estaban sincronizados conceptualmente
hasta `session_10_live`, aunque no tenían por qué tener el mismo código.
Por tanto, el análisis de qué portar debe partir de:

```bash
rtk git -C /home/basf/wsTakeoff/ai-engineering-lidr \
  diff session_10_live 3292744c12c69f88b10ed8c851ae9fb733e2667d
```

No usar una comparación completa de los dos árboles como lista automática de
cosas que faltan al alumno: sus estructuras y decisiones anteriores difieren.

### 1.3 Qué ocurrió entre las dos referencias

El historial inspeccionado entre `session_10_live` y el checkout inicialmente
indicado contiene exactamente estos dos commits:

| Commit | Contenido |
| --- | --- |
| `3292744` | Pre-work: citación por línea, validación, golden de generación y RAGAS. Es nuestro alcance. |
| `8695e8b` | Sesión completa: verificación semántica, augmentation, synthesis, evaluación ampliada e indexación. Fuera de alcance. |

El diff correcto del pre-work afecta 17 archivos:

```text
estimator/app/api/routers/estimate_stages.py
estimator/app/generation/rag/context_assembler.py
estimator/app/generation/rag/estimator.py
estimator/app/generation/rag/prompt_builder.py
estimator/app/generation/rag/schemas.py
estimator/app/generation/rag/validation.py
estimator/evals/RAGAS_BASELINE_S11.md
estimator/evals/golden_generation_s11.json
estimator/evals/ragas_baseline_s11.json
estimator/pyproject.toml
estimator/scripts/demo_verify_citations_s11.py
estimator/scripts/eval_ragas_s11.py
estimator/scripts/score_ragas_s11.py
estimator/tests/api/test_estimate_stages.py
estimator/tests/generation/rag/test_estimator.py
estimator/tests/generation/rag/test_validation.py
estimator/uv.lock
```

No hay cambios en `estimator-web` entre `session_10_live` y ninguno de esos dos
commits. No hay una modificación Rails del pre-work que debamos traducir
literalmente a Streamlit.

## 2. Instrucciones y decisiones del usuario

### 2.1 Decisiones ya tomadas

1. **No hacer ningún commit hasta que el usuario revise y lo autorice.**
2. Implementar solo el pre-work del ejercicio, equivalente al commit `3292744`.
3. Seguir el enfoque de LIDR, adaptándolo a nuestra arquitectura.
4. Podemos copiar código y datos del instructor, pero solo si encajan y nos
   parecen correctos; no copiar por imitación.
5. No incorporar Rails/Ruby. La interfaz del alumno es Streamlit.
6. Conservar Instructor/LiteLLM; no migrar a Responses API para este ejercicio.
7. Para las citaciones colgantes, seguir el comportamiento de LIDR, descrito en
   la sección 5. No introducir por nuestra cuenta un rechazo HTTP distinto.
8. Las llamadas de pago están autorizadas, **pero el usuario quiere ejecutarlas
   personalmente para aprender**. La autorización no es una orden para que el
   asistente las ejecute en su lugar.
9. Entregar instrucciones de ejecución real paso a paso, autónomas y verificables.
   Actualizado el 17 de noviembre de 2026: el usuario ejecutará la fase 2
   manualmente, sin IA; no depender de ayuda interactiva para interpretar
   resultados o decidir cómo continuar. Ver sección 0.2.
10. Código nuevo en inglés: nombres, comentarios, docstrings, mensajes, logs,
    literales de interfaz y prompts. La documentación y el golden pueden estar
    en español.
11. Investigar con evidencias de código, datos, documentación o historial.
    Distinguir hechos de propuestas y de lo que no se ha verificado.
12. No hacer inferencias sobre credenciales, servicios, datos cargados o
    resultados de métricas.
13. Añadir un apartado separado de estimación fundamentada en Streamlit y
    mantener el Wizard actual sin cambios. Aprobado el 17 de noviembre de 2026:
    el usuario eligió la opción 1 condicionada a que esa función existiera solo
    como endpoint sin pantalla propia en nuestro cliente. Se comprobó esa
    condición en `src/routers/rag_estimate.py` y buscando `from-transcript` y
    `estimate_from_transcript` en `streamlit_app.py`, `src/` y `scripts/`:
    el endpoint existe y no hay llamada desde la interfaz Streamlit.
    La presentación del informe se resolvió por separado en la decisión 14.
14. No añadir el resumen ni el detalle completo de `CitationReport` a la nueva
    pantalla. El usuario decidió: «los muestra lidr? si si, si. si no, no».
    Se comprobó que la API de LIDR devuelve `citation_report`, pero
    `estimator-web/app/models/rag/generation_view.rb` no lo lee y las vistas
    no muestran sus contadores ni el detalle por línea. Su vista
    `_step_generation.html.erb` conserva un aviso anterior para
    `fabricated_source_ids` e incoherencias; eso no es el nuevo informe.
    Su `estimator/streamlit_app.py` tampoco muestra ese informe. Mantener el
    informe detallado en logs y evaluación, mostrar las fuentes y request ID
    en nuestro panel y no ampliar el contrato HTTP solo para ese resumen.
15. Conservar literalmente las cifras y el criterio del golden de generación
    de LIDR, sin corregir aproximaciones ni añadir por nuestra cuenta la
    aclaración de 8 horas/día al prompt. El usuario eligió la opción 2 y pidió:
    «el 2, pero anota esto en un archivo sesion11_porting_drift.md».
    Registrar la discrepancia conocida y la decisión de no corregirla en
    [sesion11_porting_drift.md](sesion11_porting_drift.md). No confundir conservar
    las referencias con copiar sus métricas: generar nuestra propia baseline.
16. Usar el entorno local habitual: API, PostgreSQL y Redis con Docker Compose,
    y Streamlit aparte en esta misma máquina. Confirmado por el usuario el
    17 de noviembre de 2026 con esa opción explícita. No crear otro despliegue
    ni otra base de datos para este ejercicio. Los pasos de ejecución deben
    concretar las rutas/conexiones de ese montaje, no pedir elegir entorno
    durante la implementación.

El usuario pidió este archivo porque va a cerrar la sesión. No necesita ahora
una implementación parcial ni que se arranquen pruebas reales automáticamente.

### 2.2 Restricciones prácticas

- Mantener cambios quirúrgicos y preservar los flujos anteriores.
- No leer ni mostrar secretos. La existencia de `.env` se ha visto en el
  listado, pero no se ha leído su contenido.
- El entorno puede estar compartido. No parar procesos ajenos, reiniciar
  servicios ni modificar datos sin verificar con el usuario qué instancia usa.
- No borrar datos para preparar la evaluación. No ejecutar `FLUSHDB`, limpiar
  volúmenes o eliminar corpus anteriores por conveniencia.
- Los comandos de shell deben ir prefijados con `rtk`; para herramientas sin
  adaptación específica se puede usar `rtk proxy`.
- Los ejemplos de comandos de este documento son instrucciones futuras, no
  evidencia de que se hayan ejecutado.

## 3. Requisitos del ejercicio que debemos entregar

### 3.1 Citación verificable por línea

Cada tarea de una estimación generada a partir de históricos es una línea.
Debe transportar:

```python
class SourceReference(BaseModel):
    chunk_id: str
    document_id: str
    evidence: str
```

Adaptar nuestro `TaskItem`, no crear un modelo paralelo innecesario:

- [ ] Mantener `name` y `description`.
- [ ] Mantener esfuerzo en `engineer_days`, como el modelo actual y LIDR.
- [ ] Permitir esfuerzo nulo cuando no hay soporte.
- [ ] Añadir `grounded: bool`.
- [ ] Sustituir `sources: list[int]` por `sources: list[SourceReference]`.
- [ ] `grounded=True` exige al menos una fuente.
- [ ] `grounded=False` exige fuentes vacías y esfuerzo nulo.
- [ ] No representar falta de datos mediante cero días.
- [ ] Mantener las asunciones y la política global de contexto insuficiente.

El prompt debe pedir IDs exactos del contexto, documento correspondiente y
evidencia literal, no paráfrasis. No inventar números ni fuentes.

Implementar:

```python
def verify_citations(
    estimate: Estimate,
    retrieved_chunk_ids: set[str],
) -> CitationReport:
    ...
```

El informe debe distinguir líneas `grounded`, `dangling` e `insufficient`,
incluir detalles por línea, contadores y los IDs colgantes. Comprobar también
las citas globales heredadas, no solo las fuentes por tarea.

Debe existir una prueba offline con una cita deliberadamente inventada.
Registrar el resultado mediante structlog correlacionado con `request_id`.

### 3.2 RAGAS

Enriquecer las cinco consultas Q1-Q5 del golden de recuperación de sesión 10 con
`ground_truth`, sin sustituir el set existente ni eliminar Q6-Q8.

Por cada consulta registrar:

```text
question
answer
contexts
ground_truth
```

Calcular realmente:

```text
faithfulness
answer_relevancy
context_precision
context_recall
```

Juez propuesto por la referencia: `gpt-4o-mini`. Embeddings de evaluación:
`text-embedding-3-small`. No confundir el juez con el modelo que genera las
estimaciones; conservar y registrar la configuración efectiva del generador.

Entregables:

1. [ ] Schema, prompt y función verificadora.
2. [ ] Golden de generación Q1-Q5 con respuestas de referencia.
3. [ ] Script de evaluación, muestras trazables y tabla de cinco filas más promedio.
4. [ ] Nota propia de 2-3 frases sobre los resultados reales.

No dar por terminado el apartado de métricas hasta tener las cuatro métricas
numéricas para las cinco consultas y sus promedios.

## 4. Evidencias del proyecto alumno y correspondencia con LIDR

### 4.1 Generación y contratos

| Archivo alumno | Hecho comprobado |
| --- | --- |
| [schemas.py](../src/generation/rag/schemas.py#L256) | `TaskItem.engineer_days` es entero obligatorio y `sources` es `list[int]`; no existe `grounded`. |
| [schemas.py](../src/generation/rag/schemas.py#L236) | `SourceCitation` global usa `source_id: int`, `relevance` y `used_for`. No eliminarlo sin necesidad. |
| [schemas.py](../src/generation/rag/schemas.py#L295) | `Estimate` tiene módulos, totales, asunciones, confianza y explicación de contexto insuficiente. |
| [schemas.py](../src/generation/rag/schemas.py#L385) | Existe `GenerateResult`, aunque no hay router de etapas que lo exponga actualmente. |
| [estimator.py](../src/generation/rag/estimator.py#L31) | Generación y orquestación del flujo RAG fundamentado. |
| [validation.py](../src/generation/rag/validation.py#L18) | `validate_citations` comprueba IDs globales y de tareas, pero no distingue líneas sin soporte. |
| [prompt_builder.py](../src/generation/rag/prompt_builder.py#L14) | Ya pide fuentes por tarea y no inventar números; aún no exige `SourceReference`, `grounded` ni evidencia literal. |
| [context_assembler.py](../src/generation/rag/context_assembler.py#L19) | Cada source incluye ID, sector, año, tipo y distancia; falta `document_id`. |

Nuestro `RetrievedChunk.id` es un entero de base de datos. El ID trazable de
presupuesto viaja en `budget_id`, y existe `source_id` genérico opcional.
No confundir esos campos con `SourceCitation.source_id`, que es el ID numérico
del chunk. En las nuevas referencias usar `chunk_id=str(chunk.id)`.

LIDR expone `document_id = chunk.source_id or chunk.budget_id or "unknown"` en el
XML. La prioridad es reutilizable, pero `"unknown"` no prueba procedencia:
verificar que las muestras presupuestarias tienen realmente `budget_id`.
No fabricar documentos ni presentar ese marcador como identificación verificada.

Nuestro ensamblador soporta `distance=None` con `not-scored` y el modelo lleva
`has_vector_distance`. Preservar esta mejora del alumno al adaptar el XML;
copiar la interpolación numérica de LIDR rompería ese caso.

### 4.2 Wrapper de modelos y desviación respecto al enunciado

[LLMWrapper](../src/services/llm_wrapper.py#L95) usa:

```text
instructor.from_litellm(litellm.completion)
    -> chat.completions.create_with_completion(...)
    -> response_model de Pydantic
```

`complete_structured` conserva selección de modelo, timeout, delimitación de
contenido no confiable, logs, tokens, latencia y coste. Tiene reintentos de
Instructor cuando fallan validadores Pydantic. El generador RAG conserva además
sus reintentos de citación/coherencia: no son el mismo mecanismo.

| Aspecto | Enunciado literal: lado A | Repositorios actuales: lado B |
| --- | --- | --- |
| API de generación | `client.responses.parse`, formato estricto | Instructor sobre LiteLLM |
| Validación de negocio | Hay que implementarla | También; Pydantic e Instructor permiten validación y reintento |
| Veracidad de una cita | No la demuestra la API | Tampoco; requiere cotejo con el contexto |
| Impacto de elegir A | Añadir/cambiar integración y comprobar equivalencia del wrapper | B mantiene la integración existente |

**Decisión del usuario: B.** Documentar que no se cumple literalmente el punto
del enunciado que obliga a Responses API. No afirmar que el wrapper actual
garantiza exactamente el mismo `text.format` estricto: no se ha comprobado.
No migrar el resto de llamadas del proyecto.

### 4.3 Los dos caminos existentes no son una decisión pendiente

La primera pregunta del asistente los presentó erróneamente como alternativas.
El usuario pidió seguir la evolución real de LIDR, no rediseñarlos.

**A. Estimación RAG fundamentada**

```text
transcript -> reformulate -> embed -> retrieve
           -> truncate whole chunks -> assemble -> generate
           -> verify/retry -> coherence -> optional idempotency
```

Se expone en [rag_estimate.py](../src/routers/rag_estimate.py#L29) mediante
`POST /v1/estimate/from-transcript`, devuelve `Estimate`, requiere
`X-API-Key` con `ESTIMATE_API_KEY` y está limitado a 10 solicitudes/minuto.
El middleware devuelve `X-Request-ID`.

**B. Wizard persistido de sesión 10**

```text
transcript -> reformulation -> free structure
           -> human structural review -> per-task historical neighbors
           -> weighted consensus hours -> human hours/rates confirmation
```

Evidencias:

- [services/rag_runs.py](../src/services/rag_runs.py#L66) genera estructura
  mediante `generate_structure`, no mediante el generador fundamentado.
- [structure.py](../src/generation/rag/structure.py#L12) prohíbe expresamente
  generar horas y fuentes en ese paso.
- [task_hours.py](../src/generation/rag/task_hours.py#L26) recupera
  `historical_task` y calcula consenso; no pide al LLM que invente horas.
- [wizard.py](../src/generation/rag/wizard.py#L10) tiene contratos separados
  (`StructureEstimate`, `TaskHours`, etc.). No es necesario convertirlos a
  `Estimate` para cumplir el pre-work.
- [wizard_ui.py](../src/wizard_ui.py#L81) renderiza ese flujo.
- [streamlit_app.py](../streamlit_app.py#L922) llama a `render_wizard`.

**El pre-work de LIDR aplica la citación nueva a A y evalúa A con RAGAS.**
No exige atribuir fuentes inexistentes al paso de estructura libre de B.
Conservar B, incluidas edición humana, persistencia, contratos y cálculo horario.

### 4.4 Recuperación: no asumir que todo el proyecto usa el camino avanzado

- [retriever.py](../src/generation/rag/retriever.py#L80) implementa
  `search_chunks`, usado por nuestro generador fundamentado y por horas.
- La búsqueda híbrida/reranking correspondiente está en
  [search_pipeline.py](../src/generation/rag/retrieval/search_pipeline.py#L104).
- El camino avanzado independiente está en
  [advanced_search_pipeline.py](../src/generation/rag/retrieval/advanced_search_pipeline.py#L147).
- [eval_retrieval_s10.py](../scripts/eval_retrieval_s10.py#L21) evalúa ese camino
  avanzado con distintas configuraciones.

No afirmar que routing, expansión y filtrado temporal se ejecutan en el
orquestador RAG solo porque existen en el repositorio. El código leído del
orquestador llama a `search_chunks`, no a `advanced_retrieve`.

La baseline RAGAS de LIDR fuerza búsqueda híbrida, reranking y umbral 1.2;
su import `app.generation.rag.retrieval.pipeline` no existe con ese nombre aquí.
Adaptar a nuestro `generation.rag.retrieval.search_pipeline.retrieve` sin portar
toda su organización ni ampliar este ejercicio a un cambio de recuperación.
Explicitar los parámetros del harness y su diferencia con defaults del endpoint.

### 4.5 Datos y documentación

Se ejecutó `diff -q` entre alumno e instructor y no hubo diferencias en:

- [budgets_sample.json](../data/budgets_sample.json).
- [golden_retrieval.json](../evals/golden_retrieval.json).

El golden existente contiene Q1-Q8. Q1-Q5 son consultas presupuestarias;
Q6-Q8 comprueban casos multi-colección. No sustituirlas por un set inventado.

Aunque el enunciado dice que el corpus está en español, los archivos inspeccionados
de presupuestos y las consultas Q1-Q5 están en inglés. No traducirlos para
forzar esa descripción ni diagnosticar resultados como si se hubiera verificado
un corpus español.

La [guía de sesión 10](post_sesion_10_guia.md) documenta Docker, corpus y Wizard.
No ejecutar sus pasos de borrado de corpus: no son requisito de este ejercicio.

### 4.6 Estado local comprobado durante la revisión del plan

Comprobación de solo lectura el 17 de noviembre de 2026:

```text
docker: 29.1.3
docker-compose: 1.29.2
docker compose -f ... ps: falla en esta terminal
docker-compose -f ... ps: funciona

estimator: Exit 137
estimator-postgres: Exit 0
estimator-redis: Exit 143
```

Se usó `rtk proxy docker-compose -f
/home/basf/wsTakeoff/ai-engineering/estimador-cag/docker-compose.yml ps`.
Los códigos de salida no demuestran por sí solos la causa de la parada.
No se ha arrancado, reiniciado ni modificado ningún servicio.

El usuario indicó después: «mira el readme si quieres ver como arrancar los
servicios... no te lo inventes». Se volvió a leer el README: su apartado Docker
documenta `docker compose up --build` y el apartado de arranque para pruebas
documenta `docker compose up --build -d`; Streamlit se arranca en host con
`uv run streamlit run streamlit_app.py`.

**Seguir ese procedimiento documentado.** No sustituirlo por un arranque
parcial de PostgreSQL y Redis: esa propuesta del asistente no fue aprobada.
Tampoco cambiar el procedimiento del usuario a `docker-compose` por el fallo
de una consulta en la terminal del asistente. Si el usuario encuentra un error
al ejecutar el comando documentado, recoger su salida exacta y resolver ese
error sin asumir la causa.

Comandos de arranque documentados, con el prefijo `rtk` del entorno:

```bash
# Desde /home/basf/wsTakeoff/ai-engineering/estimador-cag
rtk proxy docker compose up --build -d

# En otra terminal, desde el mismo directorio
rtk proxy uv run streamlit run streamlit_app.py
```

Fuentes: [README, Docker](../README.md#docker) y
[README, CAG stress / arranque](../README.md#stress-server-up).
El arranque de la API aplica las migraciones pendientes, como define Compose.
No copiar `.env.example` sobre un `.env` existente ni ejecutar instrucciones
históricas de limpieza de volúmenes del README.

Sigue sin comprobarse la conexión a la base, los datos persistidos y los
permisos reales de modelos. El siguiente paso de preparación es que el usuario
ejecute el arranque documentado y comparta su resultado, sin mostrar secretos.

## 5. Política exacta de citaciones y sus límites

### 5.1 Comportamiento que seguiremos de LIDR

En el pipeline completo:

1. [ ] Verificar contra **los chunks conservados tras truncar**, no todos los
   candidatos recuperados.
2. [ ] Registrar el informe con `request_id`.
3. [ ] Si hay IDs colgantes, pedir una corrección al generador.
4. [ ] Verificar la respuesta corregida.
5. [ ] Si persisten, warning `citations_unrepaired` y `confidence="low"`.
6. [ ] Mantener el guard de coherencia; si una reparación posterior regenera la
   estimación, verificar también la respuesta final para no devolver otra
   generación sin comprobar.

El punto 6 es una precaución directamente ligada al requisito de verificar lo
que realmente se devuelve. Evitar bucles de reparación ilimitados y conservar
los límites de reintento existentes.

En el router de etapas del instructor, `/generate` devuelve
`citation_report`, `fabricated_source_ids` y `coherent`, sin autorreparación.
**Nuestro proyecto no tiene ese router registrado ni un archivo de etapas.**
No crearlo entero solo para imitar una estructura del instructor.

### 5.2 Desviaciones y límites que deben quedar visibles

- Warning y confianza baja **no equivalen a rechazar la respuesta**. El usuario
  eligió expresamente seguir LIDR tras explicarle esa diferencia con el texto
  del ejercicio. No describir el resultado como rechazo estricto.
- `verify_citations(estimate, set[str])` prueba pertenencia del chunk, no que
  `document_id` sea correcto, que `evidence` sea una subcadena literal ni que
  una cifra se deduzca semánticamente de la fuente.
- Pedir evidencia literal y documento en el prompt no es una comprobación
  programática de ambos campos. No anunciar esas garantías adicionales.
- La comprobación semántica del segundo commit está fuera del pre-work.
- Si faltan IDs documentales en datos reales, investigar el origen y corregir
  la propagación dentro de este alcance; no reemplazar por un identificador
  ficticio con apariencia de éxito.

## 6. Plan de implementación, en orden

### Paso 1. Revalidar estado y hacer inventario de afectados

- [ ] **Paso 1 completado y comprobado.**

1. [ ] Comprobar que seguimos en las ramas y commits de la sección 1.
2. [ ] Revisar cambios nuevos del usuario y no revertirlos.
3. [ ] Buscar referencias a `TaskItem`, `task.sources`, `engineer_days`,
   `validate_citations`, `GenerateResult` y deserializaciones de `Estimate`.
4. [ ] Leer los tests afectados antes de cambiar contratos.
5. [ ] No modificar infraestructura, modelos de BD, migraciones ni recuperación
   avanzada salvo dependencia demostrada del cambio.

Las búsquedas ya realizadas localizaron consumidores directos en
[test_estimator.py](../tests/test_estimator.py) y
[test_validation.py](../tests/test_validation.py), además del orquestador.
Repetir la búsqueda sobre el estado de la sesión de implementación.

### Paso 2. Extender los modelos Pydantic

- [ ] **Paso 2 completado y comprobado.**

En [schemas.py](../src/generation/rag/schemas.py):

1. [ ] Añadir `SourceReference`.
2. [ ] Cambiar `TaskItem` conservando la estructura módulos/tareas:
   `engineer_days: int | None`, `grounded` y fuentes tipadas.
3. [ ] Añadir un `model_validator(mode="after")` para las tres reglas de integridad.
4. [ ] Añadir `LineCitation` y `CitationReport`, con los campos y estados de LIDR:
   contadores, IDs citados/colgantes, detalle por módulo/tarea y `has_dangling`.
5. [ ] Mantener `SourceCitation` global y `Estimate` globalmente insuficiente.
6. [ ] Actualizar contratos dependientes solo si tienen consumidores reales. Si se
   adapta `GenerateResult`, cambiar los IDs colgantes a strings y contemplar el
   informe opcional como LIDR, sin añadir endpoints muertos.
7. [ ] No convertir el Wizard de sesión 10 a este modelo.

Conservar días enteros como LIDR evita ampliar el cambio a unidades nuevas.
Conservar también el texto y las aproximaciones del golden de LIDR, conforme a
la decisión 15. No reescribirlo con equivalencias exactas.

### Paso 3. Propagar documento y reforzar el prompt

- [ ] **Paso 3 completado y comprobado.**

En [context_assembler.py](../src/generation/rag/context_assembler.py):

1. [ ] Añadir `document_id` al `<source>`, usando procedencia real del chunk.
2. [ ] Conservar soporte de distancia ausente.
3. [ ] Conservar chunks completos y presupuesto calculado sobre el XML envuelto:
   el atributo nuevo también consume tokens.
4. [ ] Verificar procedencia en nuestros resultados reales de presupuestos.

En [prompt_builder.py](../src/generation/rag/prompt_builder.py):

1. [ ] Definir explícitamente que cada tarea es una línea.
2. [ ] Exigir `grounded=true`, referencias exactas y evidencia literal si hay soporte.
3. [ ] Exigir `grounded=false`, `engineer_days=null` y fuentes vacías si no lo hay.
4. [ ] Pedir que se explicite el alcance sin soporte en las asunciones.
5. [ ] Mantener contexto global insuficiente y suma de tareas fundamentadas.
6. [ ] Conservar el tratamiento de unidades del prompt de LIDR; no añadir una
   instrucción propia de conversión a días de 8 horas, conforme a la decisión 15.
7. [ ] Conservar la descomposición actual; no optimizar el prompt para inflar RAGAS.

La propuesta de aclarar adicionalmente las unidades fue rechazada por el usuario
para conservar el criterio de LIDR. El motivo y el riesgo están documentados en
[sesion11_porting_drift.md](sesion11_porting_drift.md).

### Paso 4. Implementar verificador, integración y observabilidad

- [ ] **Paso 4 completado y comprobado.**

En [validation.py](../src/generation/rag/validation.py):

1. [ ] Implementar `verify_citations` como función pura.
2. [ ] Recorrer módulos/tareas y clasificar cada línea.
3. [ ] Agregar citas globales a la detección de IDs inventados.
4. [ ] Ordenar y deduplicar IDs colgantes; no deduplicar los contadores de
   referencias si se sigue la semántica de LIDR.
5. [ ] Resolver los consumidores de `validate_citations`: sustituirlos; mantener un
   adaptador solo si quedan usos reales que lo necesiten.
6. [ ] Mantener `check_coherence`.

En [estimator.py](../src/generation/rag/estimator.py):

1. [ ] Usar los IDs de `kept` y la política de la sección 5.
2. [ ] Registrar informe inicial y resultado final si hubo regeneración, para que
   el log no muestre solo una versión descartada.
3. [ ] Mantener `request_id` de HTTP o generar uno en ejecución no HTTP.
4. [ ] Conservar selección de modelo, reasoning, techo de tokens, hilo de trabajo,
   errores, soft-fail e idempotencia.
5. [ ] No añadir el gate semántico de la sesión completa.

Compatibilidad de caché:

- [idempotency.py](../src/generation/rag/idempotency.py#L56) deserializa `Estimate`.
  Una entrada antigua con fuentes enteras ya no cumple el schema nuevo.
- Su código actual trata errores de deserialización como miss y elimina solo
  la clave concreta. No purgar Redis para resolverlo.
- [ ] Añadir una prueba de transición si el cambio afecta ese comportamiento.
- [ ] No reinterpretar automáticamente una fuente antigua como nueva evidencia:
  no tenemos documento/evidencia en esos enteros.

### Paso 5. Adaptación mínima a Streamlit

- [ ] **Paso 5 completado y comprobado.**

Esta parte no es una traducción de cambios Rails: no los hubo. El usuario ya
aprobó añadir el panel separado y mantener el Wizard actual. También decidió
no añadir una presentación del informe detallado que LIDR no muestra.
No implementar hasta aprobar el plan completo.

1. [ ] Conservar intacto el recorrido principal del RAG Wizard de sesión 10.
2. [ ] Añadir dentro de la pestaña RAG un panel secundario claramente separado:
   `Grounded RAG estimate`.
3. [ ] El panel enviará una transcripción al endpoint ya existente
   `POST /v1/estimate/from-transcript`, con `ESTIMATE_API_KEY`.
4. [ ] Streamlit seguirá siendo cliente HTTP: no importar el generador, abrir BD,
   consultar Redis o llamar al LLM desde este panel.
5. [ ] Mostrar por módulo/tarea:
   - [ ] nombre y descripción;
   - [ ] días estimados o `Insufficient source data`, sin convertir null en cero;
   - [ ] indicador declarado `grounded`;
   - [ ] chunk, documento y evidencia literal por fuente;
   - [ ] confianza, asunciones y explicación global de contexto insuficiente.
6. [ ] Conservar el JSON de respuesta y mostrar `X-Request-ID` para correlacionar
   con el informe real del backend.
7. [ ] Mostrar errores HTTP/transporte explícitos; no tratar un fallo como una
   estimación vacía válida.
8. [ ] Advertir que una respuesta con confianza baja requiere revisión.
9. [ ] No etiquetar una línea como `verified` solo porque el modelo devuelve
   `grounded=true`: el endpoint actual devuelve `Estimate`, no el contexto ni
   `CitationReport`. La comprobación efectiva se observa en logs y muestras
   de evaluación.
10. [ ] No inventar un informe local sin conocer `kept` ni añadir un panel de
    `CitationReport`. Mantener el informe detallado en logs y evaluación,
    conforme a la decisión 14; conservar el contrato HTTP de este endpoint.

Archivos previstos: [streamlit_app.py](../streamlit_app.py),
[wizard_ui.py](../src/wizard_ui.py) y su test existente. Reutilizar patrones HTTP
locales; no crear un cliente genérico ni un nuevo framework de interfaz.

### Paso 6. Construir el golden de generación

- [ ] **Paso 6 completado y comprobado.**

1. [ ] Copiar sin modificar su contenido
   `estimator/evals/golden_generation_s11.json` de la referencia correcta a
   `evals/golden_generation_s11.json` del alumno.
2. [ ] Mantener IDs y `query` idénticos a Q1-Q5 del golden de recuperación.
3. [ ] Mantener las transcripciones enriquecidas del instructor si se verifican
   contra sus consultas; no inventar requisitos nuevos.
4. [ ] Revisar cada `ground_truth` contra los presupuestos reales para conocer
   sus diferencias, sin modificar la referencia:

   - [ ] Q1: comprobar componentes, alcance, unidades y suma.
   - [ ] Q2: comprobar componentes, alcance, unidades y suma.
   - [ ] Q3: comprobar componentes, alcance, unidades y suma.
   - [ ] Q4: comprobar componentes, alcance, unidades y suma.
   - [ ] Q5: comprobar componentes, alcance, unidades y suma.

   | Query | Presupuesto principal | Total histórico | Equivalencia exacta |
   | --- | --- | ---: | ---: |
   | Q1 banca | BUD-2024-001 | 480 h | 60 días |
   | Q2 comercio | BUD-2024-005 | 460 h | 57.5 días |
   | Q3 telemedicina | BUD-2024-009 | 560 h | 70 días |
   | Q4 IoT | BUD-2024-013 | 500 h | 62.5 días |
   | Q5 pagos | BUD-2024-003 | 600 h | 75 días |

5. [ ] Conservar los totales aproximados de LIDR, incluidos 59 días para Q2 y
   76 para Q5, sin presentarlos como conversiones exactas de las horas.
6. [ ] Comprobar que el golden copiado coincide con el de la referencia
   `3292744` y que las diferencias conocidas siguen documentadas en
   [sesion11_porting_drift.md](sesion11_porting_drift.md).
7. [ ] Identificar las respuestas como referencias heredadas de LIDR y revisadas
   contra datos; no afirmar que el usuario o un experto las ha validado si no
   ocurrió.
8. [ ] No modificar el golden después de ver resultados para mejorar puntuaciones
   sin documentar una nueva versión de la baseline.
9. [ ] No copiar los resultados RAGAS del instructor como si fueran nuestros.

### Paso 7. Implementar el harness de recolección

- [ ] **Paso 7 completado y comprobado.**

Crear `scripts/eval_ragas_s11.py`, adaptando la referencia:

1. [ ] Resolver imports de nuestro layout `src`; no usar `app.*`.
2. [ ] Reutilizar dependencias y helpers existentes. El helper real es
   [scripts/s08/s08_common.py](../scripts/s08/s08_common.py#L41), no
   `scripts/s08_common.py` ni `scripts/s08/common.py`.
3. [ ] Separar recogida de muestras de scoring para repetir RAGAS sin volver a
   pagar generación.
4. [ ] Para Q1-Q5 ejecutar reformulación, embedding, búsqueda híbrida/reranking,
   truncado, ensamblado y generación con nuestras funciones compartidas.
5. [ ] Registrar la configuración real usada; la referencia usa umbral permisivo
   `1.2` para evaluar generación, no el soft-fail del endpoint.
6. [ ] No afirmar que esta configuración equivale a todos los defaults HTTP.
7. [ ] Verificar las citas sobre los chunks enviados al LLM.
8. [ ] Guardar pregunta, respuesta textual, contextos exactos y ground truth,
   además del informe de citación e identificadores de consulta.
9. [ ] Guardar procedencia de chunks y parámetros suficientes para explicar la
   ejecución; no inventar métricas o metadatos de coste no medidos.
10. [ ] El texto de respuesta debe incluir alcance, cifras/unidades, falta de datos,
    asunciones y razonamiento relevantes, sin omitir afirmaciones problemáticas
    para favorecer la puntuación.
11. [ ] Si una consulta no tiene contexto o falla, mostrarlo como fallo real.
    No sustituirla por ejemplos estáticos, eliminarla del promedio ni generar
    una tabla aparentemente completa.
12. [ ] Añadir `--collect-only PATH`, scoring de muestras guardadas y salida de
    informe. `--limit` puede servir para diagnóstico, pero no cumple la entrega.

### Paso 8. Configurar RAGAS sin copiar hacks por defecto

- [ ] **Paso 8 completado y comprobado.**

En [pyproject.toml](../pyproject.toml) y [uv.lock](../uv.lock):

1. [ ] Añadir a dependencias de desarrollo las dependencias de evaluación realmente
   necesarias. LIDR añadió `ragas` y `datasets`; ya tenemos `langchain-openai`.
2. [ ] Resolver con `uv`, no editar el lock a mano.
3. [ ] Verificar importaciones y compatibilidad real de versiones instaladas.
4. [ ] Instalar/restaurar solo después de cambiar el manifiesto o de un fallo real
   por dependencia ausente.

Advertencia de la referencia:

- Su documentación describe una incompatibilidad de `ragas 0.4.x` con una
  importación Vertex de `langchain-community`.
- `score_ragas_s11.py` introduce módulos ficticios en `sys.modules` para
  esquivarla y se ejecuta en un entorno separado.
- **No se ha reproducido ese fallo en el alumno.** No presentarlo como hecho
  local ni copiar los shims preventivamente.
- Preferir un conjunto de versiones compatible y verificable. Si hay conflicto
  demostrado, aislar solo el scorer con dependencias declaradas/reproducibles
  y explicar la causa; no degradar el entorno principal ni añadir mocks de
  proveedores para hacer pasar imports.

El scorer puede ser una parte del script o un archivo
`scripts/score_ragas_s11.py` si el aislamiento lo requiere. Mantener una única
implementación de cálculo/formato, no duplicar el código de tablas de LIDR.

Cálculo:

1. [ ] Juez OpenAI `gpt-4o-mini`, temperatura 0 donde la API lo permita.
2. [ ] Embeddings `text-embedding-3-small`.
3. [ ] Adaptar los cuatro nombres de entrada a la API de la versión elegida.
4. [ ] Calcular las cuatro métricas requeridas por consulta.
5. [ ] Validar que hay exactamente Q1-Q5, sin duplicados, con métricas finitas.
6. [ ] Una métrica ausente/NaN no es un cero: error explícito y baseline incompleta.
7. [ ] Promedio aritmético por columna sobre cinco consultas válidas.
8. [ ] Persistir JSON válido y tabla Markdown. No serializar `NaN` como si fuera
   JSON estándar ni promediar silenciosamente solo las filas válidas.
9. [ ] Registrar versión/modelos y conservar muestras para trazabilidad.
10. [ ] El scorer aislado debe recibir la clave por entorno o cargar la configuración
    de forma segura: no asumir que LangChain lee nuestro `.env` automáticamente.
    Nunca pedir al usuario que pegue la clave en el chat.

### Paso 9. Pruebas y demo offline

- [ ] **Paso 9 completado y comprobado.**

Este paso pertenece a la fase 1. Ejecutar aquí todas las comprobaciones posibles
sin infraestructura, incluida la demo. Antes de usar los comandos orientativos,
revisar fixtures, imports y hooks; separar los casos que requieren servicios
reales y documentarlos en la guía de fase 2, sin ejecutarlos ahora.

Preferir ampliar archivos existentes. Casos mínimos:

**Schema y verificador**

- [ ] Fuente válida y línea fundamentada.
- [ ] `grounded=True` sin fuentes: error Pydantic.
- [ ] `grounded=False` con fuentes: error.
- [ ] `grounded=False` con cifra, incluido cero: error.
- [ ] Línea sin datos con esfuerzo nulo: válida y clasificada `insufficient`.
- [ ] ID inventado en una línea: `dangling`.
- [ ] ID inventado solo en la cita global: también se detecta.
- [ ] Mezcla de líneas correctas, colgantes y sin datos; contadores y detalles.
- [ ] Chunk recuperado pero descartado por presupuesto: citarlo se detecta como
  colgante respecto al contexto realmente usado.

**Integración**

- [ ] Camino correcto, soft-fail sin generación e idempotencia conservados.
- [ ] Corrección de cita una vez.
- [ ] Persistencia del error: warning y confianza baja, como LIDR.
- [ ] Informe correlacionado por `request_id`.
- [ ] Respuesta final regenerada por coherencia no sale sin verificación.
- [ ] XML con documento y con distancia ausente; presupuesto sigue respetándose.
- [ ] Actualizar fixtures que antes usaban `sources=[1]`; ahora deben describir una
  fuente completa y `grounded=True`.

**Evaluación y Streamlit**

- [ ] Prueba offline de adaptación de muestra: los contextos corresponden a `kept`.
- [ ] Prueba de rechazo de métricas ausentes/no finitas y de tabla con promedio.
- [ ] Prueba de visualización de línea sin soporte y fuentes por línea.
- [ ] Regresión: el Wizard mantiene la edición humana y no permite confirmar horas
  ausentes; ya hay pruebas en
  [test_wizard_ui.py](../tests/test_wizard_ui.py).

- [ ] Añadir una demo offline equivalente a
  `scripts/demo_verify_citations_s11.py`: ejemplo determinista con fuente real,
  cita inventada y línea sin datos. Debe poder ejecutarse sin clave ni BD y
  terminar con un fallo visible si no detecta el caso inventado.

Archivos de tests existentes inspeccionados:

```text
tests/test_validation.py
tests/test_estimator.py
tests/test_context_assembler.py
tests/test_idempotency.py
tests/test_rag_runs.py
tests/test_task_hours.py
tests/test_task_hours_vector_validity.py
tests/test_wizard_ui.py
```

Comandos orientativos, desde el proyecto, ajustando la lista a archivos creados:

```bash
rtk proxy uv run --locked pytest \
  tests/test_validation.py tests/test_estimator.py \
  tests/test_context_assembler.py tests/test_idempotency.py \
  tests/test_rag_runs.py tests/test_task_hours.py \
  tests/test_task_hours_vector_validity.py tests/test_wizard_ui.py

rtk proxy uv run --locked ruff check <changed-python-files>
```

- [ ] Ejecutar las pruebas dirigidas, incluyendo los tests del harness si se
  crea un archivo nuevo, y registrar comando, resultado y evidencia.
- [ ] Ejecutar lint sobre los archivos Python cambiados y registrar el resultado.
  No ejecutar comandos con el marcador `<changed-python-files>` literalmente.
- [ ] Usar las herramientas de tipos existentes si las hay; no añadir un framework
  de type checking solo por este ejercicio. Ampliar a suite completa únicamente
  si las pruebas dirigidas o los cambios compartidos lo justifican.

### Paso 10. Preparar la guía autónoma y ejecutar manualmente la fase 2

- [ ] Guía autónoma completa, revisada offline y entregada en la fase 1.
- [ ] **Paso 10 completado: fase 2 ejecutada y comprobada por el usuario.**

**El asistente prepara; el usuario ejecuta.** No gastar llamadas de generación
o scoring de fondo mientras el usuario cree que solo se está preparando código.
La preparación de esta guía pertenece a la fase 1; las casillas de ejecución
siguientes quedan pendientes hasta que el usuario las complete manualmente.
La guía final debe quedar en este documento, con enlaces relativos a los
apartados necesarios del README, y cumplir el formato de la sección 0.2.
La lista y los comandos previstos siguientes son el alcance que debe
concretarse tras implementar, no una guía manual ya terminada.

Secuencia manual que debe concretar la guía:

1. [ ] Explicar qué se va a probar y qué llamadas/coste implica.
2. [ ] Usar el montaje aprobado en la decisión 16: Compose para API, PostgreSQL
   y Redis, y Streamlit en host. Comprobar su estado sin cambiar de instancia.
   Seguir los comandos de arranque del README, sin sustituirlos por una receta
   propia; ver sección 4.6 y la corrección solicitada por el usuario.
3. [ ] Comprobar salud de API y configuración de acceso sin revelar claves,
   con comandos, respuestas esperadas y acciones ante fallos documentados.
4. [ ] Verificar conexión a PostgreSQL y el corpus presupuestario cargado mediante
   consultas de solo lectura. No deducirlo de que el JSON existe en disco.
5. [ ] Si falta corpus, ejecutar la ingesta idempotente documentada con
   [query_examples.py](../scripts/query_examples.py) o el helper existente
   apropiado. Avisar de que también ejecuta búsquedas de smoke; no borrar nada.
6. [ ] No cargar las tareas sintéticas del Wizard como sustituto del corpus
   presupuestario Q1-Q5.
7. [ ] Tener presente que el evaluador directo usa la configuración de proceso y la
   BD del host; no basta con que el contenedor tenga acceso a su hostname.
8. [ ] La configuración de Compose inspeccionada publica PostgreSQL en 5432,
   API en 8000, Redis en 6379 y Streamlit se ejecuta en host. No copiar el
   puerto 5433 de las notas del instructor como si fuera el nuestro.
9. [ ] Las migraciones ya se ejecutan en el arranque de Compose. No proponer
   recrear servicios ni aplicar migraciones como paso inocuo sin revisar.
10. [ ] Consultar la evidencia de la demo ya ejecutada en fase 1 y la
    explicación documentada de los tres estados. Repetirla solo si quedó
    bloqueada o cambió el código, indicando el motivo.
11. [ ] Ejecutar el panel de Streamlit con una transcripción y correlacionar el
    `X-Request-ID` con los logs del backend.
12. [ ] Ejecutar recolección de Q1-Q5 y revisar una muestra completa, especialmente
    IDs, evidencia, unidades y contextos.
13. [ ] Ejecutar scoring de ese mismo archivo, sin regenerar respuestas.
14. [ ] Revisar las cinco filas, promedios y errores. Si hay NaN, no declarar éxito.
    - [ ] Q1: comprobar las cuatro métricas finitas y su muestra.
    - [ ] Q2: comprobar las cuatro métricas finitas y su muestra.
    - [ ] Q3: comprobar las cuatro métricas finitas y su muestra.
    - [ ] Q4: comprobar las cuatro métricas finitas y su muestra.
    - [ ] Q5: comprobar las cuatro métricas finitas y su muestra.
    - [ ] Promedio: comprobar las cuatro medias sobre las cinco consultas.
15. [ ] Guardar los resultados propios y completar la nota de hallazgos siguiendo
    una plantilla preparada en fase 1, con instrucciones para interpretar los
    números sin IA y sin inventar conclusiones.

Comandos previstos después de implementar y verificar el harness:

```bash
# Desde /home/basf/wsTakeoff/ai-engineering/estimador-cag
rtk proxy uv run --locked python scripts/eval_ragas_s11.py \
  --collect-only evals/ragas_samples_s11.json

rtk proxy uv run --locked python scripts/eval_ragas_s11.py \
  --score-file evals/ragas_samples_s11.json \
  --out evals/ragas_baseline_s11.json
```

Si el scorer finalmente requiere aislamiento, sustituir el último comando por
el ejecutable/entorno documentado y probado. No presentar esa ruta como decidida
antes de resolver dependencias.

El primer uso del reranker puede descargar su modelo y consumir tiempo/memoria.
No confundir esa descarga o su calentamiento con un bloqueo de RAGAS.

### Paso 11. Documentación, resultados y entrega

- [ ] **Paso 11 completado y comprobado.**

1. [ ] Actualizar el README solo en los apartados directamente afectados:
   nuevo resultado, uso de UI, evaluación y límites.
2. [ ] Crear `evals/RAGAS_BASELINE_S11.md` con:
   - [ ] configuración y procedencia del golden;
   - [ ] comandos reales utilizados;
   - [ ] tabla propia Q1-Q5 más promedio;
   - [ ] resumen de informes de citas;
   - [ ] nota de 2-3 frases basada en nuestros números;
   - [ ] desviaciones respecto a Responses API y rechazo estricto;
   - [ ] diferencias efectivas respecto a la referencia, si las hay.
3. [ ] Guardar muestras e informe JSON en las rutas documentadas, sin secretos.
   Revisar su contenido antes de proponer incluirlos en Git.
4. [ ] No generar una tabla ficticia si el usuario aún no ha ejecutado el scorer.
   Dejar estado explícitamente pendiente.
5. [ ] Revisar el diff final, tests y worktree; no incluir `src/alembic.ini`.
6. [ ] Dejar la revisión al usuario. No hacer commit.

Preparar en fase 1 el README, las instrucciones y la estructura de los informes,
sin datos ficticios. Completar resultados, tabla y hallazgos únicamente después
de la ejecución manual de fase 2. El cierre offline debe enumerar las
validaciones superadas, los bloqueos y todos los criterios online pendientes.

## 7. Baseline de LIDR: contexto, no objetivo ni resultado nuestro

La documentación de la referencia contiene esta tabla:

| Query | faithfulness | answer_relevancy | context_precision | context_recall |
| --- | ---: | ---: | ---: | ---: |
| Q1 | 0.418 | 0.000 | 1.000 | 0.000 |
| Q2 | 0.426 | 0.061 | 1.000 | 0.000 |
| Q3 | 0.564 | 0.000 | 1.000 | 0.571 |
| Q4 | 0.877 | 0.000 | 1.000 | 0.000 |
| Q5 | 0.476 | 0.104 | 1.000 | 0.000 |
| Promedio | 0.552 | 0.033 | 1.000 | 0.114 |

También declara 169 líneas, 116 fundamentadas, ninguna colgante y 53 sin datos.
Son resultados documentados por el instructor; **no los hemos reproducido**.

Sus notas atribuyen problemas a formato declarativo de la pregunta, desajustes
horas/días y descomposición fina del esfuerzo. Esas explicaciones son
interpretaciones de su informe, no causas demostradas en nuestro pipeline.
Nuestra nota debe distinguir observación de hipótesis y no repetirlas como
diagnóstico antes de ver las muestras propias.

Un ID real no demuestra que la estimación esté bien sustentada. Por eso pueden
coexistir cero IDs inventados y faithfulness baja. Este pre-work debe explicar
la diferencia, no prometer que el verificador referencial resuelve la
alucinación semántica.

## 8. Fuera de alcance expresamente

No portar desde `8695e8b`:

- `quality/hallucination.py` ni juez semántico de líneas.
- `quality/augmentation.py`, compresión o edge-loading.
- `quality/synthesis.py` ni rangos de horas ante contradicciones.
- Nuevos toggles/modelos de esas tres funcionalidades en Ajustes o Redis.
- `eval_generation_s11.py`, regression gate, monitor o compare de configuraciones.
- Corpus de contradicciones y su generador.
- Indexación incremental, jobs, `/embeddings/index/*` y estadísticas de índices.
- Migración HNSW multi-índice de sesión 11.

Tampoco:

- Reescribir la búsqueda avanzada de sesión 10.
- Unificar a la fuerza el generador fundamentado y el Wizard.
- Cambiar la tecnología de UI o añadir Rails.
- Refactorizar el wrapper compartido para Responses API.
- Cambiar todos los contratos de esfuerzo del proyecto a horas o floats.
- Arreglar problemas antiguos no relacionados.
- Declarar que tenemos una baseline antes de la ejecución real del usuario.

## 9. Criterios de cierre verificables

- [ ] Plan revisado y aprobado; correcciones del usuario incorporadas.
- [ ] Referencia comprobada: `session_11` / `3292744`.
- [ ] Cada tarea fundamentada tiene fuentes tipadas.
- [ ] Tarea no fundamentada no puede tener fuentes ni esfuerzo numérico.
- [ ] XML propaga documento sin romper distancias ausentes ni truncado.
- [ ] Prompt exige ID exacto y evidencia literal, conservando el tratamiento
      de unidades de LIDR sin la modificación rechazada.
- [ ] Verificador detecta el ID inventado y el ID de un chunk descartado.
- [ ] Verifica también citas globales.
- [ ] Logs iniciales/finales se correlacionan por `request_id`.
- [ ] Se conserva el comportamiento de LIDR ante citas persistentes y se explica
      que es confianza baja, no rechazo HTTP.
- [ ] La respuesta final no evade la verificación por una reparación posterior.
- [ ] CAG, conversaciones y Wizard previo mantienen su comportamiento.
- [ ] Streamlit muestra fuentes y falta de datos sin afirmar garantías que no recibe.
- [ ] Golden Q1-Q5 trazable, con referencias revisadas y Q6-Q8 intactas.
- [ ] Muestras propias contienen los cuatro campos y el contexto realmente usado.
- [ ] Dependencias/imports de RAGAS probados, sin shims preventivos.
- [ ] Tests dirigidos y lint de cambios pasan.
- [ ] Fase 1: implementación completa y validaciones sin servicios registradas.
- [ ] Fase 1: guía manual autónoma de fase 2 entregada, con resultados esperados,
      acciones ante fallos y advertencias, sin dependencia de IA.
- [ ] Fase 2: usuario ejecutó generación y scoring siguiendo la guía autónoma.
- [ ] Cinco consultas, cuatro métricas finitas cada una y promedio correcto.
- [ ] Tabla, informe y nota propios persistidos.
- [ ] Desviación de Responses API documentada.
- [ ] Ningún secreto, dato ajeno o archivo no rastreado previo incluido.
- [ ] Ningún commit sin autorización.

## 10. Incertidumbres que siguen abiertas

No se han verificado aún:

- [ ] Disponibilidad y permisos de credenciales/modelos.
- [ ] Servicios en ejecución y quién los utiliza.
- [ ] Corpus realmente cargado, duplicados y metadatos de los chunks persistidos.
- [ ] Versiones efectivas y compatibilidad de RAGAS en el entorno del alumno.
- [ ] Importaciones, tests, lint, ejecución de Streamlit y resultados reales.
- [ ] Coste y duración de una evaluación completa.

Para la revisión del plan, las propuestas que merecen atención especial son:

1. [x] Revisar y aceptar o corregir el panel secundario de estimación fundamentada
   en Streamlit, sin alterar el Wizard.
   Evidencia: el usuario respondió «si es asi lo entiendo, la respuesta seria 1»
   el 17 de noviembre de 2026. Condición comprobada en
   [rag_estimate.py](../src/routers/rag_estimate.py#L29) y mediante búsqueda de
   los usos del endpoint en el cliente: existe en la API, pero Streamlit no lo
   llama. Ver decisión 13 de la sección 2.1.
2. [x] Revisar y aceptar o corregir la propuesta de mantener el informe detallado
   en logs/evaluación mientras el endpoint siga devolviendo `Estimate`; mostrar
   citas y request ID en UI sin verificación ficticia.
   Evidencia: decisión condicional del usuario «los muestra lidr? si si, si.
   si no, no», resuelta leyendo `GenerationView`, la vista de generación Rails
   y buscando los campos del informe en ambos clientes de referencia.
   La API sí lo devuelve; las pantallas no presentan el nuevo informe completo.
   Ver decisión 14 de la sección 2.1.
3. [x] Resolver la propuesta de corregir las aproximaciones del golden y añadir
   una aclaración de 8 horas/día al prompt.
   Evidencia: el usuario eligió «el 2» (conservar literalmente las cifras y
   el criterio de LIDR, sin ese ajuste) y pidió registrarlo en
   [sesion11_porting_drift.md](sesion11_porting_drift.md).
   Ver decisión 15 de la sección 2.1. La propuesta queda rechazada y los pasos
   de implementación se han actualizado para no aplicarla.

No son bloqueos para redactar este plan. Sí deben quedar aceptadas o corregidas
en su revisión antes de tratarlas como instrucciones de implementación.
