# syntax=docker/dockerfile:1.7

# ---------- builder ----------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Resolved from the lockfile alone, so this layer survives every source edit.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# `semantic/` is data the app reads at runtime, not packaging metadata, so it travels separately
# from the wheel (pyproject packages only `app`).
COPY app ./app
COPY semantic ./semantic
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev


# ---------- runtime ----------
FROM python:3.12-slim AS runtime

# pyodbc links against msodbcsql18, and unixodbc is its driver manager. Microsoft ships these for
# Debian only, which is why this image is slim rather than alpine.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
 && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
      | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
 && echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
      > /etc/apt/sources.list.d/mssql-release.list \
 && apt-get update \
 && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 unixodbc \
 && apt-get purge -y curl gnupg \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 corelantic

WORKDIR /app
COPY --from=builder --chown=corelantic:corelantic /app /app

# The default semantic dir resolves relative to the package, which moves depending on whether the
# project was installed editable. Naming it removes the guesswork.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    CORELANTIC_API_HOST=0.0.0.0 \
    CORELANTIC_API_PORT=8080 \
    CORELANTIC_API_SEMANTIC_DIR=/app/semantic

USER corelantic
EXPOSE 8080

# Probes with the interpreter already on PATH, rather than adding curl back for one request.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/v1/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
