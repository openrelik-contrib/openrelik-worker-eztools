# ------------------------------------------------------
#   LECMD-BUILDER-STAGE
# ------------------------------------------------------
FROM ubuntu:24.04 AS lecmd-builder

# Prevent needing to configure debian packages, stopping the setup of
# the docker container.
RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections

# Install .NET SDK and Git
RUN apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common && \
    add-apt-repository ppa:dotnet/backports && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        dotnet-sdk-9.0 \
        git

# Configure repository to clone from
ARG LECMD_GIT_REPO_URL=https://github.com/EricZimmerman/LECmd.git
ARG LECMD_GIT_BRANCH=master

# Clone and build LECmd
RUN git clone --branch ${LECMD_GIT_BRANCH} --depth 1 ${LECMD_GIT_REPO_URL} /tmp/LECmd_source_build
WORKDIR /tmp/LECmd_source_build
RUN dotnet publish ./LECmd/LECmd.csproj --framework net9.0 -c Release --no-self-contained -o /opt/LECmd_built_from_source


# ------------------------------------------------------
#   RBCMD-BUILDER-STAGE
# ------------------------------------------------------
FROM ubuntu:24.04 AS rbcmd-builder

# Prevent needing to configure debian packages, stopping the setup of
# the docker container.
RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections

# Install .NET SDK and Git
RUN apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common && \
    add-apt-repository ppa:dotnet/backports && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        dotnet-sdk-9.0 \
        git

# Configure repository to clone from
ARG RBCmd_GIT_REPO_URL=https://github.com/EricZimmerman/RBCmd.git
ARG RBCmd_GIT_BRANCH=master

# Clone and build RBCmd
RUN git clone --branch ${RBCmd_GIT_BRANCH} --depth 1 ${RBCmd_GIT_REPO_URL} /tmp/RBCmd_source_build
WORKDIR /tmp/RBCmd_source_build
RUN dotnet publish ./RBCmd/RBCmd.csproj --framework net9.0 -c Release --no-self-contained -o /opt/RBCmd_built_from_source


# ------------------------------------------------------
#   APP_COMPAT_CACHE_PARSER-BUILDER-STAGE
# ------------------------------------------------------
FROM ubuntu:24.04 AS aca-builder

# Prevent needing to configure debian packages, stopping the setup of
# the docker container.
RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections

# Install .NET SDK and Git
RUN apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common && \
    add-apt-repository ppa:dotnet/backports && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        dotnet-sdk-9.0 \
        git

# Configuration
ARG ACC_REPO_URL=https://github.com/EricZimmerman/AppCompatCacheParser.git
ARG ACC_SRC_DIR_TMP=/tmp/AppCompatCacheParser_src

# Clone and build AppCompatCacheParser
RUN git clone ${ACC_REPO_URL} ${ACC_SRC_DIR_TMP}
RUN cd ${ACC_SRC_DIR_TMP}/AppCompatCacheParser && \
    dotnet publish AppCompatCacheParser.csproj \
    -c Release \
    --framework net9.0 \
    -o /app/publish_acc \
    --no-self-contained \
    /p:UseAppHost=false
RUN mkdir -p /opt/AppCompatCacheParser_built_from_source
RUN cp /app/publish_acc/* /opt/AppCompatCacheParser_built_from_source/


# ------------------------------------------------------
#   OPENRELIK-WORKER-STAGE
# ------------------------------------------------------
FROM ubuntu:24.04 AS openrelik-worker

# Prevent needing to configure debian packages, stopping the setup of
# the docker container.
RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections

# Install runtime, Python Poetry, and clean up apt cache
RUN apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common && \
    add-apt-repository ppa:dotnet/backports && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        python3-poetry \
        dotnet-runtime-9.0 \
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

# Copy compiled binaries from build stages
COPY --from=lecmd-builder /opt/LECmd_built_from_source /opt/LECmd_built_from_source
COPY --from=rbcmd-builder /opt/RBCmd_built_from_source /opt/RBCmd_built_from_source
COPY --from=aca-builder /opt/AppCompatCacheParser_built_from_source /opt/AppCompatCacheParser_built_from_source

# Default command if not run from docker-compose (and command being overidden)
CMD ["celery", "--app=src.tasks", "worker", "--task-events", "--concurrency=1", "--loglevel=INFO"]
