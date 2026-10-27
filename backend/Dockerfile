# AR Remittance API - container image.
# Build from the backend folder:  docker build -t ar-api backend
# Multi-stage: libraries are installed and trimmed in "build" (with build tools); the runtime image gets
# only the finished library folders, Tesseract with the 7 language packs, and our code.
#
# Free GHCR storage is 500 MB, and image versions share identical layers. So the layers are ordered from
# "almost never changes" to "changes every deploy":
#   base image (pinned digest) -> Tesseract -> /opt/heavy (requirements-heavy.txt: PyMuPDF, OpenCV,
#   numpy, Pillow, ~2/3 of the libraries) -> /opt/venv (requirements.txt) -> our code.
# A normal code change adds only the code layer; a requirements.txt change adds only the /opt/venv layer.
# Size report without pushing: GitHub Actions -> "Image size report".

# Bump on purpose (one new full image copy): docker.io python:3.12-slim, digest from 2026-10-27
ARG PYTHON_IMAGE=python:3.12-slim@sha256:12316debbfb86890f6b2d825820612741ba527ad5a44e3902759141d572bfe8f

# ---- Stage 1: install Python packages, then trim them ----
FROM ${PYTHON_IMAGE} AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_COMPILE=1
# binutils = "strip" for trim.sh; only in this stage
RUN apt-get update && apt-get install -y --no-install-recommends binutils && rm -rf /var/lib/apt/lists/*
COPY docker/trim.sh /usr/local/bin/trim.sh

# 1) the large libraries into their own folder (own layer in the runtime image)
COPY requirements-heavy.txt .
RUN pip install --target /opt/heavy -r requirements-heavy.txt && sh /usr/local/bin/trim.sh /opt/heavy

# 2) everything else into a virtual environment that also sees /opt/heavy (.pth file), so pip
#    treats the large libraries as already installed
COPY requirements.txt .
RUN python -m venv /opt/venv \
 && echo /opt/heavy > /opt/venv/lib/python3.12/site-packages/00-heavy.pth \
 && /opt/venv/bin/pip install -r requirements.txt \
 # pip / setuptools are only needed to install; not at run time
 && (/opt/venv/bin/python -m pip uninstall -y -q pip setuptools wheel 2>/dev/null || true) \
 # google-api-python-client bundles ~500 API descriptions; keep only Gmail's
 && find /opt/venv -path "*googleapiclient/discovery_cache/documents/*" ! -name "gmail.v1.json" -delete \
 && sh /usr/local/bin/trim.sh /opt/venv/lib/python3.12/site-packages \
 # check the finished set imports (fails the build early, e.g. if stripping broke a library)
 && /opt/venv/bin/python -c "import cv2, fitz, numpy, PIL, pdfplumber, docx, openpyxl, pytesseract, fastapi, uvicorn, sqlalchemy, psycopg, alembic, googleapiclient, azure.storage.blob, azure.identity; print('imports ok')"

# ---- Stage 2: runtime image ----
FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    ENVIRONMENT=demo

# Tesseract OCR + languages eng deu fra spa por jpn jpn_vert + orientation/script detection (osd);
# package lists, docs, manuals and translations are removed in the same step (no extra layer)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      tesseract-ocr tesseract-ocr-osd tesseract-ocr-eng tesseract-ocr-deu tesseract-ocr-fra \
      tesseract-ocr-spa tesseract-ocr-por tesseract-ocr-jpn tesseract-ocr-jpn-vert \
 && rm -rf /var/lib/apt/lists/* /var/cache/apt/* /usr/share/doc/* /usr/share/man/* /usr/share/locale/* \
 && tesseract --version \
 && tesseract --list-langs

# Non-root user that runs the app
RUN useradd --create-home --uid 10001 appuser
COPY --from=build /opt/heavy /opt/heavy
COPY --from=build /opt/venv /opt/venv

# Code lives in /srv/backend so the app's PROJECT_ROOT is /srv (same layout as the repo)
WORKDIR /srv/backend
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser scripts ./scripts
COPY --chown=appuser:appuser app ./app

USER appuser
EXPOSE 8000
# 1) bring the database to the latest Alembic version (safe: the app runs at most 1 replica)
# 2) start the API; --proxy-headers: Azure's ingress terminates HTTPS and forwards the request
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips '*'"]
