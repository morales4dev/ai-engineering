He revisado los cambios de vuestra rama y los he contrastado con el live del instructor. La idea central es esta: ahora el estimador puede partir de una conversación, buscar trabajos anteriores parecidos y enseñar qué fuentes ha utilizado para construir una estimación. En vuestro repositorio se prueba desde **Streamlit**, no desde la aplicación Rails del instructor, y el historial se guarda en vuestro PostgreSQL.

## 1. Arrancar el entorno

Desde una terminal, entrad en el proyecto:

```bash
cd /home/basf/wsTakeoff/ai-engineering/estimador-cag
```

Necesitáis Docker con Compose, Python 3.11 o superior, `uv` y una clave de OpenAI con acceso a los modelos configurados. En este entorno ya existe un archivo [.env](/home/basf/wsTakeoff/ai-engineering/estimador-cag/.env): revisadlo sin sobrescribirlo. Para esta prueba comprobad especialmente:

- `OPENAI_API_KEY`: se usa tanto para los embeddings como para los modelos.
- `ESTIMATE_API_KEY` y `RETRIEVAL_API_KEY`: son dos claves **propias de la aplicación**, distintas de la de OpenAI. La primera permite estimar; la segunda solo permite buscar.
- `LLM_TIMEOUT=600`. Por defecto, la reformulación usa `gpt-5-mini` y la generación, `gpt-5`; esta última puede tardar varios minutos y tener coste.

Los valores de ejemplo están explicados en [.env.example](/home/basf/wsTakeoff/ai-engineering/estimador-cag/.env.example). Si cambiáis el `.env`, recread el servicio para que recoja la configuración.

En la máquina que he consultado está disponible `docker-compose` —con guion—, pero no el plugin `docker compose`. Usando esa variante:

```bash
docker-compose up -d --build
docker-compose ps
```

Compose levanta la API, PostgreSQL con pgvector y Redis. Al arrancar la API aplica las migraciones, incluida la tabla nueva para las ejecuciones del asistente. Comprobad que los servicios están activos y abrid [http://localhost:8000/health](http://localhost:8000/health) y [http://localhost:8000/docs](http://localhost:8000/docs).

En otra terminal, desde el mismo directorio, instalad las dependencias y arrancad la interfaz:

```bash
uv sync
uv run streamlit run streamlit_app.py
```

Abrid la dirección que indique Streamlit, normalmente [http://localhost:8501](http://localhost:8501). No hace falta arrancar Rails ni una segunda base de datos.

## 2. Preparar los datos si PostgreSQL está vacío

Las migraciones crean las tablas, pero **no cargan automáticamente ejemplos para buscar**. Si no hay datos, podréis empezar el recorrido, pero no habrá antecedentes con los que fundamentar una estimación.

Hay dos corpus incluidos, complementarios:

1. **Los 12 proyectos sintéticos de la sesión 9**, con tareas agrupadas por módulos. Son especialmente útiles para ver el nuevo desglose fino. El archivo [task_corpus.json](/home/basf/wsTakeoff/ai-engineering/estimador-cag/data/task_corpus.json) ya está en el repo; no hace falta generarlo de nuevo. Para cargarlo:

   ```bash
   docker-compose exec -T estimator python scripts/s09/build_task_corpus.py --ingest-only
   ```

2. **Los 17 presupuestos de ejemplo de la sesión 8**, más gruesos: cada fragmento representa un componente de presupuesto. Son opcionales, pero permiten comparar ambos tipos de evidencia:

   ```bash
   docker-compose exec -T estimator python scripts/query_examples.py
   ```

   Este segundo comando también ejecuta cinco búsquedas de ejemplo y muestra sus resultados.

Ambas cargas llaman a OpenAI para crear los embeddings y pueden tener coste. Los scripts omiten los documentos que ya estaban cargados, por lo que podéis repetirlos si una carga se interrumpe.

Para comprobar qué hay realmente en la base:

```bash
docker-compose exec -T postgres psql -U postgres -d estimator -c \
  "SELECT document_type, count(*) FROM documents GROUP BY 1 ORDER BY 1;"

docker-compose exec -T postgres psql -U postgres -d estimator -c \
  "SELECT chunk_type, count(*) FROM chunks GROUP BY 1 ORDER BY 1;"
```

Con la base inicialmente vacía y ambas cargas completas deberíais ver **12** documentos `historical_task_breakdown` y **17** `historical_budget`. El corpus de tareas incluido contiene **222 tareas**. Son datos sintéticos, no presupuestos reales: sirven para entender el mecanismo, no para tomar sus cifras como verdad de negocio.

## 3. Recorrer la funcionalidad

En Streamlit, abrid **RAG Wizard**. Podéis pegar una conversación de al menos 100 caracteres o subir un `.txt` UTF-8. Por ejemplo:

> Queremos crear una plataforma de comercio electrónico para vender productos online. Necesitamos un catálogo con búsqueda, carrito y checkout, integración con una pasarela de pago, acceso seguro para clientes y un panel para consultar pedidos. La solución debe exponer una API y disponer de una interfaz web. En la reunión todavía no hemos decidido el equipo ni la fecha de entrega.

1. **Empezad con “Start guided estimation”.** El primer resultado es una *reformulación*: comparad el texto original con el **Brief** y el **Search text**. La aplicación intenta separar lo que se quiere construir del ruido de la conversación y producir una búsqueda técnica más concisa. Fijaos también en si deja sin completar lo que no se ha dicho, en lugar de inventarlo.

2. **Ejecutad “Run / re-run retrieval”.** Veréis los fragmentos históricos encontrados, su sector, año, tipo y distancia. Una distancia menor significa mayor similitud; el umbral inicial es `0.6`. Probad a seleccionar `ecommerce` y después a cambiar el umbral o el rango de años: observad cómo cambian los candidatos y resultados. El sector reconocido en el brief puede aplicarse por defecto.

   Si aparece **Low confidence**, significa que ningún fragmento ha superado el filtro de relevancia. Probad un umbral más permisivo o filtros menos restrictivos, pero mirad si los resultados siguen siendo realmente pertinentes: recuperar algo no equivale a recuperar buena evidencia.

3. **Pulsad “Assemble context”.** Abrís así el bloque **Assembled `<source>` block**, que es el material que se enviará al modelo. Comparad sus identificadores y contenido con los resultados anteriores. La pantalla también indica cuántos fragmentos se conservaron o descartaron para respetar el límite de contexto.

4. **Pulsad “Generate estimate”.** Puede tardar varios minutos. La salida se organiza en módulos y tareas, con esfuerzo en *días de ingeniero*, fuentes, supuestos y un nivel de confianza. Comparad los **Source IDs** con los fragmentos recuperados: esa trazabilidad es la diferencia importante frente a una cifra sin justificación.

   Si aparecen avisos de identificadores inventados o de incoherencia, tratadlos como señales para revisar el resultado. Incluso sin avisos, que un identificador exista no demuestra que la estimación sea correcta: hay que leer la fuente y juzgar si realmente respalda la tarea.

5. **Revisad la propuesta humana.** En **Human verification**, cambiad los días de una tarea o añadid una fila y pulsad **Save human version**. Comprobad que cambia el total humano, mientras que la versión original del modelo permanece visible y sin modificar.

6. **Comprobad la persistencia.** En **Execution history**, abrid la ejecución guardada. Después probad a repetir la búsqueda o la reformulación: las etapas posteriores se limpian para que una estimación antigua no parezca válida con fuentes nuevas. Tendréis que volver a ensamblar y generar.

Como prueba negativa, usad filtros que no devuelvan resultados. El wizard avisa de que no hay evidencia; permite continuar, así que no interpretéis una generación posterior como fundamentada. La API de recorrido completo, `POST /v1/estimate/from-transcript`, se comporta de forma distinta: ante ausencia de resultados devuelve contexto insuficiente sin generar una cifra.

## 4. Una mirada rápida a la API

En [http://localhost:8000/docs](http://localhost:8000/docs) podéis localizar los endpoints nuevos: la búsqueda independiente `/v1/retrieval/search`, la estimación completa `/v1/estimate/from-transcript` y las etapas persistidas bajo `/v1/estimate/runs`. Estos últimos son los que utiliza el wizard; la estimación completa de una sola llamada **no** crea una entrada en su historial.

Como comprobación sencilla de seguridad, una petición a un endpoint protegido sin `X-API-Key` debe responder **401**. La clave de búsqueda no debe permitir generar estimaciones, ni la de estimación acceder al endpoint independiente de búsqueda. Las rutas también tienen límites de peticiones y devuelven un `X-Request-ID` útil para localizar errores en los logs.

**Nota sobre la verificación:** he comprobado el código, los corpus y el estado local, pero no he lanzado servicios ni llamadas de pago. En el momento de la consulta los contenedores estaban detenidos.
