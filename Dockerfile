# Terry - Personal AI Coding Agent
# Multi-stage build for minimal image size
# Supports: linux/amd64, linux/arm64 (Apple Silicon, AWS Graviton, Raspberry Pi 4/5)
# Build for both: docker buildx build --platform linux/amd64,linux/arm64 -t terry .

FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache -e ".[dev]" || \
    pip install --no-cache-dir anthropic openai httpx python-dotenv rich typer pyyaml

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY . .

# Create terry user for security
RUN useradd --create-home --shell /bin/bash terry && \
    mkdir -p /home/terry/.terry && \
    chown -R terry:terry /app /home/terry/.terry

USER terry
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "terry.cli"]
