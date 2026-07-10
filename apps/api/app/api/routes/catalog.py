from fastapi import APIRouter

from app.api.dependencies import RegistryDep
from app.schemas.catalog import CatalogResponse
from app.services.catalog import build_catalog

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("", response_model=CatalogResponse)
async def get_catalog(registry: RegistryDep) -> CatalogResponse:
    """The vocabulary an intent may draw on, and what each metric admits.

    Read this before composing an intent: it is the difference between a planner that asks a
    valid question and one that guesses, then reads a 422 to find out.
    """

    return build_catalog(registry)
