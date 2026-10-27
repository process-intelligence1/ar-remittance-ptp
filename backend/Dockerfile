# AR Remittance API - container image.
# Build from the backend folder:  docker build -t ar-api backend
# Multi-stage: libraries are installed (and trimmed) in "build"; the runtime image gets only the
# finished virtual environment, Tesseract with the 7 language packs, and our code.

# ---- Stage 1: install Python packages into a virtual environment, then trim it ----
FROM python:3.12-slim AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install -r requirements.txt \
 # test suites shipped inside libraries are never used at run time
 && find /opt/venv -type d \( -name tests -o -name testing \) -path "*/site-packages/*" -prune -exec rm -rf {} + \
 # google-api-python-client bundles ~500 API descriptions; keep only Gmail's
 && find /opt/venv -path "*googleapiclient/discovery_cache/documents/*" ! -name "gmail.v1.json" -delete

# ---- Stage 2: runtime image ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    ENVIRONMENT=demo

# Tesseract OCR + languages eng deu fra spa por jpn jpn_vert + orientation/script detection (osd)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      tesseract-ocr tesseract-ocr-osd tesseract-ocr-eng tesseract-ocr-deu tesseract-ocr-fra \
      tesseract-ocr-spa tesseract-ocr-por tesseract-ocr-jpn tesseract-ocr-jpn-vert \
 && rm -rf /var/lib/apt/lists/* \
 && tesseract --version \
 && tesseract --list-langs

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
# 1) bring the database to the latest Alembic version (safe: the app runs at most 1 replica)
# 2) start the API; --proxy-headers: Azure's ingress terminates HTTPS and forwards the request
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips '*'"]
