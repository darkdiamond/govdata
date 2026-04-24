# Cloud Run container for govdata-builder.
#
# One container per scheduler tick; parallelism across sources lives inside
# the container via asyncio.gather. Python-only — the Node/Firebase build is
# handled separately by Cloud Build (cloudbuild-publish.yaml).

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    PORT=8080

WORKDIR /app

# Install deps first so the layer is cached across code changes.
COPY services/page_builder/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy only what the Cloud Run service needs.
COPY services/__init__.py ./services/__init__.py
COPY services/shared ./services/shared
COPY services/scanner ./services/scanner
COPY services/page_builder ./services/page_builder

EXPOSE 8080

# functions-framework exposes the HTTP entry defined in services/page_builder/main.py.
CMD exec functions-framework \
    --target=http_entry \
    --source=services/page_builder/main.py \
    --host=0.0.0.0 \
    --port=${PORT}
