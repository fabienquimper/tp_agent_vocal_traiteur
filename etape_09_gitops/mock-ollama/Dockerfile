# ─────────────────────────────────────────────────────────────────────────────
# mock-ollama — Dockerfile
#
# Image ultra-légère (~50 MB) qui simule l'API Ollama REST.
# N'utilise que la bibliothèque standard Python — zéro dépendance.
#
# Comparaison :
#   ollama/ollama (avec Mistral) : ~4.5 GB, démarrage ~60s
#   mock-ollama                  : ~50 MB,  démarrage ~1s
#
# Utilisé en CI (GitHub Actions) où la RAM est limitée et le temps compte.
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

WORKDIR /app

# Copier uniquement le serveur — pas de requirements.txt (bibliothèque standard)
COPY server.py .

# Port Ollama standard
EXPOSE 11434

# Healthcheck identique à Ollama réel
HEALTHCHECK --interval=5s --timeout=3s --retries=5 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:11434/')"

CMD ["python3", "server.py"]
