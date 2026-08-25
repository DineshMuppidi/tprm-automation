# Multi-stage build: a slim runtime image with no compiler toolchain in
# the final layer. Not built or run in this sandbox (no Docker daemon
# available — see README's "Running it" section for what actually was
# verified here); written to be correct and pulled straight into a real
# CI/CD pipeline, not aspirational.

FROM python:3.13-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.13-slim

# Non-root runtime user (Phase 5 spec §1b container security).
RUN groupadd --gid 1000 tprm && useradd --uid 1000 --gid tprm --shell /bin/bash --create-home tprm

WORKDIR /app
COPY --from=builder /root/.local /home/tprm/.local
COPY app ./app
COPY db ./db

RUN chown -R tprm:tprm /app
USER tprm
ENV PATH=/home/tprm/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live', timeout=3)" || exit 1

# Workers: 2 as a conservative default for a small deployment — the Phase 0
# architecture scales this tier horizontally (more replicas) rather than
# more workers per instance, so this isn't meant to be tuned way up here.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
