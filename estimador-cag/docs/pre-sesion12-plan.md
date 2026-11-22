# Pre-sesión 12: plan del agente de estimación

## Punto de partida

El objetivo es añadir un agente al servicio IA sin sustituir el pipeline actual.
Se ejecutará desde consola, no desde una pantalla nueva ni un endpoint nuevo.
Streamlit y la API existente seguirán como están.

Los materiales del ejercicio ya están en
[`exercises/session-12/`](../exercises/session-12/). El
[`README.md`](../exercises/session-12/README.md) describe la solución del
instructor, no la nuestra.
Su `example_trace_complex.txt` es una muestra de referencia, no una ejecución
propia y no debe entregarse como tal.

El resultado será una estimación por componentes, en horas, y una traza de
decisiones, llamadas a herramientas y resultados. El ejemplo complejo menciona
cuatro piezas: backend, integración SAP, aplicación móvil y panel de analítica.
El agente debe identificar más de un componente y hacer más de una búsqueda;
no se puede garantizar de antemano qué resultados encontrará ni qué resumirá
el modelo.

**Prerrequisito:** partimos de la hipótesis de que el corpus de la sesión 11
ya está disponible y es suficiente para este ejercicio. No se contempla
modificarlo ni cargar datos en esta sesión.

Se usará `gpt-5` con razonamiento `medium` para la entrega. La fase 2 es
**sin asistencia de IA para la persona**, pero el agente sí necesita llamar al
modelo: esas llamadas y los embeddings tienen coste.

## Fase 1: con IA, sin servicios ni descargas

Aquí se hace todo el porting y se deja preparada la guía de ejecución. No se
levantan ni usan servicios, aunque ya estén encendidos; tampoco se descargan
dependencias, modelos o paquetes, ni se hacen llamadas externas al modelo.
Si falta algo para una prueba, se anota el bloqueo y se pasa esa comprobación
a la fase 2. Una prueba con dobles no demuestra que la ejecución real funcione.

### 1. Construir el agente

- [x] Adaptar la idea de la solución del instructor, no copiarla a ciegas. El
  bucle decidirá qué herramientas ejecutar, devolverá cada resultado con su
  `call_id` y continuará con `previous_response_id`. Debe terminar de forma
  natural y tener un límite de iteraciones; si alcanza el límite, debe decirlo
  sin presentar una estimación incompleta como válida.
- [x] Ampliar el [wrapper de LLM](../src/services/llm_wrapper.py) para soportar
  esta conversación con tools mediante Responses, conservando el aislamiento
  de la transcripción como dato no confiable, los errores, el timeout y la
  observabilidad. El método actual devuelve una respuesta estructurada, pero
  no expone el bucle de herramientas; no basta con llamarlo tal cual.
- [x] Definir las tres herramientas con esquemas planos de Responses y
  `strict: true`: `search_budgets`, `calculate_estimate` y la opcional
  `validate_estimate`, que hemos decidido incluir. Nombres, descripciones,
  parámetros, código y logs del agente irán en inglés.
- [x] Conectar la búsqueda al
  [retriever existente](../src/generation/rag/retriever.py), usando búsqueda
  híbrida y reranking, sin reconstruirlos. Devolver referencias con sus horas
  y metadatos; no dar por hecho que todos los resultados tienen horas.
- [x] Calcular el desglose y el total con Python determinista, tomando el
  [esqueleto](../exercises/session-12/calculate_estimate_skeleton.py) como
  punto de partida. Señalar los componentes sin referencias, sin inventar
  cifras. La validación revisará referencias ausentes, rangos y suma del total.
- [x] Registrar la traza ordenada y legible. Pedir resúmenes de razonamiento,
  pero no inventarlos si la API no los devuelve: indicarlo explícitamente.
  Cuando varias llamadas compartan una decisión, reflejar esa relación.
- [x] Crear `scripts/run_agent_s12.py` para aceptar una ruta de transcripción,
  `--model`, `--effort`, `--max-iterations`, `--stub` y `--out`. Imprimirá
  traza, estimación y motivo de parada; devolverá un código de error si no hay
  una estimación válida. No sobrescribirá silenciosamente una traza existente.
  `--stub` usará los datos ficticios del ejercicio solo para depuración.
- [x] Documentar el comando y sus opciones en el README del proyecto. Mantener
  sin cambios el contrato actual de estimación, su idempotencia y las pantallas.

Implementación: [bucle](../src/generation/agentic/agent.py),
[herramientas](../src/generation/agentic/tools.py),
[wrapper](../src/services/llm_wrapper.py) y
[ejecutable](../scripts/run_agent_s12.py). La validación con avisos se muestra
con `STOP: validation_issues` y devuelve un código distinto de cero, aunque
conserva el resultado parcial para revisión.

### 2. Comprobar sin conexión y dejar el relevo

- [x] Añadir y ejecutar pruebas aisladas del bucle y del wrapper: varias
  llamadas en un turno, correspondencia de `call_id`, continuación, parada
  natural y por límite, errores, salida estructurada y traza con y sin resumen.
- [x] Probar cálculo y validación, especialmente referencias vacías y total
  incoherente; comprobar que la búsqueda adapta sus argumentos al retriever
  existente. Verificar que la configuración obliga a híbrido y reranking.
- [x] Ejecutar las pruebas relevantes existentes del wrapper y de idempotencia,
  además del lint aplicable, usando únicamente herramientas ya instaladas.
  Revisar antes que las pruebas no contacten servicios. Si falta una
  dependencia, anotar el comando y el motivo aquí para repetirlo en fase 2.
- [x] Actualizar los comandos de la fase 2 si la implementación final cambia
  alguna ruta u opción; comprobar que el script realmente admite cada comando
  publicado. Anotar en este archivo qué se ha ejecutado y qué queda pendiente.
  No marcar como completada una comprobación online antes de hacerla.

**Salida de la fase 1:** agente, pruebas y documentación terminados; sin una
traza real todavía. La fase 2 empieza solo cuando la persona decida ejecutarla.

Evidencia offline desde `estimador-cag/`:

```bash
PYTHONPATH=src:. HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/pytest -q tests/test_agent_s12.py tests/test_llm_wrapper.py tests/test_idempotency.py
PYTHONPATH=src:. HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python scripts/run_agent_s12.py --help
.venv/bin/ruff check src/generation/agentic src/services/llm_wrapper.py scripts/run_agent_s12.py tests/test_agent_s12.py tests/test_llm_wrapper.py --ignore PIE810
.venv/bin/ruff format --check src/generation/agentic scripts/run_agent_s12.py tests/test_agent_s12.py
```

Resultado: 33 pruebas pasaron, con dos avisos de deprecación de dependencias;
la ayuda, el lint con esa exclusión y el formato de los archivos nuevos
pasaron. Las pruebas usan dobles y transporte HTTP simulado; no prueban OpenAI
ni los servicios reales. El lint completo señala `PIE810` en una línea
preexistente del wrapper, comprobada también en `HEAD`; se excluye esa regla
para revisar el resto sin modificar código ajeno al ejercicio.

## Fase 2: manual, con servicios y sin asistencia de IA

Ejecuta los pasos en orden desde una terminal. No hace falta Streamlit. Los
comandos del agente que aparecen abajo se verificaron sin servicios; antes de
continuar, comprueba su ayuda en tu entorno.

### 1. Preparar el entorno

1. Sitúate en el proyecto:

   ```bash
   cd /home/basf/wsTakeoff/ai-engineering/estimador-cag
   git status --short --branch
   ```

   Comprueba que estás en `session-12/pre-work` y que tienes los cambios de la
   fase 1. No descartes cambios que no reconozcas.

2. Necesitas Docker con Compose, `uv`, acceso a OpenAI y permiso para consumir
   API. Revisa `.env` **sin publicar su contenido**: necesita una
   `OPENAI_API_KEY` válida y `LLM_TIMEOUT=600`. Si no existe `.env`, copia
   `.env.example` a `.env` y completa la clave de OpenAI en un editor. No
   sustituyas un `.env` existente ni incluyas claves en capturas, trazas,
   comandos compartidos o Git.

3. Instala las dependencias del proyecto y las de desarrollo, desde el lock:

   ```bash
   uv sync --locked
   ```

   Si falla, lee el error y resuelve primero la instalación; no continúes con
   una validación parcial. Ejecuta las pruebas offline que la fase 1 haya
   dejado bloqueadas y anota su resultado.

4. Comprueba la interfaz del ejecutable:

   ```bash
   uv run --no-sync python scripts/run_agent_s12.py --help
   ```

   Deben aparecer las opciones indicadas en la fase 1. Si no aparece el
   script o alguna opción, para: el porting o esta guía están incompletos.

### 2. Arrancar y comprobar los servicios

**Antes de arrancar:** Compose publica los puertos 8000, 6379, 8001 y 5432,
usa volúmenes persistentes y aplica migraciones al iniciar la API. En un
entorno compartido, confirma que puedes usar esos recursos y modificar esa
base de datos. No borres volúmenes ni datos como medida de diagnóstico.
El build puede descargar imágenes y dependencias.

```bash
docker compose up -d --build
docker compose ps
curl -fsS http://localhost:8000/health
```

Espera a que `estimator`, `redis` y `postgres` aparezcan saludables. El
`health` debe devolver `status: healthy`; eso no prueba que OpenAI ni el
agente funcionen. Consulta los logs si un servicio no arranca:

```bash
docker compose logs --tail=100 estimator postgres redis
```

### 3. Probar primero el recorrido sencillo

El stub evita la base de datos para la búsqueda, pero **no** evita la llamada
de pago al modelo. Sirve para comprobar el bucle, no para acreditar la
recuperación real:

```bash
uv run --no-sync python scripts/run_agent_s12.py exercises/session-12/sample_transcript_simple.txt --model gpt-5-mini --effort minimal --stub
```

Comprueba que se ven pasos con acción y observación, que se indica el
razonamiento disponible y que aparece una estimación final con parada normal.
Si falta un resumen, debe constar como no disponible, no como texto inventado.
Si falla, consulta el apartado de problemas antes de gastar en la prueba final.

### 4. Ejecutar y revisar la entrega

Comprueba primero que `session12-trace-complex.txt` no existe o elige otro
nombre para no perder una ejecución anterior. Después ejecuta con el retrieval
real, sin `--stub`:

```bash
uv run --no-sync python scripts/run_agent_s12.py exercises/session-12/sample_transcript_complex.txt --model gpt-5 --effort medium --out session12-trace-complex.txt
```

Abre el fichero y verifica manualmente:

- La ejecución terminó de forma natural, no por límite ni por error.
- Hay más de un componente y más de una llamada a `search_budgets`.
- Se llamó a `calculate_estimate` con componentes y horas de referencia, y a
  `validate_estimate` antes de la respuesta final.
- Cada paso muestra decisión o su ausencia explícita, acción con argumentos y
  observación. Si faltan resúmenes de razonamiento, la traza no cumple
  plenamente el requisito: no los inventes ni la des por entregable.
- Las referencias corresponden al alcance, los componentes sin referencia
  están señalados, los parciales suman el total y los avisos de validación
  quedan resueltos o claramente indicados. Una suma correcta por sí sola no
  demuestra que las referencias sean pertinentes.

Si el comando acaba con `STOP: validation_issues`, conserva la estimación y
los avisos para revisarlos: el código de salida no es cero. Si falta algún
criterio, conserva la traza como evidencia de fallo; no la
entregues como éxito. Corregir el problema puede requerir cambios de código o
revisión humana antes de repetir la ejecución de pago.

La entrega es el enlace a este repositorio con el agente publicado y la traza
propia. Revisa la traza antes de compartirla: no debe contener claves ni datos
que no esté permitido divulgar. No sustituyas el resultado por el ejemplo del
instructor.

### 5. Si algo falla

| Síntoma | Qué hacer |
|---|---|
| `uv sync --locked` falla | Lee el paquete o conflicto indicado y corrige el entorno antes de continuar. No cambies el lock a ciegas. |
| Puerto ocupado o contenedor no saludable | Mira `docker compose ps` y los logs anteriores. Comprueba quién usa el puerto y coordínalo antes de parar o cambiar servicios compartidos. |
| Error de migración o base de datos | Revisa los logs de `estimator` y `postgres`; detente antes de modificar el esquema o borrar datos. |
| Error de OpenAI, cuota o timeout | Comprueba clave, acceso al modelo, cuota y `LLM_TIMEOUT`. El `health` solo indica configuración general. Evita repetir llamadas de pago sin revisar el error. |
| No hay referencias, o no encajan con el componente | Revisa filtros, horas y alcance de las referencias. No rellenes cifras a mano ni uses el stub para fingir que hay evidencia real; si no puedes resolverlo, conserva la traza y detente. |
| Error al cargar el reranker | Revisa el mensaje y el acceso al modelo configurado. La primera carga puede necesitar descarga; no declares que hubo reranking si no se ha ejecutado. |
| Bucle sin terminar, total incorrecto o falta razonamiento | Guarda el fallo, revisa la traza y los logs y corrige la causa antes de repetir. No aumentes el límite ni aceptes una respuesta parcial como solución automática. |

Al terminar, deja los servicios en el estado acordado con las demás personas
que usen el entorno; no los detengas ni elimines datos sin comprobarlo.
