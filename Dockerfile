### BUILD LECmd locally with a git clone
# Use the official Dotnet SDK 9.0 base image from Microsoft (Ubuntu 24.04 Noble)
FROM mcr.microsoft.com/dotnet/sdk:9.0-noble AS build-lecmd

ARG LECMD_GIT_REPO_URL=https://github.com/EricZimmerman/LECmd.git
ARG LECMD_GIT_BRANCH=master # Or specify a tag like 'v1.5.1.0' or a commit hash
RUN git clone --branch ${LECMD_GIT_BRANCH} --depth 1 ${LECMD_GIT_REPO_URL} /tmp/LECmd_source_build
WORKDIR /tmp/LECmd_source_build
RUN dotnet publish ./LECmd/LECmd.csproj --framework net9.0 -c Release --no-self-contained -o /opt/LECmd_built_from_source
WORKDIR /
RUN rm -rf /tmp/LECmd_source_build



### BUILD RBCmd locally with a git clone
# Use the official Dotnet SDK 9.0 base image from Microsoft (Ubuntu 24.04 Noble)
FROM mcr.microsoft.com/dotnet/sdk:9.0-noble AS build-rbcmd

ARG RBCmd_GIT_REPO_URL=https://github.com/EricZimmerman/RBCmd.git
ARG RBCmd_GIT_BRANCH=master # Or specify a tag like 'v1.5.1.0' or a commit hash
RUN git clone --branch ${RBCmd_GIT_BRANCH} --depth 1 ${RBCmd_GIT_REPO_URL} /tmp/RBCmd_source_build
WORKDIR /tmp/RBCmd_source_build
RUN dotnet publish ./RBCmd/RBCmd.csproj --framework net9.0 -c Release --no-self-contained -o /opt/RBCmd_built_from_source
WORKDIR /
RUN rm -rf /tmp/RBCmd_source_build

# --- Build AppCompatCacheParser ---
# Use the official Dotnet SDK 9.0 base image from Microsoft (Ubuntu 24.04 Noble)
FROM mcr.microsoft.com/dotnet/sdk:9.0-noble AS build-accp

ARG ACC_REPO_URL=https://github.com/EricZimmerman/AppCompatCacheParser.git
ARG ACC_SRC_DIR_TMP=/tmp/AppCompatCacheParser_src

RUN git clone ${ACC_REPO_URL} ${ACC_SRC_DIR_TMP}

# The AppCompatCacheParser.csproj is inside a subdirectory named 'AppCompatCacheParser'
RUN cd ${ACC_SRC_DIR_TMP}/AppCompatCacheParser && \
    dotnet publish AppCompatCacheParser.csproj \
    -c Release \
    --framework net9.0 \
    -o /app/publish_acc \
    --no-self-contained \
    /p:UseAppHost=false


# Use the official Dotnet Runtime 9.0 base image from Microsoft (Ubuntu 24.04 Noble)
FROM mcr.microsoft.com/dotnet/runtime:9.0-noble AS final

# Prevent needing to configure debian packages, stopping the setup of
# the docker container.
RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections
# Install Poetry
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-poetry \
    && rm -rf /var/lib/apt/lists/*

# Configure poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

# Configure debugging
ARG OPENRELIK_PYDEBUG
ENV OPENRELIK_PYDEBUG=${OPENRELIK_PYDEBUG:-0}
ARG OPENRELIK_PYDEBUG_PORT
ENV OPENRELIK_PYDEBUG_PORT=${OPENRELIK_PYDEBUG_PORT:-5678}

# Set working directory
WORKDIR /openrelik

# Copy poetry toml and install dependencies
COPY ./pyproject.toml ./poetry.lock ./
RUN poetry install --no-interaction --no-ansi

# Copy files needed to build
COPY . ./

# Install the worker and set environment to use the correct python interpreter.
RUN poetry install && rm -rf $POETRY_CACHE_DIR
ENV VIRTUAL_ENV=/app/.venv PATH="/openrelik/.venv/bin:$PATH"

# Copy Binaries to Final image
COPY --from=build-lecmd /opt/LECmd_built_from_source /opt/LECmd_built_from_source
COPY --from=build-rbcmd /opt/RBCmd_built_from_source /opt/RBCmd_built_from_source
COPY --from=build-accp /app/publish_acc/* /opt/AppCompatCacheParser_built_from_source/

# Default command if not run from docker-compose (and command being overidden)
CMD ["celery", "--app=src.tasks", "worker", "--task-events", "--concurrency=1", "--loglevel=INFO"]
