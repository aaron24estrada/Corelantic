"""Application factory and wiring."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.adapters.factory import ProviderNotConfiguredError
from app.api.router import api_router
from app.core.config import get_settings
from app.semantic.errors import SemanticError


def _unique_operation_id(route: APIRoute) -> str:
    tag = route.tags[0] if route.tags else "default"
    return f"{tag}-{route.name}"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Corelantic API",
        version="0.1.0",
        generate_unique_id_function=_unique_operation_id,
    )
    app.include_router(api_router)

    @app.exception_handler(SemanticError)
    async def _handle_semantic_error(_: Request, exc: SemanticError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ProviderNotConfiguredError)
    async def _handle_not_configured(_: Request, exc: ProviderNotConfiguredError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
