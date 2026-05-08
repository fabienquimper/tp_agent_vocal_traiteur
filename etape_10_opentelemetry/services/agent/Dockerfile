# ─────────────────────────────────────────────────────────────────────────────
# Service Agent IA – LangGraph + LangChain + FastAPI
# Modèle d'embeddings sentence-transformers (~90 MB) téléchargé au build
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Installation des dépendances Python (ordre optimisé pour le cache Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pré-téléchargement du modèle d'embeddings multilingue (~90 MB)
# Ce modèle gère très bien le français et évite de dépendre d'Ollama pour les embeddings
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
print('Téléchargement du modèle embeddings...'); \
SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2'); \
print('Modèle embeddings prêt.')"

# Code de l'application (séparé des deps pour profiter du cache)
COPY app/ ./app/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
