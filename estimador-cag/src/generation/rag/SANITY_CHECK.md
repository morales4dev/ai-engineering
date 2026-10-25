# Pair 1

| Campo | Valor |
|---|---|
| Text A | OAuth 2.0 authentication backend with JWT tokens for fintech mobile app |
| Text B | Authorization service using JSON Web Tokens for a banking application |
| Cosine similarity | 0.5957 |

# Pair 2

| Campo | Valor |
|---|---|
| Text A | OAuth 2.0 authentication backend with JWT tokens for fintech mobile app |
| Text B | Database migration from MySQL to PostgreSQL with zero downtime |
| Cosine similarity | 0.1920 |

# Pair 3

| Campo | Valor |
|---|---|
| Text A | Backend services |
| Text B | API development |
| Cosine similarity | 0.5407 |

## Comentario

La pareja 1 (0.5957) puntúa por encima de la 2 (0.1920): autenticación/JWT/banca frente a autenticación vs. migración de base de datos. Encaja con discriminar textos cercanos y lejanos.

Llama la atención la pareja 3: 0.5407, a 0.055 de la 1 y lejos de la 2. Dos frases cortas (“Backend services” / “API development”) quedan casi al nivel de dos textos del mismo servicio. Queda registrado.

Esto no es una validación formal del modelo. Es el mínimo: hay tres cosenos y el par lejano queda claramente más bajo que el cercano.
