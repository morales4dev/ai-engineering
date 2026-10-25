import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from routers.embeddings import router as embeddings_router
from routers.config import router as config_router
from routers.estimations import router as estimations_router
from routers.ingestion import router as ingestion_router
from routers.sessions import router as sessions_router
from services.history import init_db


def configure_logging() -> None:
    """Set up structlog: JSON in production, human-readable in development."""
    settings = get_settings()

    if settings.APP_ENV == "production":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    configure_logging()
    log = structlog.get_logger()
    settings = get_settings()
    try:
        from dependencies import get_catalog

        catalog = get_catalog()
        log.info(
            "catalog_loaded",
            version=catalog.version,
            sources_total=len(catalog.sources),
            sources_included=len(catalog.included_sources()),
        )
    except Exception as exc:  # noqa: BLE001
        log.error("catalog_load_failed", error=str(exc)[:400])
    log.info("application_started", environment=settings.APP_ENV)
    init_db()
    yield
    log.info("application_shutdown")


app = FastAPI(
    title="Estimation CAG Service",
    description="AI-powered software estimation service using Cache Augmented Generation architecture",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS is off on purpose. Streamlit calls from Python, not a browser.
# Wildcard origins plus credentials is invalid CORS — Starlette would echo
# any Origin. If a browser client appears, list its origins explicitly and
# keep credentials off until you actually need cookies.
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

app.include_router(estimations_router)
app.include_router(sessions_router)
app.include_router(ingestion_router)
app.include_router(embeddings_router)
app.include_router(config_router)


@app.get("/health")
async def health_check() -> dict:
    """Liveness probe. Survives a missing API key; reports it instead of dying."""
    settings = get_settings()
    return {
        "status": "healthy",
        "version": "0.1.0",
        "environment": settings.APP_ENV,
        "llm_configured": settings.llm_configured,
    }


# if __name__ == "__main__":
#     uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)