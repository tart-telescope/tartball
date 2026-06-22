# Use Python 3.12 as base image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install uv
RUN pip install --no-cache-dir uv

# Install the tartball module
RUN uv pip install --system --no-cache .

# Set metadata labels
LABEL org.opencontainers.image.source="https://github.com/tart-telescope/tartball"
LABEL org.opencontainers.image.description="Prediction code to simulate TART data"
LABEL org.opencontainers.image.licenses="GPL-3.0"

# Default command
CMD ["python", "--version"]
