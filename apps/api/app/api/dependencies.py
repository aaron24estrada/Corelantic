"""Shared dependencies and typed injection aliases.

The registry is loaded once and cached; providers are built per request from settings so
an unconfigured provider surfaces as a clean 503 at the point of use.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.adapters.data.base import DataSource
from app.adapters.factory import build_data_source, build_llm
from app.core.config import Settings, get_settings
from app.semantic.models import SemanticRegistry
from app.semantic.registry import load_registry
from app.services.agent.orchestrator import Orchestrator

SettingsDep = Annotated[Settings, Depends(get_settings)]


@lru_cache
def get_registry() -> SemanticRegistry:
    return load_registry(get_settings().semantic_dir)


RegistryDep = Annotated[SemanticRegistry, Depends(get_registry)]


def get_data_source(settings: SettingsDep) -> DataSource:
    return build_data_source(settings)


DataSourceDep = Annotated[DataSource, Depends(get_data_source)]


def get_orchestrator(settings: SettingsDep, registry: RegistryDep) -> Orchestrator:
    llm = build_llm(settings)
    data_source = build_data_source(settings)
    return Orchestrator(llm=llm, registry=registry, data_source=data_source)


OrchestratorDep = Annotated[Orchestrator, Depends(get_orchestrator)]
