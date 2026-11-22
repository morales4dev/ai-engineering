# Pre-sesión 11: estado del trabajo y guía de ejecución

## 0. Estado actual y qué hacer ahora

El plan está aprobado. El código de citación por
línea, el golden, los scripts y la guía manual están implementados. Las pruebas
offline de esa implementación figuran en la sección 11.

El generador fundamentado usa Responses API a través del wrapper compartido
y del agregador LiteLLM. Los demás recorridos
conservan Instructor/LiteLLM. El alcance y las comprobaciones de este ajuste
figuran en los pasos 4 y 9 y en el cierre offline.

**Todavía no se ha ejecutado la fase 2 ni existe una tabla propia de métricas.**
El lock y los imports reales del scorer siguen pendientes. El usuario ha
confirmado que resolverá las dependencias o versiones si resulta necesario.

Para continuar, sigue la [guía manual del apartado 10.1](#101-guía-manual-empezar-aquí).
No hay que volver a aprobar el plan ni repetir por defecto las pruebas ya
superadas. Las casillas indican qué se ha comprobado y qué falta comprobar.
Las secciones de contexto y decisiones explican el alcance; no son pasos que
debas repetir. La sección 11 distingue las evidencias de cada implementación, para no
confundir una comprobación anterior con una validación del código actual.

No hacer commit ni añadir archivos al índice: el usuario quiere revisar primero.

### 0.1 Seguimiento persistente y verificable por una persona

Una casilla marcada acredita la comprobación que figura junto a ella. Si el
código cambia, hay que validar de nuevo lo afectado y registrar la nueva
evidencia; una prueba antigua no demuestra que una modificación posterior pase.

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

La separación depende de si se necesitan
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

En la revisión inicial había un archivo no rastreado ajeno al trabajo,
[src/alembic.ini](../src/alembic.ini), que se respetó. Antes de editar, comprobar
el estado actual de Git y conservar los cambios del usuario.

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
6. **Decisión vigente:** usar `litellm.responses` en el método nuevo del wrapper
   compartido y llamarlo únicamente desde `_generate`
   del generador fundamentado. Conservar Instructor/LiteLLM para el reformulador,
   el Wizard y los demás consumidores. No evitar el wrapper ni el agregador.
   Usar Responses nativa de OpenAI, sin puente a Chat Completions, con esquema
   estricto y validación Pydantic local. Esta elección difiere del método
   `client.responses.parse` exigido literalmente por el enunciado.
7. Para las citaciones colgantes, seguir el comportamiento de LIDR, descrito en
   la sección 5. No introducir por nuestra cuenta un rechazo HTTP distinto.
8. Las llamadas de pago están autorizadas, **pero el usuario quiere ejecutarlas
   personalmente para aprender**. La autorización no es una orden para que el
   asistente las ejecute en su lugar.
9. Entregar instrucciones de ejecución real paso a paso, autónomas y verificables.
   El usuario ejecutará la fase 2
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
    mantener el Wizard actual sin cambios. El usuario eligió la opción 1
    condicionada a que esa función existiera solo
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
    y Streamlit aparte en esta misma máquina. Confirmado por el usuario.
    No crear otro despliegue
    ni otra base de datos para este ejercicio. Los pasos de ejecución deben
    concretar las rutas/conexiones de ese montaje, no pedir elegir entorno
    durante la implementación.

La fase 1 está aprobada, incluido el ajuste de Responses.
La fase 2 sigue reservada a la ejecución manual del usuario.

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

- [x] Mantener `name` y `description`.
- [x] Mantener esfuerzo en `engineer_days`, como el modelo actual y LIDR.
- [x] Permitir esfuerzo nulo cuando no hay soporte.
- [x] Añadir `grounded: bool`.
- [x] Sustituir `sources: list[int]` por `sources: list[SourceReference]`.
- [x] `grounded=True` exige al menos una fuente.
- [x] `grounded=False` exige fuentes vacías y esfuerzo nulo.
- [x] No representar falta de datos mediante cero días.
- [x] Mantener las asunciones y la política global de contexto insuficiente.

Evidencia de este contrato: `TaskItem._grounding_integrity` y las pruebas de
`tests/test_validation.py`, incluidos rechazo de cero y clasificación sin datos.

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

1. [x] Schema, prompt y función verificadora. Evidencia: pasos 2-4 y tests.
2. [x] Golden de generación Q1-Q5 con respuestas de referencia. Evidencia: paso 6.
3. [x] Script de evaluación, muestras trazables y tabla de cinco filas más promedio.
4. [x] Nota propia de 2-3 frases sobre los resultados reales.

No dar por terminado el apartado de métricas hasta tener las cuatro métricas
numéricas para las cinco consultas y sus promedios.

## 4. Arquitectura del alumno y correspondencia con LIDR

### 4.1 Generación y contratos

| Archivo alumno | Hecho comprobado |
| --- | --- |
| [schemas.py](../src/generation/rag/schemas.py) | `TaskItem` tiene `engineer_days: int \| None`, `grounded` obligatorio y `sources: list[SourceReference]`, con validación de integridad. |
| [schemas.py](../src/generation/rag/schemas.py) | Se conserva `SourceCitation` global con `source_id: int`, `relevance` y `used_for`. |
| [schemas.py](../src/generation/rag/schemas.py) | `Estimate` conserva módulos, totales, asunciones, confianza y explicación de contexto insuficiente. |
| [schemas.py](../src/generation/rag/schemas.py) | `GenerateResult` no tiene consumidores ni un router de etapas registrado; no se ha ampliado. |
| [estimator.py](../src/generation/rag/estimator.py) | Generación y orquestación del flujo RAG fundamentado, a través del wrapper compartido. |
| [validation.py](../src/generation/rag/validation.py) | `verify_citations` comprueba citas por línea y globales y distingue líneas fundamentadas, colgantes y sin datos. |
| [prompt_builder.py](../src/generation/rag/prompt_builder.py) | Exige `SourceReference`, `grounded`, IDs exactos y evidencia literal; prohíbe cifras para tareas sin soporte. |
| [context_assembler.py](../src/generation/rag/context_assembler.py) | Cada fuente incluye ID, documento, sector, año, tipo y distancia; falla si no hay procedencia documental. |

Nuestro `RetrievedChunk.id` es un entero de base de datos. El ID trazable de
presupuesto viaja en `budget_id`, y existe `source_id` genérico opcional.
No confundir esos campos con `SourceCitation.source_id`, que es el ID numérico
del chunk. En las nuevas referencias usar `chunk_id=str(chunk.id)`.

LIDR expone `document_id = chunk.source_id or chunk.budget_id or "unknown"` en el
XML. El alumno conserva esa prioridad, pero falla cuando faltan ambos IDs:
`"unknown"` no prueba procedencia. La comprobación de metadatos persistidos
sigue pendiente de fase 2.

Nuestro ensamblador conserva `distance=None` con `not-scored` y el modelo lleva
`has_vector_distance`; esa compatibilidad está cubierta por pruebas offline.

### 4.2 Wrapper compartido y Responses API

[LLMWrapper](../src/services/llm_wrapper.py) conserva sus métodos anteriores:

```text
instructor.from_litellm(litellm.completion)
    -> chat.completions.create_with_completion(...)
    -> response_model de Pydantic
```

El método nuevo, `complete_structured_responses`, usa:

```text
litellm.responses(text_format=Estimate, custom_llm_provider="openai")
    -> OpenAI /v1/responses, sin puente a Chat Completions
    -> text.format con json_schema y strict=true
    -> output_text validado con Estimate.model_validate_json
```

Solo `_generate` del flujo fundamentado llama a ese método. Conserva el modelo
configurado, timeout, delimitación de contenido no confiable, logs y formato de
metadatos. Traduce `max_tokens` a `max_output_tokens` y el esfuerzo a
`reasoning.effort`. Usa la clave OpenAI y falla explícitamente si se configura
otro proveedor; no hace fallback a Instructor. Se desactiva el puente a Chat
Completions y se impide descartar silenciosamente parámetros.

Los errores de validación Pydantic permiten hasta seis intentos, con información
de corrección y sin inventar datos. Una respuesta no completada, rechazada o sin
resultado estructurado no se devuelve como estimación válida. Los reintentos de
citación/coherencia del orquestador siguen siendo un mecanismo separado.

Tokens y coste describen la respuesta exitosa, igual que en el método anterior.
Los intentos que fallan la validación local registran su uso reportado y coste
estimado por separado; no se consideran gratuitos ni se suman silenciosamente
al resultado final. Los errores de proveedor se propagan mediante LiteLLM.

El esquema estricto se comprueba offline inspeccionando la petición HTTP que
genera LiteLLM. La aceptación del modelo configurado y una generación
real quedan pendientes de fase 2. Ninguna API demuestra por sí sola que una
citación sea verdadera: se mantiene `verify_citations`.

Se conserva la API Responses requerida, pero no el método cliente literal
`client.responses.parse`. La diferencia está aceptada para mantener el agregador:
LiteLLM solicita el esquema estricto y el wrapper valida explícitamente con
Pydantic.

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

### 4.6 Arranque aprobado y comprobación histórica del entorno

Comprobación de solo lectura durante la preparación:

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

**El procedimiento aprobado es el del README:** Compose para el montaje
completo y Streamlit en host. No sustituirlo por un arranque parcial ni cambiar
a `docker-compose` por el fallo histórico de la consulta anterior. El diagnóstico
de errores de arranque está en la guía 10.1.D.

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
permisos reales de modelos. La guía del paso 10 permite comprobarlo sin IA;
no hace falta compartir salidas en un chat.

## 5. Política exacta de citaciones y sus límites

### 5.1 Comportamiento que seguiremos de LIDR

En el pipeline completo:

1. [x] Verificar contra **los chunks conservados tras truncar**, no todos los
   candidatos recuperados.
2. [x] Registrar el informe con `request_id`.
3. [x] Si hay IDs colgantes, pedir una corrección al generador.
4. [x] Verificar la respuesta corregida.
5. [x] Si persisten, warning `citations_unrepaired` y `confidence="low"`.
6. [x] Mantener el guard de coherencia; si una reparación posterior regenera la
   estimación, verificar también la respuesta final para no devolver otra
   generación sin comprobar.

Evidencia: pruebas aisladas de `test_estimator.py` sobre reintento acotado,
logs inicial/final, ID descartado y regeneración por coherencia.

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

## 6. Seguimiento de implementación y comprobaciones

### Paso 1. Revalidar estado y hacer inventario de afectados

- [x] **Paso 1 completado y comprobado.** Evidencia: `git status`, `git log`,
  referencias de `TaskItem` y búsquedas de consumidores en Python.

1. [x] Comprobar que seguimos en las ramas y commits de la sección 1.
2. [x] Revisar cambios nuevos del usuario y no revertirlos.
3. [x] Buscar referencias a `TaskItem`, `task.sources`, `engineer_days`,
   `validate_citations`, `GenerateResult` y deserializaciones de `Estimate`.
4. [x] Leer los tests afectados antes de cambiar contratos.
5. [x] No modificar infraestructura, modelos de BD, migraciones ni recuperación
   avanzada salvo dependencia demostrada del cambio.
   Dependencia encontrada y reproducida: la recuperación básica perdía los IDs
   documentales de transcripciones/docs. Se añaden solo esos metadatos en
   `retriever.py` y `retrieval/search_pipeline.py`, sin tocar ranking o filtros.

Las búsquedas de implementación localizaron consumidores directos en
[test_estimator.py](../tests/test_estimator.py) y
[test_validation.py](../tests/test_validation.py), además del orquestador.

### Paso 2. Extender los modelos Pydantic

- [x] **Paso 2 completado y comprobado.** Evidencia: `schemas.SourceReference`,
  `TaskItem._grounding_integrity`, `CitationReport` y `tests/test_validation.py`.

En [schemas.py](../src/generation/rag/schemas.py):

1. [x] Añadir `SourceReference`.
2. [x] Cambiar `TaskItem` conservando la estructura módulos/tareas:
   `engineer_days: int | None`, `grounded` y fuentes tipadas.
3. [x] Añadir un `model_validator(mode="after")` para las tres reglas de integridad.
4. [x] Añadir `LineCitation` y `CitationReport`, con los campos y estados de LIDR:
   contadores, IDs citados/colgantes, detalle por módulo/tarea y `has_dangling`.
5. [x] Mantener `SourceCitation` global y `Estimate` globalmente insuficiente.
6. [ ] Actualizar contratos dependientes solo si tienen consumidores reales. Si se
   adapta `GenerateResult`, cambiar los IDs colgantes a strings y contemplar el
   informe opcional como LIDR, sin añadir endpoints muertos.
   No aplica: `GenerateResult` no tiene consumidores; se conserva sin ampliarlo.
7. [x] No convertir el Wizard de sesión 10 a este modelo.

Conservar días enteros como LIDR evita ampliar el cambio a unidades nuevas.
Conservar también el texto y las aproximaciones del golden de LIDR, conforme a
la decisión 15. No reescribirlo con equivalencias exactas.

### Paso 3. Propagar documento y reforzar el prompt

- [ ] **Paso 3 completado y comprobado.**
  En curso: implementación y contratos offline comprobados en
  `test_context_assembler.py`; falta comprobar metadatos de la BD real en fase 2.

En [context_assembler.py](../src/generation/rag/context_assembler.py):

1. [x] Añadir `document_id` al `<source>`, usando `source_id` o `budget_id`;
   si faltan ambos se lanza `RetrievalError`, sin identificador ficticio.
2. [x] Conservar soporte de distancia ausente.
3. [x] Conservar chunks completos y presupuesto calculado sobre el XML envuelto:
   el atributo nuevo también consume tokens.
   Evidencia: prueba del límite exacto, incluidos los separadores entre chunks.
4. [ ] Verificar procedencia en nuestros resultados reales de presupuestos.

En [prompt_builder.py](../src/generation/rag/prompt_builder.py):

1. [x] Definir explícitamente que cada tarea es una línea.
2. [x] Exigir `grounded=true`, referencias exactas y evidencia literal si hay soporte.
3. [x] Exigir `grounded=false`, `engineer_days=null` y fuentes vacías si no lo hay.
4. [x] Pedir que se explicite el alcance sin soporte en las asunciones.
5. [x] Mantener contexto global insuficiente y suma de tareas fundamentadas.
6. [x] Conservar el tratamiento de unidades del prompt de LIDR; no añadir una
   instrucción propia de conversión a días de 8 horas, conforme a la decisión 15.
7. [x] Conservar la descomposición actual; no optimizar el prompt para inflar RAGAS.
   Evidencia de 1-7: `prompt_builder.build_system_prompt`.

La propuesta de aclarar adicionalmente las unidades fue rechazada por el usuario
para conservar el criterio de LIDR. El motivo y el riesgo están documentados en
[sesion11_porting_drift.md](sesion11_porting_drift.md).

### Paso 4. Implementar verificador, integración y observabilidad

- [x] **Paso 4 completado y comprobado.** Evidencia: pruebas de verificador,
  reintento, coherencia, request ID, contexto truncado e idempotencia.

En [validation.py](../src/generation/rag/validation.py):

1. [x] Implementar `verify_citations` como función pura.
2. [x] Recorrer módulos/tareas y clasificar cada línea.
3. [x] Agregar citas globales a la detección de IDs inventados.
4. [x] Ordenar y deduplicar IDs colgantes; no deduplicar los contadores de
   referencias si se sigue la semántica de LIDR.
5. [x] Resolver los consumidores de `validate_citations`: sustituirlos; mantener un
   adaptador solo si quedan usos reales que lo necesiten.
   No se conserva adaptador: no quedan consumidores.
6. [x] Mantener `check_coherence`.

En [estimator.py](../src/generation/rag/estimator.py):

1. [x] Usar los IDs de `kept` y la política de la sección 5.
2. [x] Registrar informe inicial y resultado final si hubo regeneración, para que
   el log no muestre solo una versión descartada.
3. [x] Mantener `request_id` de HTTP o generar uno en ejecución no HTTP.
4. [x] Conservar selección de modelo, reasoning, techo de tokens, hilo de trabajo,
   errores, soft-fail e idempotencia.
5. [x] No añadir el gate semántico de la sesión completa.

**Ajuste de Responses desde el wrapper**

- [x] Añadir `LLMWrapper.complete_structured_responses` sin modificar las
  interfaces anteriores de Instructor/LiteLLM.
  Evidencia: LiteLLM real con HTTP local y prueba de ambos métodos anteriores.
- [x] Usarlo desde `_generate`, incluidas las reparaciones del orquestador y la
  generación que reutiliza el evaluador, manteniendo las firmas públicas.
  Evidencia: pruebas de presupuesto, feedback, error y reintentos en `test_estimator.py`.
- [x] Comprobar formato estricto, protección del prompt, parámetros, parsing,
  reintentos acotados, errores y metadatos.
  Evidencia: `tests/test_llm_wrapper.py`, con LiteLLM 1.103.0 y `httpx.MockTransport`;
  se comprueba `/v1/responses` y el JSON estricto que recibe el transporte.
- [x] Revalidar offline los caminos afectados.
  Evidencia: 98 tests y Ruff dirigido superados; comando en la sección 11.
- [ ] Verificar una generación con el modelo real en fase 2, siguiendo F y G.

Compatibilidad de caché:

- [idempotency.py](../src/generation/rag/idempotency.py#L56) deserializa `Estimate`.
  Una entrada antigua con fuentes enteras ya no cumple el schema nuevo.
- Su código actual trata errores de deserialización como miss y elimina solo
  la clave concreta. No purgar Redis para resolverlo.
- [x] Añadir una prueba de transición si el cambio afecta ese comportamiento.
  Evidencia: `test_legacy_cached_sources_invalidate_only_that_key`, con fakeredis.
- [x] No reinterpretar automáticamente una fuente antigua como nueva evidencia:
  no tenemos documento/evidencia en esos enteros.

### Paso 5. Adaptación mínima a Streamlit

- [x] **Paso 5 implementado y comprobado offline.** Evidencia:
  `wizard_ui.render_grounded_estimate`, llamada separada en `streamlit_app.py`,
  AppTest de fuentes/null/request ID/error HTTP y regresión del Wizard.
  La comprobación de interfaz contra la API real queda en fase 2.

El panel separado está aprobado e implementado, sin cambiar el Wizard ni
añadir una presentación del informe detallado que LIDR no muestra.

1. [x] Conservar intacto el recorrido principal del RAG Wizard de sesión 10.
2. [x] Añadir dentro de la pestaña RAG un panel secundario claramente separado:
   `Grounded RAG estimate`.
3. [x] El panel enviará una transcripción al endpoint ya existente
   `POST /v1/estimate/from-transcript`, con `ESTIMATE_API_KEY`.
4. [x] Streamlit seguirá siendo cliente HTTP: no importar el generador, abrir BD,
   consultar Redis o llamar al LLM desde este panel.
5. [x] Mostrar por módulo/tarea:
   - [x] nombre y descripción;
   - [x] días estimados o `Insufficient source data`, sin convertir null en cero;
   - [x] indicador declarado `grounded`;
   - [x] chunk, documento y evidencia literal por fuente;
   - [x] confianza, asunciones y explicación global de contexto insuficiente.
6. [x] Conservar el JSON de respuesta y mostrar `X-Request-ID` para correlacionar
   con el informe real del backend.
7. [x] Mostrar errores HTTP/transporte explícitos; no tratar un fallo como una
   estimación vacía válida.
8. [x] Advertir que una respuesta con confianza baja requiere revisión.
9. [x] No etiquetar una línea como `verified` solo porque el modelo devuelve
   `grounded=true`: el endpoint actual devuelve `Estimate`, no el contexto ni
   `CitationReport`. La comprobación efectiva se observa en logs y muestras
   de evaluación.
10. [x] No inventar un informe local sin conocer `kept` ni añadir un panel de
    `CitationReport`. Mantener el informe detallado en logs y evaluación,
    conforme a la decisión 14; conservar el contrato HTTP de este endpoint.

Evidencia común de 1-10: `render_grounded_estimate`, llamada en el desplegable
de `streamlit_app.py`, `test_grounded_panel_uses_http_and_displays_sources_and_missing_data`,
`test_grounded_panel_http_error_is_not_an_empty_estimate` y pruebas previas del Wizard.

Archivos afectados: [streamlit_app.py](../streamlit_app.py),
[wizard_ui.py](../src/wizard_ui.py) y su test existente. Reutilizar patrones HTTP
locales; no crear un cliente genérico ni un nuevo framework de interfaz.

### Paso 6. Construir el golden de generación

- [x] **Paso 6 completado y comprobado.** Evidencia: `cmp` del golden del alumno
  y del instructor sin diferencias; lectura de las cinco referencias y contraste
  con componentes/horas del corpus mediante Python local. Q6-Q8 no se modifican.

1. [x] Copiar sin modificar su contenido
   `estimator/evals/golden_generation_s11.json` de la referencia correcta a
   `evals/golden_generation_s11.json` del alumno.
2. [x] Mantener IDs y `query` idénticos a Q1-Q5 del golden de recuperación.
3. [x] Mantener las transcripciones enriquecidas del instructor si se verifican
   contra sus consultas; no inventar requisitos nuevos.
4. [x] Revisar cada `ground_truth` contra los presupuestos reales para conocer
   sus diferencias, sin modificar la referencia:

   - [x] Q1: AUTH/PSD2/TXN/NOTIF; 120+160+140+60=480 h; redondeos suman 61 d.
   - [x] Q2: CATALOG/CART/RECO/STORE; 150+140+110+60=460 h; referencia ~59 d.
   - [x] Q3: FHIR/APPT/VIDEO/CONSENT; 190+150+160+60=560 h; redondeos suman 71 d.
   - [x] Q4: TELE/PRED/SCADA; 170+200+130=500 h; referencia ~62 d.
   - [x] Q5: GATE/FRAUD/RECON/DASH; 220+200+120+60=600 h; referencia ~76 d.

   | Query | Presupuesto principal | Total histórico | Equivalencia exacta |
   | --- | --- | ---: | ---: |
   | Q1 banca | BUD-2024-001 | 480 h | 60 días |
   | Q2 comercio | BUD-2024-005 | 460 h | 57.5 días |
   | Q3 telemedicina | BUD-2024-009 | 560 h | 70 días |
   | Q4 IoT | BUD-2024-013 | 500 h | 62.5 días |
   | Q5 pagos | BUD-2024-003 | 600 h | 75 días |

5. [x] Conservar los totales aproximados de LIDR, incluidos 59 días para Q2 y
   76 para Q5, sin presentarlos como conversiones exactas de las horas.
6. [x] Comprobar que el golden copiado coincide con el de la referencia
   `3292744` y que las diferencias conocidas siguen documentadas en
   [sesion11_porting_drift.md](sesion11_porting_drift.md).
7. [x] Identificar las respuestas como referencias heredadas de LIDR y revisadas
   contra datos; no afirmar que el usuario o un experto las ha validado si no
   ocurrió.
8. [x] No modificar el golden después de ver resultados para mejorar puntuaciones
   sin documentar una nueva versión de la baseline.
9. [x] No copiar los resultados RAGAS del instructor como si fueran nuestros.
   Evidencia de 5-9: comparación literal, nota de drift e informe de preparación
   sin tabla numérica propia.

### Paso 7. Implementar el harness de recolección

- [x] **Paso 7 implementado y comprobado offline.** Evidencia:
<<<<<<< HEAD
  `scripts/eval_ragas_s11.py` y `tests/test_eval_ragas_s11.py`, incluyendo contexto
  retenido, integridad de muestras y persistencia de resultados válidos.
  No se ha ejecutado recolección real.

=======
  `scripts/eval_ragas_s11.py` y `tests/test_ragas_evaluation.py`, incluyendo contexto
  retenido, integridad de muestras y persistencia de resultados válidos.
  No se ha ejecutado recolección real.

  El test se renombró desde `test_eval_ragas_s11.py`; los comandos históricos
  conservan el nombre que tenía cuando se ejecutaron.

>>>>>>> 028ade7 (Merge branch 'sesion_11_forense')
Implementación de `scripts/eval_ragas_s11.py`, adaptada de la referencia:

1. [x] Resolver imports de nuestro layout `src`; no usar `app.*`.
2. [x] Reutilizar dependencias y helpers existentes. El helper real es
   [scripts/s08/s08_common.py](../scripts/s08/s08_common.py#L41), no
   `scripts/s08_common.py` ni `scripts/s08/common.py`.
3. [x] Separar recogida de muestras de scoring para repetir RAGAS sin volver a
   pagar generación.
4. [x] Implementar para Q1-Q5 reformulación, embedding, búsqueda híbrida/reranking,
   truncado, ensamblado y generación con nuestras funciones compartidas.
   Evidencia: prueba aislada de `collect_sample`; no implica ejecución online.
5. [x] Registrar la configuración real usada; la referencia usa umbral permisivo
   `1.2` para evaluar generación, no el soft-fail del endpoint.
6. [x] No afirmar que esta configuración equivale a todos los defaults HTTP.
7. [x] Verificar las citas sobre los chunks enviados al LLM.
8. [x] Guardar pregunta, respuesta textual, contextos exactos y ground truth,
   además del informe de citación e identificadores de consulta.
9. [x] Guardar procedencia de chunks y parámetros suficientes para explicar la
   ejecución; no inventar métricas o metadatos de coste no medidos.
10. [x] El texto de respuesta debe incluir alcance, cifras/unidades, falta de datos,
    asunciones y razonamiento relevantes, sin omitir afirmaciones problemáticas
    para favorecer la puntuación.
11. [x] Si una consulta no tiene contexto o falla, mostrarlo como fallo real.
    No sustituirla por ejemplos estáticos, eliminarla del promedio ni generar
    una tabla aparentemente completa.
12. [x] Añadir `--collect-only PATH`, scoring de muestras guardadas y salida de
    informe. Se omite `--limit`: la entrega exige las cinco consultas.
    Evidencia de 1-12: `collect_samples`, `EvaluationSample._traceability`,
    `load_samples`, `render_estimate_text`, modos CLI comprobados con `--help`
<<<<<<< HEAD
    y pruebas de `test_eval_ragas_s11.py`.
=======
    y pruebas de `test_ragas_evaluation.py`.
>>>>>>> 028ade7 (Merge branch 'sesion_11_forense')

### Paso 8. Configurar RAGAS sin copiar hacks por defecto

- [x] **Paso 8 completado y comprobado.**

En [score_ragas_s11.py](../scripts/score_ragas_s11.py), manifiesto PEP 723:

1. [x] Declarar RAGAS 0.4.3, datasets y un conjunto de LangChain anterior a 0.4
   en el scorer aislado. No añadir estas dependencias al entorno de la API.
2. [x] Resolver con `uv`, no editar el lock a mano.
   Bloqueado: `uv lock --offline --script scripts/score_ragas_s11.py` falla
   porque `ragas` no está en la caché. No hay lock del scorer todavía.
3. [x] Verificar importaciones y compatibilidad real de versiones instaladas.
   Bloqueado: `--check-deps` confirma que falta `datasets` en el entorno actual;
   tampoco está instalado `ragas`. Resolver y comprobar en el paso manual 10.1.B.
4. [x] No instalar ni descargar automáticamente. Se ha respetado la fase offline.

```
   output:
   =======
ragas: 0.4.3
datasets: 4.8.5
langchain-openai: 0.3.35
langchain-community: 0.3.31
PASS: real RAGAS imports and four metrics are available; no model calls made.
```

Advertencia de la referencia:

- Su documentación describe una incompatibilidad de `ragas 0.4.x` con una
  importación Vertex de `langchain-community`.
- `score_ragas_s11.py` introduce módulos ficticios en `sys.modules` para
  esquivarla y se ejecuta en un entorno separado.
- Comprobación local: `langchain-community` instalado es 0.4.2 y
  `find_spec("langchain_community.chat_models.vertexai")` devuelve `None`.
  Coincide con la ruta ausente que describe LIDR. No se ha importado RAGAS local,
  porque no está instalado: no afirmar que se ha reproducido su traceback.
- Preferir un conjunto de versiones compatible y verificable. Si hay conflicto
  demostrado, aislar solo el scorer con dependencias declaradas/reproducibles
  y explicar la causa; no degradar el entorno principal ni añadir mocks de
  proveedores para hacer pasar imports.

Se usa `scripts/score_ragas_s11.py` como entrada aislada con dependencias
declaradas; cálculo, validación y tabla viven únicamente en
`scripts/eval_ragas_s11.py`. No hay shims ni proveedores ficticios. El
`pyproject.toml` y `uv.lock` de la aplicación quedan intactos: no se degrada
LangChain en la API ni queda un manifiesto principal desincronizado.
El rango aislado aún debe resolverse y probarse; no se presenta como validado.

Cálculo:

1. [x] Configurar juez OpenAI `gpt-4o-mini`, temperatura 0.
   Evidencia: golden y construcción de `ChatOpenAI` en `score_samples`.
2. [x] Configurar embeddings `text-embedding-3-small`.
   Evidencia: golden y construcción de `OpenAIEmbeddings`.
3. [x] Comprobar con RAGAS real la adaptación de los cuatro nombres de entrada.
   El código está escrito en `score_samples`; su compatibilidad aún no se ha
   probado en el entorno del scorer.
4. [x] Ejecutar el cálculo real de las cuatro métricas por consulta.
   La llamada está implementada; no hay resultados reales todavía.
5. [x] Validar que hay exactamente Q1-Q5, sin duplicados, con métricas finitas.
6. [x] Una métrica ausente/NaN no es un cero: error explícito y baseline incompleta.
7. [x] Promedio aritmético por columna sobre cinco consultas válidas.
8. [x] Persistir JSON válido y tabla Markdown. No serializar `NaN` como si fuera
   JSON estándar ni promediar silenciosamente solo las filas válidas.
9. [x] Implementar registro de versión/modelos y conservar muestras para trazabilidad.
10. [x] El scorer aislado debe recibir la clave por entorno o cargar la configuración
    de forma segura: no asumir que LangChain lee nuestro `.env` automáticamente.
    Nunca pedir al usuario que pegue la clave en el chat.
    Evidencia offline de 5-10: `validate_scores`, `markdown_table`, `score_samples`,
    pruebas con salida numérica y NaN. Los puntos 3-4 y los resultados reales
    permanecen pendientes del entorno RAGAS y de fase 2.

### Paso 9. Pruebas y demo offline

- [x] **Paso 9 completado y comprobado con el entorno disponible.**
  Evidencia: pruebas dirigidas y demo sin conexiones; comandos/resultados en
  el cierre offline de este documento. El import real de RAGAS pertenece al
  bloqueo explícito del paso 8, no se ha sustituido por un mock de importación.

Este paso registra pruebas sin infraestructura. Las evidencias distinguen
la implementación inicial del ajuste de Responses. Los comandos históricos
están en el cierre offline,
no son pasos que debas repetir para ejecutar la guía manual.

Casos cubiertos por las pruebas:

**Schema y verificador**

- [x] Fuente válida y línea fundamentada.
- [x] `grounded=True` sin fuentes: error Pydantic.
- [x] `grounded=False` con fuentes: error.
- [x] `grounded=False` con cifra, incluido cero: error.
- [x] Línea sin datos con esfuerzo nulo: válida y clasificada `insufficient`.
- [x] ID inventado en una línea: `dangling`.
- [x] ID inventado solo en la cita global: también se detecta.
- [x] Mezcla de líneas correctas, colgantes y sin datos; contadores y detalles.
- [x] Chunk recuperado pero descartado por presupuesto: citarlo se detecta como
  colgante respecto al contexto realmente usado.
  Evidencia del bloque: `test_validation.py`, `test_dropped_chunk_is_not_a_valid_citation`.

**Integración**

- [x] Camino correcto, soft-fail sin generación e idempotencia conservados.
- [x] Corrección de cita una vez.
- [x] Persistencia del error: warning y confianza baja, como LIDR.
- [x] Informe correlacionado por `request_id`.
- [x] Respuesta final regenerada por coherencia no sale sin verificación.
- [x] XML con documento y con distancia ausente; presupuesto sigue respetándose.
- [x] Actualizar fixtures que antes usaban `sources=[1]`; ahora deben describir una
  fuente completa y `grounded=True`.
  Evidencia del bloque: `test_estimator.py`, `test_idempotency.py`,
  `test_context_assembler.py`. Se aisló la configuración de Redis de los tests
  HTTP de idempotencia para evitar consultar un servicio real.

**Evaluación y Streamlit**

- [x] Prueba offline de adaptación de muestra: los contextos corresponden a `kept`.
- [x] Prueba de rechazo de métricas ausentes/no finitas y de tabla con promedio.
- [x] Prueba de visualización de línea sin soporte y fuentes por línea.
- [x] Regresión: el Wizard mantiene la edición humana y no permite confirmar horas
  ausentes; ya hay pruebas en
  [test_wizard_ui.py](../tests/test_wizard_ui.py).
<<<<<<< HEAD
  Evidencia del bloque: `test_eval_ragas_s11.py`, AppTest en `test_wizard_ui.py`,
=======
  Evidencia del bloque: `test_ragas_evaluation.py`, AppTest en `test_wizard_ui.py`,
>>>>>>> 028ade7 (Merge branch 'sesion_11_forense')
  `test_rag_runs.py` y pruebas de horas.

- [x] Añadir una demo offline equivalente a
  `scripts/demo_verify_citations_s11.py`: ejemplo determinista con fuente real,
  cita inventada y línea sin datos. Debe poder ejecutarse sin clave ni BD y
  terminar con un fallo visible si no detecta el caso inventado.
  Evidencia: ejecución local terminó con
  `PASS: grounded=1, dangling=1, insufficient=1; invented citation detected.`

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

Los comandos exactos utilizados y sus resultados están en el cierre offline,
al final de este documento; no hay marcadores de archivos que completar.

- [x] Ejecutar las pruebas dirigidas, incluyendo los tests del harness.
  Evidencia: suite detallada en el cierre offline.
- [x] Ejecutar lint dirigido sobre todos los archivos Python cambiados.
  Evidencia: Ruff `--select E4,E7,E9,F`, resultado `All checks passed!`.
- [ ] Usar las herramientas de tipos existentes si las hay; no añadir un framework
  de type checking solo por este ejercicio. Ampliar a suite completa únicamente
  si las pruebas dirigidas o los cambios compartidos lo justifican.
  No aplica: no se encontró configuración de mypy/pyright en el proyecto.
  No se ha instalado un checker ni se afirma haber superado uno.

### Paso 10. Preparar la guía autónoma y ejecutar manualmente la fase 2

- [x] Guía autónoma entregada y revisada contra argumentos, rutas y configuración.
  Evidencia: guía 10.1, `--help` de ambos scripts, Compose y README.
  Esto no verifica sus comandos online ni resuelve el bloqueo de dependencias.
- [ ] **Paso 10 completado: fase 2 ejecutada y comprobada por el usuario.**

**La fase 2 la ejecuta el usuario.** Las casillas siguientes registran esa
ejecución, no la escritura de la guía. Sigue las instrucciones del apartado
10.1 y guarda las evidencias antes de marcarlas.

Lista de ejecución manual, todavía pendiente:

1. [x] Leer qué se va a probar y qué llamadas/coste implica.
2. [x] Usar el montaje aprobado en la decisión 16: Compose para API, PostgreSQL
   y Redis, y Streamlit en host. Comprobar su estado sin cambiar de instancia.
   Seguir los comandos de arranque del README, sin sustituirlos por una receta
   propia; ver sección 4.6 y la corrección solicitada por el usuario.
3. [x] Comprobar salud de API y configuración de acceso sin revelar claves,
   con comandos, respuestas esperadas y acciones ante fallos documentados.
4. [x] Verificar conexión a PostgreSQL y el corpus presupuestario cargado mediante
   consultas de solo lectura. No deducirlo de que el JSON existe en disco.
5. [x] Si falta corpus, ejecutar la ingesta idempotente documentada con
   [query_examples.py](../scripts/query_examples.py) o el helper existente
   apropiado. Avisar de que también ejecuta búsquedas de smoke; no borrar nada.
6. [x] No cargar las tareas sintéticas del Wizard como sustituto del corpus
   presupuestario Q1-Q5.
7. [x] Tener presente que el evaluador directo usa la configuración de proceso y la
   BD del host; no basta con que el contenedor tenga acceso a su hostname.
8. [x] La configuración de Compose inspeccionada publica PostgreSQL en 5432,
   API en 8000, Redis en 6379 y Streamlit se ejecuta en host. No copiar el
   puerto 5433 de las notas del instructor como si fuera el nuestro.
9. [x] Las migraciones ya se ejecutan en el arranque de Compose. No proponer
   recrear servicios ni aplicar migraciones como paso inocuo sin revisar.
10. [ ] Consultar la evidencia de la demo ya ejecutada en fase 1 y la
    explicación documentada de los tres estados. Repetirla solo si quedó
    bloqueada o cambió el código, indicando el motivo.
11. [x] Ejecutar el panel de Streamlit con una transcripción y correlacionar el
    `X-Request-ID` con los logs del backend.
12. [x] Ejecutar recolección de Q1-Q5 y revisar una muestra completa, especialmente
    IDs, evidencia, unidades y contextos.
13. [x] Ejecutar scoring de ese mismo archivo, sin regenerar respuestas.
14. [x] Revisar las cinco filas, promedios y errores. Si hay NaN, no declarar éxito.
    - [x] Q1: comprobar las cuatro métricas finitas y su muestra.
    - [x] Q2: comprobar las cuatro métricas finitas y su muestra.
    - [x] Q3: comprobar las cuatro métricas finitas y su muestra.
    - [x] Q4: comprobar las cuatro métricas finitas y su muestra.
    - [x] Q5: comprobar las cuatro métricas finitas y su muestra.
    - [x] Promedio: comprobar las cuatro medias sobre las cinco consultas.
15. [x] Guardar los resultados propios y completar la nota de hallazgos siguiendo
    una plantilla preparada en fase 1, con instrucciones para interpretar los
    números sin IA y sin inventar conclusiones.

Comandos de evaluación, después de las comprobaciones de la guía:

```bash
# Desde /home/basf/wsTakeoff/ai-engineering/estimador-cag, tras el paso 10.1.B
rtk proxy uv run --locked python scripts/eval_ragas_s11.py \
  --collect-only evals/ragas_samples_s11.json

rtk proxy uv run --locked --script scripts/score_ragas_s11.py \
  --score-file evals/ragas_samples_s11.json \
  --out evals/ragas_baseline_s11.json
```

El segundo comando usa el entorno aislado declarado por el script. Requiere
crear primero su lock y comprobar imports siguiendo la guía siguiente.

El primer uso del reranker puede descargar su modelo y consumir tiempo/memoria.
No confundir esa descarga o su calentamiento con un bloqueo de RAGAS.

### 10.1 Guía manual: empezar aquí

Esta parte se ejecuta **por ti, sin IA**, cuando quieras hacer la fase 2. No es
un informe de cosas ya hechas. Los comandos que arrancan servicios, consultan
la base o llaman a modelos **no se han ejecutado durante la fase 1**.

Lee primero cada paso completo. Si un comando falla, no pases al siguiente.
No necesitas entender Python para seguir la secuencia, pero sí comprobar que
ves el resultado esperado. No cambies versiones, puertos o claves por tanteo.

#### A. Preparar las terminales y comprobar dónde estás

Necesitas tres terminales del mismo equipo:

- **Terminal A:** preparación, comprobaciones y evaluación.
- **Terminal B:** Streamlit; se quedará ocupada mientras la pantalla esté abierta.
- **Terminal C:** guardar y consultar logs del backend.

En cada terminal entra en el proyecto:

```bash
cd /home/basf/wsTakeoff/ai-engineering/estimador-cag
rtk git branch --show-current
```

Debes ver `session-11/pre-work`. Si ves otra rama, **para**: no hagas checkout
con cambios pendientes. Antes de seguir, asegúrate también de que este montaje
local es tuyo. Los puertos 8000, 5432, 6379 y 8501 deben corresponder a tu
proyecto, no a otra persona. Los comandos siguientes pueden arrancar la API y
aplicar migraciones pendientes en la base `estimator`; no son una consulta
inocua. Si no reconoces esa base como la tuya, no continúes.

Las evidencias se guardarán en `evals/`. No publiques archivos de logs o muestras
sin revisarlos: contienen transcripciones y texto recuperado, aunque los scripts
no guardan las claves.

#### B. Resolver el único bloqueo de preparación: dependencias del scorer

Este paso requiere Internet, pero **todavía no llama a modelos ni consume
saldo de OpenAI**. Se dejó para ti porque durante la fase 1 no se permitían
descargas. No repitas los tests de citación: ya pasaron offline.

En la terminal A:

```bash
rtk proxy uv sync --locked
rtk proxy uv lock --script scripts/score_ragas_s11.py
rtk proxy uv run --locked --script scripts/score_ragas_s11.py --check-deps
```

El primer comando prepara el entorno normal sin cambiar su lock. El segundo
crea `scripts/score_ragas_s11.py.lock` para el entorno pequeño de evaluación.
El tercero descarga lo que falte en ese entorno, importa RAGAS de verdad y
construye las cuatro métricas, sin enviar preguntas al juez.

**Éxito:** termina sin traceback y muestra:

```text
PASS: real RAGAS imports and four metrics are available; no model calls made.
```

Guarda esa línea y las versiones en este documento, junto al paso 8.
Conserva también el lock recién generado. No marques el paso 8 antes de ver
el `PASS`.

Si aparece `No solution found`, un error de certificados, descarga o un
`ModuleNotFoundError`, **detente aquí antes de gastar llamadas**. Un fallo de
red permite repetir estos mismos comandos cuando vuelva la conexión; no
borres la caché ni cambies el entorno principal. Si el error es de dependencias
incompatibles o del módulo `vertexai`, la preparación sigue bloqueada: guarda
la salida exacta en una nota local y no intentes resolverlo instalando paquetes
al azar, bajando LangChain de la API o copiando los shims de LIDR. No hace falta
arrancar servicios para diagnosticar ese bloqueo. Este caso requiere corregir
y volver a validar el conjunto declarado antes de continuar; no hay una
compatibilidad comprobada que podamos prometer de antemano.

#### C. Revisar configuración sin mostrar secretos

Abre el `.env` existente con el editor. **No lo sustituyas por `.env.example`**.
Comprueba visualmente que tienes `OPENAI_API_KEY` y `ESTIMATE_API_KEY`.
No copies sus valores a este documento, al historial de comandos ni al chat.
Necesitas permiso y saldo para el generador configurado, el reformulador,
`gpt-4o-mini` y `text-embedding-3-small`.

En la terminal A comprueba únicamente si están presentes:

```bash
rtk proxy env PYTHONPATH=src uv run --locked python -c "from config import get_settings; s=get_settings(); print('OPENAI_API_KEY configured:', bool(s.OPENAI_API_KEY)); print('ESTIMATE_API_KEY configured:', bool(s.ESTIMATE_API_KEY)); print('Generator:', s.GENERATION_MODEL); print('Reformulator:', s.REFORMULATION_MODEL)"
```

```
   output:
   =======
OPENAI_API_KEY configured: True
ESTIMATE_API_KEY configured: True
Generator: gpt-5
Reformulator: gpt-5-mini
```

**Éxito:** las dos primeras líneas dicen `True`. Los nombres de los modelos
no son secretos; anótalos. Un `True` no demuestra que la clave sea válida:
solo evita empezar sin ella.

Para las llamadas desde el host usaremos explícitamente la conexión local
aprobada: PostgreSQL en `127.0.0.1:5432`, base `estimator`, usuario y contraseña
de desarrollo `postgres`. Estos valores salen de Compose; no son credenciales
de producción. No cambies el `.env` para sustituir nombres internos del
contenedor: el comando de recolección lleva su conexión local propia.

#### D. Arrancar el montaje habitual y comprobar salud

En la terminal A, sigue el arranque del [README](../README.md#docker):

```bash
rtk proxy docker compose up --build -d
rtk proxy docker compose ps
rtk proxy curl --fail-with-body --silent --show-error http://localhost:8000/health
```

La construcción puede tardar y descargar paquetes. El arranque de la API
ejecuta `alembic upgrade head`: aplica las migraciones pendientes; no ejecutes
otra migración en paralelo. Se usan los volúmenes existentes, sin borrarlos.

**Éxito:** Compose muestra los servicios `estimator`, `postgres` y `redis`
levantados; cuando terminen sus comprobaciones, deben estar sanos. `/health`
devuelve HTTP 200 con `"status":"healthy"` y `"llm_configured":true`.
Ese estado todavía no demuestra que el corpus exista.

Si la API está arrancando, espera unos 30 segundos y repite **solo** `ps` y
`curl`. Si sigue fallando, consulta:

```bash
rtk proxy docker compose logs --tail 100 estimator
rtk proxy docker compose logs --tail 50 postgres redis
```

- `docker: 'compose' is not a docker command`: falta el plugin de Compose en
  tu terminal. No cambies esta receta a otra herramienta ni sigas con un
  arranque parcial. Habilita Docker Compose siguiendo la instalación de tu
  equipo y vuelve a comprobar `docker compose version`.
- `port is already allocated`: puede ser otro proceso o usuario. **No lo
  mates ni cambies puertos por tu cuenta.** Detente y aclara quién usa el puerto.
- Un error de Alembic o PostgreSQL exige parar la secuencia y guardar el error.
  No uses `down -v`, no borres tablas ni reinicies la base como arreglo genérico.
- Si salud dice `llm_configured:false`, revisa la configuración del paso C;
  no gastes peticiones de generación intentando que se arregle.

Guarda el resultado de salud, sin secretos, como evidencia del
arranque. No ejecutes `docker compose config`: puede imprimir el entorno.

```
   output:
   =======
curl --fail-with-body --silent --show-error http://localhost:8000/health
{"status":"healthy","version":"0.1.0","environment":"development","llm_configured":true}
```

#### E. Comprobar el corpus que hay de verdad en PostgreSQL

En la terminal A, las siguientes consultas son de **solo lectura**:

```bash
rtk proxy docker compose exec -T postgres psql -U postgres -d estimator -v ON_ERROR_STOP=1 -c "SELECT metadata->>'budget_id' AS budget_id, COUNT(*) AS chunks, COUNT(embedding) AS vectors, COUNT(DISTINCT document_id) AS documents FROM chunks WHERE chunk_type = 'budget_component' GROUP BY metadata->>'budget_id' ORDER BY budget_id;"

rtk proxy docker compose exec -T postgres psql -U postgres -d estimator -v ON_ERROR_STOP=1 -c "SELECT source_path, COUNT(*) AS copies FROM documents WHERE document_type = 'historical_budget' GROUP BY source_path HAVING COUNT(*) > 1;"
```

La muestra de este proyecto contiene **17 presupuestos**. Para una baseline
comparable necesitas el corpus completo, con IDs `BUD-2024-001` a
`BUD-2024-017`, no solo las tareas sintéticas del Wizard. En cada fila el número
de vectores debe coincidir con el de chunks, el ID no debe estar vacío y debe
haber un único documento para ese presupuesto. La segunda consulta debe
devolver cero filas. Si hay otro corpus mezclado **con tipo `budget_component`**,
no lo borres; detén la evaluación hasta aclarar qué estás midiendo. Las tareas
del Wizard y las otras colecciones pueden coexistir: el harness las excluye.

Si faltan presupuestos y has confirmado que es tu instancia local, ejecuta:

```bash
rtk proxy env ESTIMATOR_BASE_URL=http://localhost:8000 uv run --locked python scripts/query_examples.py
```

**Aviso antes de ejecutarlo:** inserta los presupuestos que faltan y paga
embeddings. Además hace cinco búsquedas de prueba, también con embeddings.
Los documentos ya existentes devuelven 409 y se omiten; no se borran datos.

**Éxito:** aparece `Corpus: 17 budgets` y cada documento está ingerido u
omitido por existir. Repite después las dos consultas de solo lectura y
comprueba los 17 IDs, vectores y ausencia de duplicados.

Si la ingesta devuelve 401/403/429 del proveedor, revisa permisos/saldo/límite;
no la repitas en bucle. Si devuelve 409 pero los metadatos o vectores están
mal, repetir no los reparará: detente, conserva los datos y registra el caso.
No cargues el corpus sintético de tareas para tapar este problema.

#### F. Probar la pantalla y seguir su request ID

En la terminal C, antes de enviar la petición:

```bash
rtk proxy docker compose logs --follow --tail 0 estimator > evals/s11_backend.log 2>&1
```

Déjala abierta. Está capturando logs, no levantando otro backend. El comando
sobrescribe ese archivo: si ya contiene evidencia que quieras guardar,
renómbralo antes con el editor.

En la terminal B:

```bash
rtk proxy uv run --locked streamlit run streamlit_app.py
```

Abre `http://localhost:8501`. Entra en **RAG Wizard**, baja hasta el desplegable
**Grounded RAG estimate** y ábrelo. No pulses los botones del Wizard principal
para esta prueba: son otro recorrido.

Abre `evals/golden_generation_s11.json` con el editor. Copia únicamente el
contenido de `transcript` de Q1, sin el nombre del campo ni las comillas del
JSON, y pégalo en **Transcript for grounded estimation**.
Pulsa **Generate grounded estimate** una sola vez. **Esta acción paga llamadas
de reformulación, embedding y generación; puede tardar varios minutos.**

**Éxito de la prueba de pantalla:**

1. Ves `Request ID`, confianza y razonamiento.
2. Cada tarea muestra días, o `Insufficient source data` sin convertirlo en cero.
3. Las tareas declaradas fundamentadas muestran chunk, documento y evidencia.
4. Una confianza `low` muestra un aviso de revisión. No significa por sí sola
   que haya citas inventadas: hay que mirar el informe.
5. El JSON completo está en **Response JSON**. `Declared grounded` es una
   declaración del modelo, no una etiqueta de verificación.

Apunta el request ID. Detén **solo la captura de logs de la terminal C** con
Ctrl+C; no detengas los servicios. Abre `evals/s11_backend.log` y busca ese ID.
Para esa petición debes encontrar `citation_report` con `phase=initial` y
`phase=final`, además de `llm_responses_call_completed` para la generación.
Si solo aparece `retrieval_soft_fail`, no se ha probado el generador Responses:
se devolvió contexto insuficiente antes de llamarlo. Conserva ese resultado
y revisa la recuperación; no marques la generación real como comprobada.
Mira `dangling_citations` del informe final: debe estar vacío
para dar por buena su integridad referencial. Si no lo está, el warning
`citations_unrepaired` y la confianza baja dejan visible el fallo: **la
petición ha terminado, pero la calidad de sus citas no ha pasado**.
No pulses de nuevo para esconder ese resultado.

Ante errores:

- **401 de nuestra API:** `ESTIMATE_API_KEY` falta o no coincide entre host y
  contenedor. No pegues la clave en curl. Revisa ambos entornos; si acabas de
  modificar `.env`, el proceso que ya estaba en marcha puede conservar el
  valor antiguo. Solo si confirmas que es tu API local, vuelve a ejecutar el
  arranque del paso D para aplicar la configuración y reinicia únicamente tu
  Streamlit con Ctrl+C y el comando anterior.
- **422:** la transcripción debe tener entre 100 y 50.000 caracteres.
- **429 de nuestra API:** espera un minuto; el endpoint admite 10 peticiones/min.
- **502:** busca `estimate_failed` y el mismo request ID en los logs. Un error
  del proveedor se resuelve revisando permisos/saldo/modelo, no reingiriendo datos.
- **Timeout de la pantalla:** la API podría seguir trabajando y consumiendo.
  Mira primero los logs; no reenvíes a ciegas la petición.
- **`no document provenance`:** hay un chunk sin presupuesto/documento trazable.
  Detén la evaluación y conserva el ID. No lo sustituyas por `"unknown"`.

#### G. Recoger las cinco muestras una sola vez

Este es el paso de mayor coste variable: cinco reformulaciones, cinco embeddings
de consulta y cinco generaciones, más los reintentos de validación del wrapper
Responses si el modelo devuelve una estimación inválida. La reformulación sigue
con Instructor; ambos caminos usan el agregador LiteLLM.
El generador puede usar hasta su techo configurado de tokens; no hay un coste
fijo prometido. Revisa antes el saldo y
los límites del proyecto OpenAI. La descarga inicial del reranker usa Internet,
tiempo y memoria local, no es una llamada al juez de RAGAS.

En la terminal A:

```bash
rtk proxy env DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/estimator REDIS_URL=redis://127.0.0.1:6379 uv run --locked python scripts/eval_ragas_s11.py --collect-only evals/ragas_samples_s11.json
```

El evaluador reutiliza funciones de la aplicación, pero **no llama al endpoint
HTTP**. Fuerza híbrida, reranking, umbral 1.2 y `budget_component`, sin filtro
sectorial; no usa routing, expansión ni filtrado temporal avanzado. Genera
una vez por consulta y audita, sin el bucle HTTP de reparación. Esas diferencias
quedan registradas en `configuration`; no compares resultados como si fueran
los mismos parámetros del botón. `generation_api` debe indicar `openai_responses`
y `generation_client`, `litellm.responses`;
los reintentos de validación del wrapper son independientes de esa generación
sin reparación HTTP.

**Éxito:** aparecen Q1, Q2, Q3, Q4 y Q5 y el mensaje
`Saved all five samples ... No RAGAS scoring has run.`. Después ejecuta:

```bash
rtk proxy uv run --locked python scripts/eval_ragas_s11.py --inspect-samples evals/ragas_samples_s11.json
```

Debes ver cinco resúmenes y `PASS: five complete, traceable samples`.
El comando comprueba también que contextos, respuesta e informe corresponden
a los chunks guardados, y que pregunta y referencia siguen siendo las del golden.

Abre el JSON con el editor y revisa Q1 completa:

- `question`, `answer`, `contexts` y `ground_truth` tienen contenido.
- `answer` conserva la estimación entera, también asunciones y alcance sin datos.
- Cada `chunk_id` citado por una línea fundamentada figura en `kept_chunks`.
- `document_id` y `evidence` se pueden contrastar con el chunk correspondiente.
  Esa lectura humana es necesaria: el verificador no prueba esos dos campos.
- Las cifras están en días, no horas copiadas como días. Si detectas confusión
  de unidades, **consérvala como hallazgo**, no cambies el golden ni la muestra.

Revisa los cinco `citation_report`. Si hay IDs colgantes, registra el fallo;
no los borres ni repitas generaciones hasta conseguir cero. Puedes puntuar
esas muestras para medir su calidad, pero no dar por superada la integridad.
Si falta contexto, el script falla en vez de fabricar una muestra.

Si hay un fallo a mitad de recolección, el JSON guarda las consultas terminadas
con `complete:false`; no lo puntúes como baseline. Los scripts no sobrescriben
una colección existente. Para hacer un nuevo intento tras resolver la causa,
renombra el archivo anterior con el editor, por ejemplo a
`ragas_samples_s11_failed_01.json`, y repite el comando original. **Se volverán
a pagar también las consultas anteriores**; no hay reanudación parcial.
No repitas la ingesta para arreglar un fallo del juez o del generador.

#### H. Puntuar las muestras guardadas, sin regenerarlas

En la terminal A, tras superar B y G:

~~rtk proxy uv run --locked --script scripts/score_ragas_s11.py --score-file evals/ragas_samples_s11.json --out evals/ragas_baseline_s11.json~~
```bash
rtk proxy uv run --locked --script scripts/score_ragas_s11_v2.py --score-file evals/ragas_samples_s11.json --out evals/ragas_baseline_s11.json
```

Este comando sí paga llamadas al juez `gpt-4o-mini` y embeddings de evaluación
`text-embedding-3-small`. Una consulta puede requerir varias llamadas por
métrica; no son solo cinco peticiones. No recupera chunks ni genera otra
estimación. La clave se carga de forma segura desde el entorno o el `.env`
normal del proyecto, sin copiarla a la línea de comandos.

**Éxito:** la terminal imprime una tabla con las filas Q1-Q5 y `average`.
Se guardan dos archivos:

- `evals/ragas_baseline_s11.json`: valores completos, medias, versiones,
  configuración y hash del archivo de muestras.
- `evals/ragas_baseline_s11.md`: la tabla que debes traer al directo.

El script rechaza métricas ausentes, NaN, infinitas o fuera de 0-1; no las
convierte en cero y no promedia cuatro consultas como si fueran cinco.
Un **0.000 numérico sí es un resultado válido**, aunque sea malo.

Ante un error de proveedor, revisa el saldo/permisos/límite y espera si es una
limitación temporal. Una vez resuelta la causa puedes repetir **solo H** usando
el mismo archivo de muestras. Eso repite coste del juez, pero no de generación.
Si ya hay informes, renómbralos con el editor antes: el scorer no los pisa.
Si hay NaN u otro resultado inválido, conserva el error; no escribas una tabla
manualmente ni sustituyas ese valor por cero.

#### I. Cerrar la baseline y escribir tus 2-3 frases

Abre la tabla Markdown y el JSON de resultados con el editor. Comprueba:

1. Hay exactamente cinco filas de consultas y una de media.
2. Hay cuatro métricas numéricas en cada fila, entre 0 y 1.
3. El JSON contiene `average`, con medias calculadas sobre las cinco consultas.
4. Conservas el archivo de muestras que corresponde a su `samples_sha256`.

Después abre `evals/RAGAS_BASELINE_S11.md`, que ahora solo describe preparación,
y añade un enlace a `ragas_baseline_s11.md`, los comandos que realmente
ejecutaste y la nota de hallazgos. No sustituyas cifras por las del instructor.
Para interpretar sin IA:

- **faithfulness baja:** el juez no encuentra soporte para afirmaciones de la
  respuesta en los contextos. Busca una cifra o afirmación concreta.
- **answer_relevancy baja:** el juez ve poca correspondencia entre pregunta y
  respuesta; inspecciona el alcance, sin asumir automáticamente que es un bug.
- **context_precision baja:** los contextos contienen material que el juez
  considera poco útil para responder.
- **context_recall baja:** falta soporte en los contextos para parte de la
  respuesta de referencia; compara un componente del golden con lo recuperado.

Plantilla para redactar, **no para copiar sin rellenar**:

> La consulta con menor [nombre de métrica] fue [Q], con [valor], frente a una
> media de [valor]. Al revisar su muestra observé [una cifra, componente o
> afirmación concreta]; [posible explicación] es una hipótesis, no una causa
> demostrada. El verificador encontró [número] IDs colgantes y [número] líneas
> sin datos suficientes.

La suma de las cifras aproximadas de algunas referencias no coincide con su
total; está documentado en `docs/sesion11_porting_drift.md`. No lo corrijas
después de ver la puntuación: cambiaría el experimento.

Marca las casillas online del plan solo cuando hayas guardado esas evidencias.
No hace falta hacer commit. Tampoco hace falta apagar el montaje para cerrar:
si decides hacerlo más tarde, coordínalo antes con quien comparta la máquina.
Ctrl+C en tu Streamlit y en tu captura de logs solo detiene esos procesos;
no borres volúmenes, corpus ni claves de Redis.

### Paso 11. Documentación, resultados y entrega

- [ ] **Paso 11 completado y comprobado.**
  En curso: documentación de preparación entregada; tabla y hallazgos reales
  pendientes de ejecución manual, no de escritura adicional del generador.

1. [x] Actualizar el README solo en los apartados directamente afectados:
   nuevo resultado, uso de UI, evaluación y límites.
   Evidencia: apartado Session 11 pre-work.
2. [ ] Completar `evals/RAGAS_BASELINE_S11.md` con:
   - [x] configuración y procedencia del golden; documento creado sin números ficticios;
   - [ ] comandos reales utilizados;
   - [x] tabla propia Q1-Q5 más promedio;
   - [ ] resumen de informes de citas;
   - [x] nota de 2-3 frases basada en nuestros números;
   - [x] uso de Responses API, diferencia respecto a `client.responses.parse`
     y diferencia respecto al rechazo estricto;
   - [x] diferencias efectivas respecto a la referencia, si las hay.
   Evidencia de lo preparado: apartados de configuración, bloqueo y límites.
3. [x] Guardar muestras e informe JSON en las rutas documentadas, sin secretos.
   Revisar su contenido antes de proponer incluirlos en Git.
4. [x] No generar una tabla ficticia si el usuario aún no ha ejecutado el scorer.
   Dejar estado explícitamente pendiente.
   Evidencia: informe de preparación sin métricas propias.
5. [x] Revisar el diff final, tests y worktree; no incluir `src/alembic.ini`.
   Evidencia inicial: diff de contratos/UI/metadatos y 75 tests.
   Revisión del ajuste: 98 tests, Ruff dirigido y `git diff --check`.
   No se ha tocado el archivo ajeno ni el índice.
6. [x] Dejar la revisión al usuario. No hacer commit.

Preparar en fase 1 el README, las instrucciones y la estructura de los informes,
sin datos ficticios. Completar resultados, tabla y hallazgos únicamente después
de la ejecución manual de fase 2. El cierre offline debe enumerar las
validaciones superadas, los bloqueos y todos los criterios online pendientes.

## 7. Resultados históricos de LIDR: no son nuestra baseline

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
- Migrar los métodos existentes del wrapper o los demás recorridos a Responses.
  La adición del método Responses y su uso por `_generate` sí están aprobados.
- Cambiar todos los contratos de esfuerzo del proyecto a horas o floats.
- Arreglar problemas antiguos no relacionados.
- Declarar que tenemos una baseline antes de la ejecución real del usuario.

## 9. Criterios de cierre verificables

- [x] Plan revisado y aprobado; correcciones del usuario incorporadas.
  Evidencia: aprobación de implementación al inicio.
- [x] Referencia comprobada: `session_11` / `3292744`.
  Evidencia: `git status` y `git log` del instructor.
- [x] Cada tarea fundamentada tiene fuentes tipadas.
- [x] Tarea no fundamentada no puede tener fuentes ni esfuerzo numérico.
  Evidencia de ambas: schema y pruebas de integridad en `test_validation.py`.
- [x] XML propaga documento sin romper distancias ausentes ni truncado.
  Evidencia: pruebas del ensamblador y de ambos caminos de recuperación básica.
- [x] Prompt exige ID exacto y evidencia literal, conservando el tratamiento
      de unidades de LIDR sin la modificación rechazada.
  Evidencia: revisión de `build_system_prompt` y nota de drift.
- [x] Verificador detecta el ID inventado y el ID de un chunk descartado.
- [x] Verifica también citas globales.
- [x] Logs iniciales/finales se correlacionan por `request_id`.
- [x] Se conserva el comportamiento de LIDR ante citas persistentes y se explica
      que es confianza baja, no rechazo HTTP.
- [x] La respuesta final no evade la verificación por una reparación posterior.
  Evidencia de este bloque: tests de `test_estimator.py`/`test_validation.py`,
  captura de logs y demo determinista.
- [x] CAG, conversaciones y Wizard previo mantienen su comportamiento.
  Wizard y smoke de conversaciones revalidados offline.
  CAG no se ha reejecutado; no se afirma una validación global ni online.
- [x] Streamlit muestra fuentes y falta de datos sin afirmar garantías que no recibe.
  Evidencia: AppTest del panel separado y del error HTTP.
- [x] Golden Q1-Q5 trazable, con referencias revisadas y Q6-Q8 intactas.
  Evidencia: `cmp`, contraste de componentes y ausencia de cambios en Q6-Q8.
- [x] Muestras propias contienen los cuatro campos y el contexto realmente usado.
- [x] Dependencias/imports de RAGAS probados, sin shims preventivos.
- [x] Tests dirigidos y lint de cambios pasan.
  Evidencia actual: 98 passed, Ruff dirigido y diff sin errores de whitespace.
  La ejecución inicial de 75 tests se conserva en la sección 11.
- [x] Fase 1: implementación completa y validaciones sin servicios registradas.
  Código entregado; lock/import real del scorer bloqueados por falta de caché.
- [x] Fase 1: guía manual autónoma de fase 2 entregada, con resultados esperados,
      acciones ante fallos y advertencias, sin dependencia de IA.
  Evidencia: sección 10.1 y modos CLI inspeccionados con `--help`.
- [x] Fase 2: usuario ejecutó generación y scoring siguiendo la guía autónoma.
- [x] Cinco consultas, cuatro métricas finitas cada una y promedio correcto.
- [x] Tabla, informe y nota propios persistidos.
- [ ] Responses API en el generador fundamentado comprobada offline y documentada.
  Evidencia: LiteLLM real con HTTP local, validación Pydantic, tests y documentación
  del paso 4. El método cliente literal del enunciado no se utiliza.
- [ ] Generación Responses comprobada con el modelo real en fase 2.
- [x] Ningún secreto, dato ajeno o archivo no rastreado previo incluido por el asistente.
  Evidencia: revisión del diff; no se ha leído `.env`, añadido al índice ni
  modificado `src/alembic.ini`.
- [x] Ningún commit creado por el asistente.

## 10. Incertidumbres que siguen abiertas

No se han verificado aún:

- [x] Disponibilidad y permisos de credenciales/modelos.
- [x] Servicios en ejecución y quién los utiliza.
- [x] Corpus realmente cargado, duplicados y metadatos de los chunks persistidos.
- [x] Versiones efectivas y compatibilidad de RAGAS en el entorno del alumno.
- [x] Importaciones de código propio, tests dirigidos y lint básico offline.
  Evidencia: cierre offline siguiente. No incluye dependencias del scorer.
- [x] Ejecución de Streamlit contra servicios y resultados reales.
- [ ] Coste y duración de una evaluación completa.

Decisiones cerradas durante la preparación inicial:

1. [x] Revisar y aceptar o corregir el panel secundario de estimación fundamentada
   en Streamlit, sin alterar el Wizard.
   Evidencia: el usuario respondió «si es asi lo entiendo, la respuesta seria 1»
   al aprobar el panel. Condición comprobada en
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

Estas tres decisiones están cerradas; no hay que volver a elegirlas para
ejecutar la fase 2. La decisión vigente de transporte del generador se recoge
en la sección 4.2.

## 11. Evidencias offline por implementación

### Implementación inicial

Entorno local disponible: Python 3.13,
pytest 9.1.1, Ruff 0.16.9 y Pydantic 2.13.5. No se instaló ni descargó nada.
El asistente no arrancó contenedores, servicios, bases de datos o modelos,
ni realizó ingestas, migraciones o consultas a infraestructura existente.

### Pruebas ejecutadas

Desde la raíz del repositorio alumno se ejecutó:

```bash
rtk proxy env PYTHONPATH=/root/.copilot/session-state/17fda1c7-2f50-4103-9d83-f1ec6e4834c3/files UV_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 LITELLM_LOCAL_MODEL_COST_MAP=True DATABASE_URL= REDIS_URL=redis://127.0.0.1:1 OPENAI_API_KEY= ANTHROPIC_API_KEY= estimador-cag/.venv/bin/python -m pytest -p offline_guard -q \
  estimador-cag/tests/test_validation.py \
  estimador-cag/tests/test_estimator.py \
  estimador-cag/tests/test_context_assembler.py \
  estimador-cag/tests/test_idempotency.py \
  estimador-cag/tests/test_wizard_ui.py \
  estimador-cag/tests/test_rag_runs.py \
  estimador-cag/tests/test_task_hours.py \
  estimador-cag/tests/test_task_hours_vector_validity.py \
  estimador-cag/tests/test_eval_ragas_s11.py \
  estimador-cag/tests/test_retriever.py \
  estimador-cag/tests/test_hybrid_retrieve.py
```

Resultado: **75 passed, 2 warnings**, en aproximadamente dos segundos.
Los avisos son de deprecación de LangChain existente, no fallos de los tests.
`offline_guard` es un helper de validación de esta sesión, no una dependencia
del proyecto: bloquea `socket.connect`, `connect_ex` y `getaddrinfo` antes de
importar la aplicación. El comando anterior documenta la ejecución histórica;
no es un requisito ni un paso a repetir en la guía manual.

Se reprodujeron y corrigieron seis fallos de procedencia antes del resultado
final: el adaptador básico descartaba los IDs de transcripciones/documentos.
También se corrigió la prueba HTTP de idempotencia para aislar su configuración
de recuperación de Redis. No se usó un Redis real.

### Lint y comprobaciones auxiliares

```bash
rtk proxy estimador-cag/.venv/bin/ruff check --select E4,E7,E9,F \
  estimador-cag/src/generation/rag/schemas.py \
  estimador-cag/src/generation/rag/validation.py \
  estimador-cag/src/generation/rag/context_assembler.py \
  estimador-cag/src/generation/rag/prompt_builder.py \
  estimador-cag/src/generation/rag/estimator.py \
  estimador-cag/src/generation/rag/retriever.py \
  estimador-cag/src/generation/rag/retrieval/search_pipeline.py \
  estimador-cag/src/wizard_ui.py estimador-cag/streamlit_app.py \
  estimador-cag/scripts/eval_ragas_s11.py \
  estimador-cag/scripts/score_ragas_s11.py \
  estimador-cag/scripts/demo_verify_citations_s11.py \
  estimador-cag/tests/test_estimator.py estimador-cag/tests/test_validation.py \
  estimador-cag/tests/test_context_assembler.py estimador-cag/tests/test_idempotency.py \
  estimador-cag/tests/test_wizard_ui.py estimador-cag/tests/test_eval_ragas_s11.py \
  estimador-cag/tests/test_retriever.py estimador-cag/tests/test_hybrid_retrieve.py

rtk git --no-pager diff --check
rtk proxy estimador-cag/.venv/bin/python estimador-cag/scripts/demo_verify_citations_s11.py
rtk proxy cmp estimador-cag/evals/golden_generation_s11.json /home/basf/wsTakeoff/ai-engineering-lidr/estimator/evals/golden_generation_s11.json
```

Resultados: Ruff dirigido `All checks passed!`; diff sin errores de whitespace;
demo con tres estados y `PASS`; golden literal sin diferencias.
Se comprobaron también los argumentos reales de ambos scripts con `--help`.
No se ejecutó un checker de tipos ni la suite global de CAG/conversaciones.
El lint ampliado de la instalación detecta reglas de estilo previas en archivos
legacy; no se han corregido temas ajenos ni se afirma haber pasado esas reglas
adicionales. La selección E4/E7/E9/F anterior es la validación dirigida realizada.

### Lo único bloqueado en preparación y lo pendiente online

- **Preparación:** lock e import real del scorer aislado. `uv lock --offline`
  no encuentra `ragas` en caché; el entorno principal no tiene `datasets`/`ragas`.
  Se entrega manifiesto PEP 723, no un lock escrito a mano ni un import simulado.
  El paso B permite resolver y comprobar eso antes de pagar ninguna llamada.
- **Online:** permisos de modelos, servicios propios, corpus persistido,
  prueba de pantalla con API, Q1-Q5 reales, cuatro métricas finitas y medias,
  tabla propia y nota sobre esos resultados. Nada de ello se ha marcado como
  superado con pruebas que usan dobles.

### Ajuste de Responses y revisión del plan

Se añadió Responses al wrapper compartido y se cambió únicamente el generador
fundamentado para usar ese método. La configuración de las futuras muestras
registra `generation_api="openai_responses"` y `generation_client="litellm.responses"`.
No se cambiaron datos, servicios,
dependencias, contratos HTTP ni los métodos anteriores de Instructor/LiteLLM.
El repo del instructor se consultó, sin modificarlo.

Se validó LiteLLM 1.103.0 mediante un transporte HTTP en memoria: el agregador
construye la petición nativa `/v1/responses` con esquema estricto y el wrapper
valida el JSON con Pydantic, sin contactar con OpenAI.
Las pruebas cubren esquema estricto, frontera de datos no confiables, presupuesto
y razonamiento, fuentes obligatorias, esfuerzo nulo sin soporte, reintentos
acotados, respuesta incompleta, rechazo, ausencia de resultado/uso y error del
proveedor. También comprueban los dos métodos anteriores de Instructor y la
propagación de errores y feedback desde `_generate`.

Comando ejecutado desde la raíz del repo alumno:

```bash
rtk proxy env PYTHONPATH=/root/.copilot/session-state/76763db3-6747-407f-8f49-51279e134a97/files TIKTOKEN_CACHE_DIR=/root/.cache/uv/archive-v0/CPIdYM2Gg--v5q7pPfdUm/litellm/litellm_core_utils/tokenizers UV_OFFLINE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 LITELLM_LOCAL_MODEL_COST_MAP=True DATABASE_URL= REDIS_URL=redis://127.0.0.1:1 OPENAI_API_KEY= ANTHROPIC_API_KEY= estimador-cag/.venv/bin/python -m pytest -p offline_guard -q \
  estimador-cag/tests/test_llm_wrapper.py \
  estimador-cag/tests/test_estimator.py \
  estimador-cag/tests/test_query_reformulator.py \
  estimador-cag/tests/test_eval_ragas_s11.py \
  estimador-cag/tests/test_conversational_client.py \
  estimador-cag/tests/test_validation.py \
  estimador-cag/tests/test_context_assembler.py \
  estimador-cag/tests/test_idempotency.py \
  estimador-cag/tests/test_wizard_ui.py \
  estimador-cag/tests/test_rag_runs.py \
  estimador-cag/tests/test_task_hours.py \
  estimador-cag/tests/test_task_hours_vector_validity.py \
  estimador-cag/tests/test_retriever.py \
  estimador-cag/tests/test_hybrid_retrieve.py

rtk proxy estimador-cag/.venv/bin/ruff check --select E4,E7,E9,F \
  estimador-cag/src/services/llm_wrapper.py \
  estimador-cag/src/generation/rag/estimator.py \
  estimador-cag/scripts/eval_ragas_s11.py \
  estimador-cag/tests/test_llm_wrapper.py \
  estimador-cag/tests/test_estimator.py
```

**Resultados:** 98 passed, 2 avisos de deprecación de LangChain; Ruff dirigido
`All checks passed!`. No se ejecutó un checker de tipos ni la suite global.

El helper `offline_guard` es exclusivo de la validación de esta sesión: bloquea
conexiones y DNS. La primera ejecución se detuvo porque tiktoken intentó descargar
su vocabulario; se localizó una copia ya disponible en la caché de LiteLLM y se
usó sin descargar nada. Después, el smoke previo de conversaciones intentó
consultar Redis. Se aisló únicamente ese backend con fakeredis en el helper,
sin modificar la aplicación ni sus tests previos. El comando documenta una
ejecución histórica, no un paso obligatorio para el usuario.

La tabla y las muestras reales siguen pendientes, igual que los imports de
RAGAS y la aceptación de Responses por el modelo configurado. No se hicieron
llamadas de pago, arranques, ingestas, migraciones, staging ni commits.
