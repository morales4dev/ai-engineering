# Sesión 11: decisiones de portado y diferencias conocidas

## Contexto y estado

Este registro acompaña al [plan de implementación](pre_sesion11_plan.md).
Referencia del instructor: rama `session_11`, commit
`3292744c12c69f88b10ed8c851ae9fb733e2667d`
(`solved pre exercise session 11`), comparado con `session_10_live`.

No usar como referencia el commit posterior `8695e8b`, que incorpora la sesión
completa y está fuera del alcance aprobado.

Esta nota registra una decisión previa a implementar. No demuestra que el
golden se haya copiado, que el prompt se haya modificado ni que se haya ejecutado
RAGAS en el alumno.

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

**Elegida la opción 2 el 17 de noviembre de 2026.**

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

### Comprobaciones pendientes de implementación

- [ ] El contenido del golden del alumno coincide con el del instructor en
  `3292744`, incluidas sus cifras aproximadas.
- [ ] El prompt no incorpora la aclaración adicional de conversión rechazada.
- [ ] El corpus original no se ha alterado para acomodar el golden.
- [ ] La documentación de la baseline enlaza esta limitación conocida sin
  atribuirle causas que no se hayan demostrado.
- [ ] Los resultados de la baseline son propios del alumno, no copiados de LIDR.

Marcar las casillas solo después de comprobar cada punto y añadir evidencia,
siguiendo las reglas de seguimiento del plan.
