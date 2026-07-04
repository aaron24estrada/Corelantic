"""Shared-secret authentication for the web backend-for-frontend.

The API is reachable in production, so the network is not a trust boundary: the web BFF
presents this secret on every business request. Fail-closed — if the secret is not
configured, guarded routes answer 503 rather than allowing unauthenticated access.
"""

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.core.config import Settings, get_settings


def require_internal_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    x_internal_api_key: Annotated[str | None, Header(alias="X-Internal-Api-Key")] = None,
) -> None:
    expected = settings.internal_api_key
    if expected is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal API authentication is not configured.",
        )
    provided = x_internal_api_key or ""
    if not secrets.compare_digest(provided.encode(), expected.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing internal API key.",
        )
