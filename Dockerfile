# Use the official Docker Hub Ubuntu base image
FROM ubuntu:24.04

# Prevent needing to configure debian packages, stopping the setup of
# the docker container.
RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections

# Install poetry and any other dependency that your worker needs.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-poetry \
    wget \
    apt-transport-https \
    software-properties-common \
    unzip \
    git \
    # Add other apt dependencies here if needed
    && rm -rf /var/lib/apt/lists/*

# Install .NET9 (change --channel if you'd prefer a different version)
RUN wget https://builds.dotnet.microsoft.com/dotnet/scripts/v1/dotnet-install.sh -O /tmp/dotnet-install.sh
RUN chmod +x /tmp/dotnet-install.sh
RUN /tmp/dotnet-install.sh --channel 9.0
RUN rm -r /tmp/dotnet-install.sh
# Add .NET tools to PATH for subsequent RUN commands and for the final container environment
ENV PATH="/root/.dotnet:${PATH}"

### BUILD LECmd locally with a git clone
ARG LECMD_GIT_REPO_URL=https://github.com/EricZimmerman/LECmd.git
ARG LECMD_GIT_BRANCH=master # Or specify a tag like 'v1.5.1.0' or a commit hash
RUN git clone --branch ${LECMD_GIT_BRANCH} --depth 1 ${LECMD_GIT_REPO_URL} /tmp/LECmd_source_build
WORKDIR /tmp/LECmd_source_build
RUN dotnet publish ./LECmd/LECmd.csproj --framework net9.0 -c Release --no-self-contained -o /opt/LECmd_built_from_source
WORKDIR /
RUN rm -rf /tmp/LECmd_source_build

### BUILD RBCmd locally with a git clone
ARG RBCmd_GIT_REPO_URL=https://github.com/EricZimmerman/RBCmd.git
ARG RBCmd_GIT_BRANCH=master # Or specify a tag like 'v1.5.1.0' or a commit hash
RUN git clone --branch ${RBCmd_GIT_BRANCH} --depth 1 ${RBCmd_GIT_REPO_URL} /tmp/RBCmd_source_build
WORKDIR /tmp/RBCmd_source_build
RUN dotnet publish ./RBCmd/RBCmd.csproj --framework net9.0 -c Release --no-self-contained -o /opt/RBCmd_built_from_source
WORKDIR /
RUN rm -rf /tmp/RBCmd_source_build

# --- Build AppCompatCacheParser ---
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

RUN mkdir -p /opt/AppCompatCacheParser_built_from_source
# Copy all published files (dll, runtimeconfig.json, deps.json, etc.)
RUN cp /app/publish_acc/* /opt/AppCompatCacheParser_built_from_source/
RUN rm -rf ${ACC_SRC_DIR_TMP} /app/publish_acc

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

# Default command if not run from docker-compose (and command being overidden)
CMD ["celery", "--app=src.tasks", "worker", "--task-events", "--concurrency=1", "--loglevel=INFO"]
