# Base image: Python slim for a lightweight container
FROM python:3.11-slim

# Define environment variables with default values
# These can be overridden during container runtime
ENV BASE_URL="lode.opencitations.net"

# Ensure Python output is unbuffered
ENV PYTHONUNBUFFERED=1

# Install system dependencies + uv
RUN apt-get update && \
    apt-get install -y \
    git \
    python3-dev \
    build-essential \
    curl && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Make uv available in PATH
ENV PATH="/root/.local/bin:$PATH"

# Set the working directory for our application
WORKDIR /website

# Copy dependency files first for better Docker layer caching
COPY pyproject.toml uv.lock README.md ./

# Install dependencies (frozen = use exact lockfile versions)
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY . .

# Expose the port that our service will listen on
EXPOSE 8080

# Start the application with gunicorn via uv
CMD ["uv", "run", "gunicorn", "-c", "gunicorn.conf.py", "lode.api:app"]