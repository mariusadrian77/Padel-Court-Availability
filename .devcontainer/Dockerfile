FROM python:3.11-slim

# Combine all ENV variables in one layer
ENV POETRY_VERSION=1.8.2 \
    POETRY_HOME=/opt/poetry \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR=/tmp/poetry_cache \
    PATH="/opt/poetry/bin:$PATH" \
    WORKING_DIR=/code

# Install system dependencies including build tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* && \
    curl -sSL https://install.python-poetry.org | python3 - && \
    poetry --version

WORKDIR $WORKING_DIR

# Copy only what's needed for dependency installation
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry install --no-root --only main && \
    rm -rf $POETRY_CACHE_DIR

# Copy application code last
COPY . .
