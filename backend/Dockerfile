# ---- Builder stage ----
FROM python:3.12.8-slim-bookworm AS builder

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Download and verify Terraform in builder
ARG TARGETARCH
ARG TERRAFORM_VERSION=1.9.8
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl unzip ca-certificates && \
    ARCH=${TARGETARCH:-amd64} && \
    curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${ARCH}.zip" \
      -o /tmp/terraform.zip && \
    curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_SHA256SUMS" \
      -o /tmp/SHA256SUMS && \
    cd /tmp && grep "terraform_${TERRAFORM_VERSION}_linux_${ARCH}.zip" SHA256SUMS | sha256sum -c - && \
    unzip /tmp/terraform.zip -d /usr/local/bin/ && \
    rm -rf /tmp/terraform.zip /tmp/SHA256SUMS /var/lib/apt/lists/*

# ---- Runtime stage ----
FROM python:3.12.8-slim-bookworm

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG BUILD_DATE
ARG GIT_SHA
ARG VERSION=dev

LABEL org.opencontainers.image.title="AnvilOps API" \
      org.opencontainers.image.description="Server provisioning platform API and Celery workers" \
      org.opencontainers.image.source="https://github.com/jconover/anvilops" \
      org.opencontainers.image.vendor="AnvilOps" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${GIT_SHA}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Copy Terraform binary from builder
COPY --from=builder /usr/local/bin/terraform /usr/local/bin/terraform

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Copy Python packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; r = urllib.request.urlopen('http://localhost:8000/health'); assert r.status == 200" || exit 1

# Default: run API server. Override for Celery worker:
#   docker run <image> celery -A app.worker.celery_app worker --loglevel=info
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
