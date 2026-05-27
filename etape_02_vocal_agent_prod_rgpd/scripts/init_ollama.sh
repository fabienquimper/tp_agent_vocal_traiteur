#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Téléchargement du modèle LLM dans le conteneur Ollama
# À exécuter après "make up" ou "docker compose up -d"
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

MODEL="${1:-mistral}"
CONTAINER="traiteur_ollama"

echo "Vérification du conteneur Ollama..."
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  echo "Erreur : le conteneur '${CONTAINER}' n'est pas en cours d'exécution."
  echo "Lancez d'abord : docker compose up -d"
  exit 1
fi

echo "Téléchargement du modèle '${MODEL}' (peut prendre plusieurs minutes)..."
docker exec "${CONTAINER}" ollama pull "${MODEL}"

echo ""
echo "✓ Modèle '${MODEL}' prêt dans Ollama."
echo ""
echo "Pour vérifier les modèles disponibles :"
echo "  docker exec ${CONTAINER} ollama list"
