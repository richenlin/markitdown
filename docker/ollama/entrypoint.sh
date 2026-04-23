#!/bin/bash
set -e

MODEL="${OLLAMA_MODEL:-qwen2-vl:7b}"

ollama serve &
OLLAMA_PID=$!

echo "[entrypoint] Waiting for Ollama to start..."
MAX_RETRIES=60
retry=0
until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
    retry=$((retry + 1))
    if [ "$retry" -ge "$MAX_RETRIES" ]; then
        echo "[entrypoint] ERROR: Ollama failed to start within $((MAX_RETRIES * 2)) seconds. Exiting." >&2
        exit 1
    fi
    sleep 2
done
echo "[entrypoint] Ollama is ready."

if ollama list | grep -q "^${MODEL}"; then
    echo "[entrypoint] Model ${MODEL} already cached, skipping pull."
else
    echo "[entrypoint] Pulling model ${MODEL} (first boot, may take several minutes)..."
    ollama pull "${MODEL}"
    echo "[entrypoint] Model ${MODEL} ready."
fi

wait $OLLAMA_PID
