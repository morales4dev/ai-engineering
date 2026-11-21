# Sesión 11: decisiones de portado y diferencias conocidas

## Contexto y estado

Este registro acompaña al [plan de implementación](pre_sesion11_plan.md).
Referencia del instructor: rama `session_11`, commit
`3292744c12c69f88b10ed8c851ae9fb733e2667d`
(`solved pre exercise session 11`), comparado con `session_10_live`.

No usar como referencia el commit posterior `8695e8b`, que incorpora la sesión
completa y está fuera del alcance aprobado.

Implementada en fase 1: golden copiado,
prompt adaptado y pruebas offline ejecutadas. RAGAS real sigue sin ejecutarse;
esta nota no contiene resultados del alumno.

## D-01. Conservar las aproximaciones numéricas de LIDR

### Qué se ha observado

El [golden de generación del instructor](../../../ai-engineering-lidr/estimator/evals/golden_generation_s11.json)
describe estimaciones aproximadas en días. Su descripción indica que los días
se derivan de las horas históricas, aproximadamente a 8 horas por día.

Algunas cifras aproximadas no coinciden con la conversión exacta:

| Consulta | Presupuesto | Horas históricas | Conversión a 8 h/día | Total aproximado en el golden de LIDR |
| --- | --- | ---: | ---: | ---: |
| Q1 | BUD-2024-001 | 480 | 60 | 60 |
| Q2 | BUD-2024-005 | 460 | 57.5 | 59 |
| Q3 | BUD-2024-009 | 560 | 70 | 70 |
| Q4 | BUD-2024-013 | 500 | 62.5 | 62 |
| Q5 | BUD-2024-003 | 600 | 75 | 76 |

Las horas proceden del [corpus de presupuestos](../data/budgets_sample.json),
que se comparó con el del instructor sin encontrar diferencias.
La conversión de esta tabla es una comprobación aritmética para explicar la
discrepancia, no una nueva respuesta experta que deba sustituir al golden.

### Alternativas explicadas al usuario

1. Conservar consultas, trabajos y presupuestos, pero reescribir las referencias
   con las horas históricas y su equivalencia exacta en días. Añadir también
   al prompt una aclaración explícita de 8 horas por día.
2. Conservar literalmente las cifras y el criterio de LIDR, sin ese ajuste.

El asistente recomendó la primera opción para evitar diferencias de unidades o
aproximaciones en la plantilla de evaluación, advirtiendo que se dejaría de
reproducir literalmente la referencia.

### Decisión del usuario

**Elegida la opción 2.**

Respuesta: «el 2, pero anota esto en un archivo sesion11_porting_drift.md».

Por tanto:

- Copiar el golden de generación de la referencia sin corregir sus cifras,
  redondeos, respuestas ni criterio.
- No añadir al prompt una instrucción propia de conversión a días de 8 horas.
  Adaptar las instrucciones de citación de LIDR sin esa mejora adicional.
- No cambiar el corpus para que encaje con las respuestas de referencia.
- No corregir estos puntos durante la implementación como si la propuesta
  inicial del asistente hubiera sido aprobada.
- Generar las métricas del alumno mediante una ejecución propia. No copiar
  los resultados numéricos de evaluación de LIDR.

### Qué diferencia estamos aceptando

En este punto se ha decidido **no introducir una desviación respecto a LIDR**.
Se conserva una limitación conocida de su referencia de evaluación, en lugar de
aprovechar el portado para corregirla.

Las cifras del golden son aproximadas y no deben describirse como equivalencias
aritméticas exactas de las horas originales. Esta diferencia podría influir en
la evaluación; no se ha medido su efecto en el alumno ni se afirma que explique
por sí sola una métrica concreta.

### Comprobaciones de la decisión

- [x] El contenido del golden del alumno coincide con el del instructor en
  `3292744`, incluidas sus cifras aproximadas.
  Evidencia: `cmp evals/golden_generation_s11.json` contra el archivo del
  instructor, sin diferencias.
- [x] El prompt no incorpora la aclaración adicional de conversión rechazada.
  Evidencia: revisión de `build_system_prompt` tras adaptar sus reglas de citas.
- [x] El corpus original no se ha alterado para acomodar el golden.
  Evidencia: no figura en el diff de implementación.
- [x] La documentación de la baseline enlaza esta limitación conocida sin
  atribuirle causas que no se hayan demostrado.
  Evidencia: apartado de configuración de `evals/RAGAS_BASELINE_S11.md`.
- [ ] Los resultados de la baseline son propios del alumno, no copiados de LIDR.

Marcar las casillas solo después de comprobar cada punto y añadir evidencia,
siguiendo las reglas de seguimiento del plan.

## D-02. Ajustes mínimos de implementación

- El presupuesto de tokens cuenta el bloque XML completo, incluidos los saltos
  entre fuentes. La prueba del límite exacto detectó que contar cada fuente
  por separado dejaba fuera esos separadores.
- Si faltan tanto `source_id` como `budget_id`, el ensamblador falla con
  `RetrievalError`; no se usa el documento ficticio `"unknown"`.
- Se propagan también `source_id`/`transcript_id`/`doc_id` desde metadatos en
  los dos caminos de recuperación básica. Se reprodujo con seis pruebas que
  esos IDs se perdían antes de ensamblar; no se cambian ranking ni filtros.
- `grounded` se exige explícitamente en el schema del alumno: no se presupone
  que omitir la declaración equivalga a tener o no tener evidencia.
- La respuesta que puntúa RAGAS es el JSON completo, no un resumen que omita
  descripciones, evidencia o racionales de las asunciones.
- El harness limita el corpus a `budget_component`, para que el corpus
  sintético del Wizard u otras colecciones no sustituyan los presupuestos.
  Registra esa diferencia y la ausencia de filtro sectorial/reparación HTTP.
- El scorer usa un manifiesto aislado PEP 723. Se constató que el entorno actual
  no tiene la ruta Vertex usada por RAGAS según LIDR, pero no se ha reproducido
  el import de RAGAS porque el paquete falta. No se copian sus shims.
  La resolución e importación real quedan pendientes de la preparación manual.

Las referencias también suman redondeos por componente: por ejemplo, Q1 lista
15+20+18+8=61 días aunque anuncia aproximadamente 60, y Q3 lista
24+19+20+8=71 aunque anuncia aproximadamente 70. Son cifras heredadas que se
mantienen; no se atribuye de antemano a ellas ninguna puntuación.

## D-03. Responses API solo para la generación fundamentada

El usuario revisó la decisión inicial de conservar
Instructor/LiteLLM también para este generador. El enunciado exige
`client.responses.parse`; la referencia `3292744` sigue utilizando el wrapper
Instructor y no aporta una implementación de Responses para copiar.

`LLMWrapper.complete_structured_responses` llama a `litellm.responses` y se usa
desde `_generate`. No se evita el wrapper ni el agregador, ni se migran sus
métodos anteriores. El reformulador, el Wizard y los demás recorridos conservan
Instructor/LiteLLM.

LiteLLM instalado y fijado en el lock es 1.103.0. Su implementación convierte
`text_format=Estimate` en `text.format` con `json_schema` y `strict=true`.
Se comprueban offline la petición nativa `/v1/responses`, el puente a Chat
Completions desactivado, ese cuerpo HTTP, los validadores Pydantic, los reintentos,
los errores y los metadatos; la aceptación por el modelo real queda en fase 2.

La elección conserva Responses API, pero no el método cliente literal
`client.responses.parse`. La validación local se hace con
`Estimate.model_validate_json` y los reintentos son del wrapper. Esta diferencia
está aceptada para conservar LiteLLM; no se presenta como equivalencia literal.
No se cambia la política de citas colgantes ni se promete verificación semántica.
