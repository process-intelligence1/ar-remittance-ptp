# AR Remittance API - container image.
# Build from the backend folder:  docker build -t ar-api backend
# (No Tesseract yet; OCR is added in a later step.)

# ---- Stage 1: install Python packages into a virtual environment ----
FROM python:3.12-slim AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---- Stage 2: small runtime image with only the venv and our code ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    ENVIRONMENT=demo

# Non-root user that runs the app
RUN useradd --create-home --uid 10001 appuser
COPY --from=build /opt/venv /opt/venv

# Code lives in /srv/backend so the app's PROJECT_ROOT is /srv (same layout as the repo)
WORKDIR /srv/backend
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser scripts ./scripts

USER appuser
EXPOSE 8000
# --proxy-headers: Azure's ingress terminates HTTPS and forwards the request
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
