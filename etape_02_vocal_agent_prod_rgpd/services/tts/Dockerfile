# ─────────────────────────────────────────────────────────────────────────────
# Service TTS (Text-to-Speech) – piper-tts
# Voix française "siwis" (medium) téléchargée au build (~60 MB)
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 120 --retries 5 -r requirements.txt

# Téléchargement du modèle de voix française (Siwis, qualité medium)
# Autres voix disponibles sur : https://huggingface.co/rhasspy/piper-voices
RUN mkdir -p /app/voices && \
    wget -q --show-progress \
        -O /app/voices/fr_FR-siwis-medium.onnx \
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx" && \
    wget -q \
        -O /app/voices/fr_FR-siwis-medium.onnx.json \
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx.json"

COPY app.py .

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8002/health || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8002"]
