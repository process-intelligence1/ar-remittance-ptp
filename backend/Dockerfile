# AR Remittance - container images (one Dockerfile, two targets).
#   --target api     slim image: API + database migrations. No Tesseract, OpenCV, numpy, Pillow, office readers.
#                    Small image = faster cold start (the API container scales to zero and is pulled/started on demand).
#   --target worker  full image: everything for reading documents (OCR) - used by the scheduled worker job.
# Build from the backend folder:  docker build --target api -t ar-api backend   (or --target worker)
#
# Layers are ordered from "almost never changes" to "changes every deploy", so a normal code change adds only the
# small code layers (GHCR keeps the 3 newest versions + the running one; public packages are free):
#   base image (pinned digest) -> [worker: Tesseract -> /opt/heavy] -> /opt/venv -> our code (+ compiled .pyc).
# Size report without pushing: GitHub Actions -> "Image size report". The deploy workflow prints both sizes.

# Bump on purpose (one new full image copy): docker.io python:3.12-slim, digest from 2026-10-27
ARG PYTHON_IMAGE=python:3.12-slim@sha256:12316debbfb86890f6b2d825820612741ba527ad5a44e3902759141d572bfe8f

# ---- build stage, slim: the API's libraries (requirements-api.txt), trimmed ----
FROM ${PYTHON_IMAGE} AS build-api
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_COMPILE=1
RUN apt-get update && apt-get install -y --no-install-recommends binutils && rm -rf /var/lib/apt/lists/*
COPY docker/trim.sh /usr/local/bin/trim.sh
COPY requirements-api.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install -r requirements-api.txt \
 && (/opt/venv/bin/python -m pip uninstall -y -q pip setuptools wheel 2>/dev/null || true) \
 # google-api-python-client bundles ~500 API descriptions; keep only Gmail's
 && find /opt/venv -path "*googleapiclient/discovery_cache/documents/*" ! -name "gmail.v1.json" -delete \
 && sh /usr/local/bin/trim.sh /opt/venv/lib/python3.12/site-packages \
 # check the finished set imports (fails the build early, e.g. if stripping broke a library)
 && /opt/venv/bin/python -c "import fitz, fastapi, uvicorn, sqlalchemy, psycopg, alembic, googleapiclient, mailparser_reply, azure.storage.blob, azure.identity, jwt, pydantic_settings; print('api imports ok')"

# ---- build stage, full: large libraries in their own folder, then everything else ----
FROM ${PYTHON_IMAGE} AS build-full
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_COMPILE=1
RUN apt-get update && apt-get install -y --no-install-recommends binutils && rm -rf /var/lib/apt/lists/*
COPY docker/trim.sh /usr/local/bin/trim.sh
# 1) the large libraries into their own folder (own layer in the worker image)
COPY requirements-heavy.txt .
RUN pip install --target /opt/heavy -r requirements-heavy.txt && sh /usr/local/bin/trim.sh /opt/heavy
# 2) everything else into a virtual environment that also sees /opt/heavy (.pth file), so pip
#    treats the large libraries as already installed
COPY requirements.txt .
RUN python -m venv /opt/venv \
 && echo /opt/heavy > /opt/venv/lib/python3.12/site-packages/00-heavy.pth \
 && /opt/venv/bin/pip install -r requirements.txt \
 && (/opt/venv/bin/python -m pip uninstall -y -q pip setuptools wheel 2>/dev/null || true) \
 && find /opt/venv -path "*googleapiclient/discovery_cache/documents/*" ! -name "gmail.v1.json" -delete \
 && sh /usr/local/bin/trim.sh /opt/venv/lib/python3.12/site-packages \
 && /opt/venv/bin/python -c "import cv2, fitz, numpy, PIL, pdfplumber, docx, openpyxl, pytesseract, fastapi, uvicorn, sqlalchemy, psycopg, alembic, googleapiclient, azure.storage.blob, azure.identity, jwt; print('worker imports ok')"

# ---- runtime base shared by both images ----
FROM ${PYTHON_IMAGE} AS runtime
# No bytecode is written at run time (read-only habits, same layers); our own code is compiled below instead.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    ENVIRONMENT=demo
RUN useradd --create-home --uid 10001 appuser
# Code lives in /srv/backend so the app's PROJECT_ROOT is /srv (same layout as the repo)
WORKDIR /srv/backend

# ---------------------------------------------------------------- target: api (slim)
FROM runtime AS api
COPY --from=build-api /opt/venv /opt/venv
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser app ./app
# Pre-compile our own code (libraries are already compiled by trim.sh): no compiling at cold start.
RUN python -m compileall -q -j 0 --invalidation-mode unchecked-hash app alembic
USER appuser
EXPOSE 8000
# Database migrations are NOT run here: the one-off Container Apps job "ar-migrate" (same image, command
# "alembic upgrade head") runs them once per deploy before this image goes live.
# --proxy-headers: Azure's ingress terminates HTTPS and forwards the request
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

# ---------------------------------------------------------------- target: worker (full)
FROM runtime AS worker
# Tesseract OCR + languages eng deu fra spa por jpn jpn_vert + orientation/script detection (osd);
# package lists, docs, manuals and translations are removed in the same step (no extra layer)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      tesseract-ocr tesseract-ocr-osd tesseract-ocr-eng tesseract-ocr-deu tesseract-ocr-fra \
      tesseract-ocr-spa tesseract-ocr-por tesseract-ocr-jpn tesseract-ocr-jpn-vert \
 && rm -rf /var/lib/apt/lists/* /var/cache/apt/* /usr/share/doc/* /usr/share/man/* /usr/share/locale/* \
 && tesseract --version \
 && tesseract --list-langs
COPY --from=build-full /opt/heavy /opt/heavy
COPY --from=build-full /opt/venv /opt/venv
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser scripts ./scripts
COPY --chown=appuser:appuser app ./app
RUN python -m compileall -q -j 0 --invalidation-mode unchecked-hash app alembic scripts
USER appuser
# The scheduled job sets its own command (python -m app.worker --once); this is the default.
CMD ["python", "-m", "app.worker", "--once"]
