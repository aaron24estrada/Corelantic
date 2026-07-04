"""Application factory and wiring."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.adapters.factory import ProviderNotConfiguredError
from app.api.middleware import request_context_middleware
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.semantic.errors import SemanticError

logger = logging.getLogger("corelantic.error")


def _unique_operation_id(route: APIRoute) -> str:
    tag = route.tags[0] if route.tags else "default"
    return f"{tag}-{route.name}"


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title="Corelantic API",
        version="0.1.0",
        generate_unique_id_function=_unique_operation_id,
    )
    app.middleware("http")(request_context_middleware)
    app.include_router(api_router)

    @app.exception_handler(SemanticError)
    async def _handle_semantic_error(_: Request, exc: SemanticError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ProviderNotConfiguredError)
    async def _handle_not_configured(_: Request, exc: ProviderNotConfiguredError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        # Log with the traceback (carrying the request id); never leak internals to the client.
        logger.exception("unhandled exception")
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})

    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
