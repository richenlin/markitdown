FROM python:3.13-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive
ENV EXIFTOOL_PATH=/usr/bin/exiftool
ENV FFMPEG_PATH=/usr/bin/ffmpeg

# Runtime dependencies: media tools + Tesseract OCR with CJK language packs
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    exiftool \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-chi-sim \
    tesseract-ocr-chi-tra \
    && rm -rf /var/lib/apt/lists/*

ARG INSTALL_GIT=false
RUN if [ "$INSTALL_GIT" = "true" ]; then \
    apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*; \
    fi

WORKDIR /app
COPY . /app

RUN pip --no-cache-dir install \
    "/app/packages/markitdown[all]" \
    "/app/packages/markitdown-ocr[tesseract]" \
    /app/packages/markitdown-sample-plugin

# Default USERID and GROUPID
# Defaults to root so the container can write to any host-mounted directory.
# Override at runtime with: docker run --user $(id -u):$(id -g) ...
ARG USERID=root
ARG GROUPID=root

USER $USERID:$GROUPID

# -p enables the markitdown-ocr plugin (Tesseract offline OCR) by default.
# Any arguments passed to `docker run <image> ...` are appended after -p.
ENTRYPOINT ["markitdown", "-p"]
