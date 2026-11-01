# Pinned toolchain for Bella: GCC 16.x (C++26) + CPython 3.14.8 + uv-locked Python deps.
#
# Pin the exact GCC patch release once verified with `docker pull`: e.g. --build-arg GCC_IMAGE=gcc:16.2.0
# The official `gcc` image tracks upstream releases (tags like 16, 16.2, 16.2.0).
ARG GCC_IMAGE=gcc:16.2
FROM ${GCC_IMAGE}

ARG PYTHON_VERSION=3.14.8
ARG UV_VERSION=0.9

RUN apt-get update \
 && apt-get install -y --no-install-recommends cmake ninja-build ca-certificates curl git \
 && rm -rf /var/lib/apt/lists/*

# uv manages the pinned CPython and the locked dependency set.
COPY --from=ghcr.io/astral-sh/uv:${UV_VERSION} /uv /uvx /bin/
ENV UV_PYTHON_INSTALL_DIR=/opt/python \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy
RUN uv python install ${PYTHON_VERSION}
ENV UV_PYTHON=${PYTHON_VERSION} \
    PATH=/opt/venv/bin:$PATH

WORKDIR /work
COPY pyproject.toml ./
# uv.lock is the real pin for Python dependencies; generate it with `uv lock` and commit it.
COPY uv.lock* ./
RUN if [ -f uv.lock ]; then uv sync --extra dev --frozen; else uv sync --extra dev; fi

COPY . .

# Record what this toolchain actually supports (reflection, <generator>, <flat_map>, ...).
RUN make probes CXX=g++ CXXSTD=c++26 || true

CMD ["make", "check"]
