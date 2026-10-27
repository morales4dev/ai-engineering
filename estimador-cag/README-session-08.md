Pregunta a) por que dos tablas y no una?
Se llama "normalizacion"? en BDD relacionales. no repetir info en varias filas de una tabla, se saca a otra tabla con relacion n-1.
Pregunta b) la metadata en json en vez de columnas para tener flexibilidad. Si cambia la metadata no hay que
cambiar el esquema.
Pregunta c) por si en el futuro se migra a un modelo de embeddings que no se normaliza.
Pregunta d) para que podamos observar cuanto tarda con secuencial, y de esta forma apreciar/distinguir/medir
la mejora con el uso del índice.