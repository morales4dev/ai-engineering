# Post sesión 5 — mejoras

Siete ajustes en `session_05_forense` después del commit de documentación (`678fd99`). Queda fuera `6c16d63` (regla ponytail). El tono de este documento: breve, claro y amable.

## Resumen

| # | Título | En una frase | Commit |
|---|---|---|---|
| 1 | Coste desde las fases | Python calcula `total_cost_eur` a partir del desglose, para que un error de suma no se convierta en 502. | [`0bc30dd`](https://github.com/morales4dev/ai-engineering/commit/0bc30dd1e3b28d9e09b39b5572e64eba1251d9cc) |
| 2 | El critic no suma | Se retira `math_error`: el critic ya no audita aritmética ni dispara el loop ACB por un descuadre inventado. | [`dbb2386`](https://github.com/morales4dev/ai-engineering/commit/dbb23865cc5187adc5632160dd0e577a18dd56ea) |
| 3 | Chuleta y criterio del critic | Recibe porcentajes y banda ya calculados, y acepta por defecto. Solo marca un major si un lead tomaría peor decisión. | [`45d3b26`](https://github.com/morales4dev/ai-engineering/commit/45d3b266bfe9363560344d4446dbffad3506a31a) |
| 4 | El actor estima con supuestos | Si el brief nombra producto y para quién (o un stack), se estima y se escriben los huecos. `Out of scope:` solo cuando no hay qué construir. | [`2802036`](https://github.com/morales4dev/ai-engineering/commit/28020369dff312ca35073d49113366791ca71ceb) |
| 5 | Plazo desde las fases | Igual que el coste: `total_duration_weeks` es la suma secuencial de las fases (máximo 104). | [`bb43ca9`](https://github.com/morales4dev/ai-engineering/commit/bb43ca94f07e0de25eb2f8b39dcf17658d9c18c5) |
| 6 | Una sola tarjeta de tarifas | Actor y critic anclan el precio a `equipo × semanas × (32 h × 62,50 €)`. La tarifa vive en un módulo. | [`7e57dbc`](https://github.com/morales4dev/ai-engineering/commit/7e57dbcaa8e03c2b8b1f359ee62f421e7d3be776) |
| 7 | Metadata antes de estimar | En el primer turno se leen los hechos del transcript *antes* del estimate, para que actor y critic vean el tamaño de equipo. | [`57b2b28`](https://github.com/morales4dev/ai-engineering/commit/57b2b28d5c5c640ad167a0181ca1a58602c12c71) |

## Detalle

### 1. Coste desde las fases

Los modelos se equivocan al sumar. Instructor reintentaba (hasta 6 veces) cuando las fases no coincidían con el total — por ejemplo 41 000 € frente a 36 000 € — y la API respondía 502.

En `EstimationResult` el validador ya no falla: asigna `total_cost_eur` a la suma de `phase.cost_eur`. El JSON público no cambia. Un test cubre el caso 36k vs 41k. Commit `0bc30dd`.

### 2. El critic no suma

El critic es otro modelo. Seguía “comprobando” las cuentas, etiquetaba `math_error` como critical (incluso cuando 12 coincidía con 12) y el boss gastaba las tres vueltas en caveats que no aportaban.

Se elimina `math_error` del schema y del prompt. Si el modelo la emite, Instructor la rechaza. Sigue mirando alcance, alucinaciones, equilibrio de fases, supuestos, tarifas y audiencia. Commit `dbb2386`.

### 3. Chuleta y criterio del critic

Al quitar las mates, el critic buscaba otros defectos y se inventaba majors: imbalance al 53 % (el umbral es 75 %), o un precio alto etiquetado como `scope_mismatch`. El prompt pedía prudencia; el modelo no la aplicaba.

Ahora su encargo es firmar, no cazar. Python le entrega la chuleta (`build_critic_facts`: % por fase y banda de tarifa) y el `detail_level`. Ejemplos genéricos: que la fase de build sea la mayor no es imbalance; quejarse del precio no es un fallo de alcance. Commit `45d3b26`.

### 4. El actor estima con supuestos

Con un brief suficiente (CRM, equipo, stack) el actor bajaba de 30 % de confianza y contestaba `Out of scope:`. A veces el critic daba por buena esa negativa.

Solo se toca `estimation/v3/system.j2` (el default conversacional). Lo que falte (roles, SLAs) se declara como supuesto y se estima igual. El rechazo queda para cuando no se puede nombrar el producto. El validador del prefijo si la confianza es baja no se mueve. Commit `2802036`.

### 5. Plazo desde las fases

El párrafo hablaba de 8–12 semanas, la métrica decía 8 y las fases sumaban 9. El plazo no se reconciliaba a propósito (las fases pueden solaparse), pero el modelo también fallaba esa cuenta.

El mismo validador asigna `total_duration_weeks` a `min(104, suma de fases)`, en entrega secuencial. El summary puede seguir llevando un rango: es texto libre. Commit `bb43ca9`.

### 6. Una sola tarjeta de tarifas

El mismo brief oscilaba entre 124 000 € y 20 000 €. Sin ancla de precio, cada pasada inventaba una escala.

`src/rates.py` define `DEV_WEEK_EUR = 32 × 62,50`. Los prompts (v1–v3 y critic) leen esa cifra por Jinja. El actor ve la regla `T × W × tarifa` (±30 %) y, si hay equipo, el coste de una semana. No se obliga el total: se le da la brújula. Commit `7e57dbc`.

### 7. Metadata antes de estimar

En sesión nueva el extractor corría *después* del estimate. Actor y critic no veían `assumed_team_size = 3`, la chuleta no tenía banda y el critic no podía contrastar 20 000 € con 60 000 €.

`prime_metadata_if_empty` extrae del transcript (sin estimación) cuando la metadata está vacía, *antes* del tier y del actor. El extractor de después se conserva. Si falla, se sigue con lo que hubiera (fail-open). Vale para ACB y para el path conversacional. Commit `57b2b28`.
