from fastapi import FastAPI

from src.routers.estimations import router as estimations_router


app = FastAPI(
	title="Estimador CAG",
	description=(
		"API para generar estimaciones de proyectos de software a partir de "
		"transcripciones de reuniones y ejemplos históricos."
	),
)
app.include_router(estimations_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
	return {"status": "ok"}
