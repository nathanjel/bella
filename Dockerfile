# Pinned toolchain for Bella: GCC 16.2.0 (C++26) + CPython 3.14.8 + uv-locked Python deps.
#
# Both base images are pinned by tag and digest (pulled 2026-11-01; the gcc digest is the
# multi-arch index, so linux/arm64 resolves to the same release). uv is pinned exactly because
# the uv release decides which python-build-standalone build of 3.14.8 is installed
# (uv 0.13.6 -> cpython-3.14.8+20261013); pyproject.toml [tool.uv] requires the same version.
ARG GCC_IMAGE=gcc:16.2.0@sha256:07280eb2e744f1b7a2d8d4a3894c089ea07266c109758afc388a634bd098e4eb
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0
FROM ${UV_IMAGE} AS uv
FROM ${GCC_IMAGE}

ARG PYTHON_VERSION=3.14.8

RUN apt-get update \
 && apt-get install -y --no-install-recommends cmake ninja-build ca-certificates curl git \
 && rm -rf /var/lib/apt/lists/*

# uv manages the pinned CPython and the locked dependency set.
COPY --from=uv /uv /uvx /bin/
ENV UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy
RUN uv python install ${PYTHON_VERSION}
ENV UV_PYTHON=${PYTHON_VERSION} \
    PATH=/opt/venv/bin:$PATH

WORKDIR /work
COPY pyproject.toml uv.lock .python-version ./
# uv.lock is the pin for Python dependencies; --frozen refuses to build if it is stale.
RUN uv sync --extra dev --frozen

COPY . .

# Record what this toolchain actually supports (reflection, <generator>, <flat_map>, ...).
RUN make probes CXX=g++ CXXSTD=c++26 || true

CMD ["make", "check"]
