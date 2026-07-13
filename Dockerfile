# Copyright (c) 2025-2026 Timothy C.A. Molteno
# Use Python 3.12 as base image
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    casacore-dev \
    gcc g++ \
    libblas-dev liblapack-dev \
    wcslib-dev libcfitsio-dev \
    libboost-python-dev \
    cmake ninja-build \
    casacore-data \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install uv
RUN pip install --no-cache-dir uv

# Force C++17 for architectures where python-casacore builds from source.
# On x86_64 (pre-built wheel) this is ignored.
ENV CMAKE_ARGS="-DCMAKE_CXX_STANDARD=17"

# Install the tartball module
RUN uv pip install --system --no-cache python-casacore .

# Set metadata labels
LABEL org.opencontainers.image.source="https://github.com/tart-telescope/tartball"
LABEL org.opencontainers.image.description="Prediction code to simulate TART data"
LABEL org.opencontainers.image.licenses="GPL-3.0"

# Default command
CMD ["python", "--version"]
