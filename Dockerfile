# Base image: Python slim for a lightweight container
FROM python:3.11-slim

# Environment defaults (overridable at runtime)
ENV BASE_URL="lode.opencitations.net"
ENV PYTHONUNBUFFERED=1

# System dependencies + uv (installed to a system path so a non-root user can use it)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        python3-dev \
        build-essential \
        curl && \
    curl -LsSf https://astral.sh/uv/install.sh | \
        env UV_INSTALL_DIR=/usr/local/bin INSTALLER_NO_MODIFY_PATH=1 sh && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Non-root user that owns the app and runs the server
RUN useradd --create-home --uid 10001 appuser

WORKDIR /website
RUN chown appuser:appuser /website

# Drop privileges before building and running: the venv and the runtime spool
# directory end up owned by appuser, so no root is needed at any point.
USER appuser

# Install dependencies first for better layer caching (frozen = exact lockfile)
COPY --chown=appuser:appuser pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Application code
COPY --chown=appuser:appuser . .

# At runtime uv must only launch the entrypoint, never re-sync the prebuilt env
ENV UV_NO_SYNC=1

# Service port (>1024, bindable by a non-root user)
EXPOSE 8080

# Start the application with gunicorn via uv
CMD ["uv", "run", "gunicorn", "-c", "gunicorn.conf.py", "lode.api:app"]
