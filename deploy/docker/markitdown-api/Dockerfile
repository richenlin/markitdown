FROM python:3.12-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    tesseract-ocr-chi-tra \
    tesseract-ocr-eng \
    exiftool \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY packages/ /app/packages/
RUN pip --no-cache-dir install \
    "/app/packages/markitdown[all]" \
    "/app/packages/markitdown-ocr[all]" \
    "/app/packages/markitdown-mcp" \
    "fastapi>=0.110.0" \
    "uvicorn[standard]>=0.29.0" \
    "python-multipart>=0.0.9"

COPY deploy/docker/markitdown-api/app.py /app/app.py

EXPOSE 8778

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8778/api/health || exit 1

CMD ["python", "app.py"]
