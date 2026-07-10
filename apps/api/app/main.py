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
from app.query.errors import IntentError
from app.schemas.error import ErrorResponse
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

    def _body(response: ErrorResponse, status_code: int) -> JSONResponse:
        return JSONResponse(status_code=status_code, content=response.model_dump())

    @app.exception_handler(IntentError)
    async def _handle_intent_error(_: Request, exc: IntentError) -> JSONResponse:
        # The intent named vocabulary the model does not offer. Unprocessable, not missing —
        # and `allowed` says what would have worked, so the caller can repair rather than retry.
        return _body(
            ErrorResponse(detail=str(exc), code=exc.code, field=exc.field, allowed=exc.allowed),
            422,
        )

    @app.exception_handler(SemanticError)
    async def _handle_semantic_error(_: Request, exc: SemanticError) -> JSONResponse:
        return _body(ErrorResponse(detail=str(exc)), 404)

    @app.exception_handler(ProviderNotConfiguredError)
    async def _handle_not_configured(_: Request, exc: ProviderNotConfiguredError) -> JSONResponse:
        return _body(ErrorResponse(detail=str(exc)), 503)

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        # Log with the traceback (carrying the request id); never leak internals to the client.
        logger.exception("unhandled exception")
        return _body(ErrorResponse(detail="Internal server error."), 500)

    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
