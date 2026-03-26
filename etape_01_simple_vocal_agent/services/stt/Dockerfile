# ─────────────────────────────────────────────────────────────────────────────
# Service STT (Speech-to-Text) – faster-whisper
# Modèle Whisper "base" (~145 MB) téléchargé au build
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Dépendances système : ffmpeg pour décoder les formats audio
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pré-téléchargement du modèle Whisper (évite le téléchargement au 1er appel)
# Modèles disponibles : tiny, base, small, medium, large-v2, large-v3
# "base" = bon équilibre vitesse/qualité pour le français
RUN python -c "\
from faster_whisper import WhisperModel; \
print('Téléchargement du modèle Whisper base...'); \
WhisperModel('base', device='cpu', download_root='/models'); \
print('Modèle prêt.')"

COPY app.py .

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8001/health || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
