# ──────────────────────────────────────────────────────────────────────────────
# Traiteur Dupont – Agent Vocal IA (Étape 02)
# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl wget && rm -rf /var/lib/apt/lists/*

# Dépendances Python (couche Docker mise en cache séparément du code)
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 120 --retries 5 -r requirements.txt

# Voix piper française (utilisée si TTS_PROVIDER=embedded)
RUN mkdir -p /app/voices && \
    wget -q -O /app/voices/fr_FR-siwis-medium.onnx \
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx" && \
    wget -q -O /app/voices/fr_FR-siwis-medium.onnx.json \
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx.json"

# Code source
COPY src/ ./src/

# Interface web (servie par FastAPI StaticFiles)
COPY ui/ ./ui/

# Répertoire de sortie des commandes (volume monté à l'exécution)
RUN mkdir -p /app/orders

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
