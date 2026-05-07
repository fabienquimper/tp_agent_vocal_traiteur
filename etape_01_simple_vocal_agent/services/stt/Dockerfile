# ─────────────────────────────────────────────────────────────────────────────
# Service STT (Speech-to-Text) – faster-whisper
# Modèle Whisper pré-téléchargé au build (configurable via ARG WHISPER_MODEL)
# Modèles : tiny, base, small, medium, large-v2, large-v3
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

ARG WHISPER_MODEL=base

WORKDIR /app

# Dépendances système : ffmpeg pour décoder les formats audio
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 120 --retries 5 -r requirements.txt

# Pré-téléchargement du modèle Whisper (évite le téléchargement au 1er appel)
# Le modèle est choisi via l'ARG WHISPER_MODEL (défaut : base)
RUN python -c "\
import os; \
model = os.environ.get('WHISPER_MODEL', '${WHISPER_MODEL}'); \
from faster_whisper import WhisperModel; \
print(f'Téléchargement du modèle Whisper {model}...'); \
WhisperModel(model, device='cpu', download_root='/models'); \
print('Modèle prêt.')"

COPY app.py .

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8001/health || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
